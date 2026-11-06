"""Classify what the rules left as "Da classificare" with the OpenAI Batch API (via kitai), by description.

Only the (normalized) description is sent — no amounts, dates or account data. Answers are kept only if the
category is one the rules already know; anything else stays "Da classificare". Results are cached on disk so
a rerun never pays twice. The Batch API is asynchronous (up to 24h), so this blocks while polling.
"""
import json
import re
from pathlib import Path

from bankanalyst.models import Transaction

MODEL = "gpt-4o-mini"
SYSTEM = (
    "Sei un assistente che categorizza movimenti bancari italiani a partire dalla sola descrizione. "
    "Scegli UNA categoria dall'elenco fornito. Rispondi solo con JSON: {\"category\": \"<nome esatto>\"}. "
    "Se non sei ragionevolmente sicuro, rispondi {\"category\": \"Da classificare\"}.\nCategorie:\n{categories}"
)


def normalize(description: str) -> str:
    return re.sub(r"\s+", " ", description).strip().lower()


def build_items(txs: list[Transaction]) -> list[dict]:
    """One item per distinct normalized description (id = position, content = the description)."""
    seen = list(dict.fromkeys(normalize(t.description) for t in txs))
    return [{"id": str(i), "content": d} for i, d in enumerate(seen)]


def parse_labels(results: list[dict], items: list[dict], allowed: set[str]) -> dict[str, str]:
    """{description: category} from raw batch results; unknown or unparseable answers are dropped."""
    if not results:
        return {}
    from kitai.batch import parse_chat_results

    by_id = {f"custom_id_{it['id']}": it["content"] for it in items}

    def extract(text: str) -> str:
        cat = json.loads(text)["category"]
        if cat not in allowed:
            raise ValueError(f"categoria sconosciuta: {cat!r}")
        return cat

    return {by_id[cid]: cat for cid, cat in parse_chat_results(results, extract) if cid in by_id}


def _load(path: Path | None) -> dict[str, str]:
    if path and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def classify_with_batch(txs: list[Transaction], allowed: set[str], cache_path: str | Path | None = None,
                        client=None, model: str = MODEL, poll_interval: float = 30.0) -> dict[str, str]:
    """{normalized description: category} for the given transactions. `client` defaults to OpenAI()."""
    cache_file = Path(cache_path) if cache_path else None
    labels = _load(cache_file)
    todo = [it for it in build_items(txs) if it["content"] not in labels]
    if todo:
        from kitai.batch import build_chat_tasks, download_batch_results, poll_until_complete, submit_batch_job

        if client is None:
            from openai import OpenAI

            client = OpenAI()
        system = SYSTEM.replace("{categories}", "\n".join(f"- {c}" for c in sorted(allowed)))
        tasks = build_chat_tasks(todo, system, model=model)
        for t in tasks:
            t["body"]["response_format"] = {"type": "json_object"}
            t["body"]["temperature"] = 0
        job = submit_batch_job(client, tasks, endpoint="/v1/chat/completions")
        if job not in poll_until_complete(client, [job], poll_interval=poll_interval):
            raise RuntimeError(f"Batch {job} non completato: controlla la dashboard OpenAI")
        labels.update(parse_labels(download_batch_results(client, job), todo, allowed))
        if cache_file:
            cache_file.write_text(json.dumps(labels, ensure_ascii=False, indent=1), encoding="utf-8")
    wanted = {normalize(t.description) for t in txs}
    return {d: c for d, c in labels.items() if d in wanted}
