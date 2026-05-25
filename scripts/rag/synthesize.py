"""
synthesize.py — Synthesizer Agent
Submits (query, context) pairs to OpenAI via kitai.batch chat completions.
Returns structured RepoAnswer objects (Pydantic strict schema).

Async, 50% cheaper than synchronous calls. Used by the learning loop for:
- "what did we learn from similar past requests?"
- Deep cross-audit analysis
- Bulk multi-query synthesis

Mirrors rss_feed/batch/create_batch_files_v2.py exactly.

Usage:
    # Submit batch (retrieves context automatically):
    python -m scripts.rag.synthesize --queries "q1" "q2" "q3"

    # Poll results (reads data/pending_synthesis_batch.txt):
    python -m scripts.rag.synthesize --poll

    # Submit without auto-retrieval (provide context inline):
    python -m scripts.rag.synthesize --queries "q1" --no-retrieve --context "context text"
"""

import argparse
import logging
import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

from config.brand import b, fmt
from kitai.batch import (
    download_batch_results,
    poll_until_complete,
    submit_batch_job,
)

ROOT                  = Path(__file__).parent.parent.parent
PENDING_BATCH_FILE    = ROOT / "data" / "pending_synthesis_batch.txt"
SYNTHESIS_RESULTS_DIR = ROOT / "data" / "synthesis_results"
CHAT_MODEL            = "gpt-4o-mini"

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger(__name__)


# ── Pydantic schema ───────────────────────────────────────────────────────────

class RepoAnswer(BaseModel):
    """Structured answer extracted from repo context chunks."""
    answer:     str                           = Field(..., description="Direct answer to the question based on the context.")
    confidence: Literal["high", "medium", "low"] = Field(..., description="Confidence based on context quality and completeness.")
    key_files:  list[str]                     = Field(default_factory=list, description="Most relevant file paths from the context.")
    gaps:       list[str]                     = Field(default_factory=list, description="What information is missing or unclear in the context.")


# ── Schema strictification (mirrors rss_feed _make_openai_strict) ─────────────

def _make_strict(schema: dict) -> dict:
    import copy
    schema = copy.deepcopy(schema)
    _strict_in_place(schema)
    return schema


def _strict_in_place(node: dict) -> None:
    if not isinstance(node, dict):
        return
    if "$ref" in node:
        for k in list(node.keys()):
            if k != "$ref":
                del node[k]
        return
    if node.get("type") == "object" or "properties" in node:
        node["additionalProperties"] = False
        if "properties" in node:
            node["required"] = list(node["properties"].keys())
            for child in node["properties"].values():
                _strict_in_place(child)
    for sub in node.get("$defs", {}).values():
        _strict_in_place(sub)
    for key in ("anyOf", "allOf", "oneOf"):
        for sub in node.get(key, []):
            _strict_in_place(sub)
    if "items" in node:
        _strict_in_place(node["items"])


STRICT_SCHEMA = _make_strict(RepoAnswer.model_json_schema())

SYSTEM_PROMPT = (
    fmt(b("agent_personas.rag_analyst_prompt")) + "\n"
    "Answer the question using ONLY the provided context excerpts from the repo.\n"
    "If the context is insufficient, reflect that in the confidence field.\n"
    "Return ONLY valid JSON matching the schema. No extra text outside JSON.\n"
)


# ── Task building ─────────────────────────────────────────────────────────────

def build_tasks(queries_with_context: list[tuple[str, str]]) -> list[dict]:
    """Build one batch task per (query, context) pair.

    custom_id format: "synthesis-{i}" — used to align results back to queries.
    """
    tasks = []
    for i, (query, context) in enumerate(queries_with_context):
        payload = f"Context:\n{context}\n\nQuestion: {query}"
        tasks.append({
            "custom_id": f"synthesis-{i}",
            "method":    "POST",
            "url":       "/v1/chat/completions",
            "body": {
                "model":       CHAT_MODEL,
                "temperature": 0,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name":   "repo_answer",
                        "schema": STRICT_SCHEMA,
                        "strict": True,
                    },
                },
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": payload},
                ],
            },
        })
    return tasks


