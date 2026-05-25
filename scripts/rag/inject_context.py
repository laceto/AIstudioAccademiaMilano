"""
inject_context.py — Context Injector Agent
Reads CLAUDE_USER_PROMPT from environment, retrieves top-5 repo chunks,
prints a <repo-context> block to stdout for Claude Code injection.

Called by the UserPromptSubmit hook in .claude/settings.json.
Claude Code captures stdout and injects it into the conversation context
before Claude processes the user's message.

Design invariants:
- Never raises — any failure exits 0 silently. Pipeline must never be blocked.
- Skips queries shorter than 10 chars (single words, git commands, "pull").
- Skips silently if vectorstore not yet built.
- Uses strategy="none" — no LLM translation call; sub-second latency.
- Outputs a clearly delimited <repo-context> XML block.

Manual test:
    set CLAUDE_USER_PROMPT=how does invoice pricing work?
    python -m scripts.rag.inject_context
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
VECTORSTORE_DIR = ROOT / "data" / "vectorstore" / "repo"
MIN_QUERY_LEN   = 10   # skip very short prompts
TOP_K           = 5    # chunks to inject


def main() -> None:
    query = os.environ.get("CLAUDE_USER_PROMPT", "").strip()

    if len(query) < MIN_QUERY_LEN:
        sys.exit(0)

    if not VECTORSTORE_DIR.exists():
        sys.exit(0)

    try:
        from scripts.rag.retrieve_repo import retrieve
        docs = retrieve(query, top_k=TOP_K, strategy="none")
    except Exception:
        sys.exit(0)

    if not docs:
        sys.exit(0)

    lines = [
        "<repo-context>",
        f"<!-- auto-retrieved for: {query[:80]} -->",
    ]
    for i, doc in enumerate(docs, 1):
        path  = doc.metadata.get("path", "unknown")
        chunk = doc.metadata.get("chunk_index", 0)
        lines.append(f"\n[{i}] {path} (chunk {chunk})")
        lines.append(doc.page_content[:400])
    lines.append("</repo-context>")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