# ── Submit ────────────────────────────────────────────────────────────────────

def submit(tasks: list[dict], client: OpenAI) -> str:
    """Submit tasks to kitai batch and persist the job ID."""
    job_id = submit_batch_job(client, tasks, endpoint="/v1/chat/completions")
    PENDING_BATCH_FILE.parent.mkdir(parents=True, exist_ok=True)
    PENDING_BATCH_FILE.write_text(job_id)
    log.info("Batch submitted: %s → saved to %s", job_id, PENDING_BATCH_FILE)
    return job_id


# ── Retrieve results ──────────────────────────────────────────────────────────

def retrieve_results(job_id: str, client: OpenAI) -> list[tuple[str, RepoAnswer]]:
    """Poll until complete, parse results into (custom_id, RepoAnswer) pairs."""
    completed = poll_until_complete(client, [job_id], poll_interval=30.0)
    if job_id not in completed:
        raise RuntimeError(
            f"Batch {job_id} did not complete. Check OpenAI dashboard.\n"
            f"Resume: python -m scripts.rag.synthesize --poll"
        )

    raw     = download_batch_results(client, job_id)
    results = []
    for item in raw:
        cid = item.get("custom_id", "?")
        try:
            content = item["response"]["body"]["choices"][0]["message"]["content"]
            answer  = RepoAnswer.model_validate_json(content)
            results.append((cid, answer))
        except Exception as e:
            log.warning("Failed to parse result %s: %s", cid, e)

    log.info("Parsed %d/%d results.", len(results), len(raw))
    return results


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Batch RAG synthesis via kitai")
    parser.add_argument("--queries",     nargs="+", help="Questions to synthesize")
    parser.add_argument("--top-k",       type=int,  default=5)
    parser.add_argument("--poll",        action="store_true", help="Poll pending batch and display results")
    parser.add_argument("--no-retrieve", action="store_true", help="Skip auto-retrieval (use with --context)")
    parser.add_argument("--context",     type=str,  default="", help="Context string when --no-retrieve is set")
    args = parser.parse_args()

    load_dotenv()
    client = OpenAI()

    if args.poll:
        if not PENDING_BATCH_FILE.exists():
            print("No pending batch file. Submit first: --queries ...")
            return
        job_id  = PENDING_BATCH_FILE.read_text().strip()
        results = retrieve_results(job_id, client)
        for cid, ans in results:
            print(f"\n[{cid}] confidence={ans.confidence}")
            print(f"Answer: {ans.answer}")
            if ans.key_files:
                print(f"Key files: {', '.join(ans.key_files)}")
            if ans.gaps:
                print(f"Gaps: {', '.join(ans.gaps)}")
        SYNTHESIS_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        import json
        out_path = SYNTHESIS_RESULTS_DIR / f"{job_id}.json"
        out_path.write_text(json.dumps([
            {"id": cid, "answer": ans.answer, "confidence": ans.confidence,
             "key_files": ans.key_files, "gaps": ans.gaps}
            for cid, ans in results
        ], indent=2))
        print(f"\nResults saved → {out_path}")
        return

    if not args.queries:
        parser.print_help()
        return

    queries_with_context: list[tuple[str, str]] = []

    if args.no_retrieve:
        for q in args.queries:
            queries_with_context.append((q, args.context))
    else:
        from scripts.rag.retrieve_repo import retrieve
        for q in args.queries:
            docs    = retrieve(q, top_k=args.top_k, strategy="expand")
            context = "\n\n".join(doc.page_content for doc in docs)
            queries_with_context.append((q, context))

    tasks  = build_tasks(queries_with_context)
    job_id = submit(tasks, client)
    print(f"Submitted {len(tasks)} synthesis task(s). Batch: {job_id}")
    print(f"Results in ~minutes. Poll: python -m scripts.rag.synthesize --poll")


if __name__ == "__main__":
    main()
