"""Mind Dashboard — turn a raw daily journal into a structured briefing.

Usage:
    python mind_dashboard.py --input today.txt
    python mind_dashboard.py --input today.txt --format both --out-dir briefings/
    cat thoughts.txt | python mind_dashboard.py --format html

Outputs:
    <out-dir>/YYYY-MM-DD_Briefing.md   (always, unless --format html)
    <out-dir>/YYYY-MM-DD_Briefing.html (when --format html or both)

Requires:
    ANTHROPIC_API_KEY in the environment (or --dry-run to skip the API call
    and render a deterministic stub from the input — useful for testing).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date as date_cls
from pathlib import Path

from prompts import SYSTEM_PROMPT, build_user_prompt
from templates import render_html, render_markdown, validate

DEFAULT_MODEL = "claude-opus-4-7"


def read_input(path: str | None) -> str:
    if path:
        return Path(path).read_text(encoding="utf-8")
    if sys.stdin.isatty():
        sys.exit("error: no --input file given and stdin is a TTY")
    return sys.stdin.read()


def extract_json(raw: str) -> dict:
    """Pull the first JSON object out of the model's response.

    The system prompt forbids fences, but we strip them defensively in case
    a future model version slips one in.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object in model output:\n{raw[:400]}")
    return json.loads(text[start : end + 1])


def call_claude(journal: str, date_str: str, model: str) -> dict:
    from anthropic import Anthropic  # imported lazily so --dry-run works offline

    client = Anthropic()
    msg = client.messages.create(
        model=model,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_prompt(journal, date_str)}],
    )
    text = "".join(block.text for block in msg.content if block.type == "text")
    return extract_json(text)


def dry_run_briefing(journal: str) -> dict:
    """Cheap deterministic stub for offline testing — counts lines, picks
    the longest as the TL;DR seed. Not meant to be insightful."""
    lines = [ln.strip() for ln in journal.splitlines() if ln.strip()]
    seed = max(lines, key=len) if lines else "Empty journal."
    return {
        "tldr": (
            f"Dry-run briefing for a {len(lines)}-line journal. "
            f"Longest thought: '{seed[:80]}'."
        ),
        "metrics": [
            {"name": "Lines written", "value": str(len(lines))},
            {"name": "Words written", "value": str(len(journal.split()))},
            {"name": "Mode", "value": "dry-run (no LLM)"},
            {"name": "Primary Blocker", "value": "— (inferred)"},
        ],
        "wins": lines[:2],
        "tasks_completed": [],
        "anxieties_backlog": lines[2:5],
        "insight": (
            "This briefing was generated without the LLM; the insight engine "
            "is off. Re-run without --dry-run to get a real observation."
        ),
        "tomorrow_top_3": [
            "Set ANTHROPIC_API_KEY and re-run for a real briefing",
            "Pick the top item from the anxieties list above",
            "Block 90 minutes of deep work before email",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mind Dashboard — daily AI briefing.")
    parser.add_argument("--input", "-i", help="Path to raw journal text. Reads stdin if omitted.")
    parser.add_argument("--date", help="Override date (YYYY-MM-DD). Default: today.")
    parser.add_argument(
        "--format",
        "-f",
        choices=("markdown", "html", "both"),
        default="markdown",
    )
    parser.add_argument("--out-dir", default=".", help="Where to write the briefing.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip the LLM call and emit a deterministic stub briefing.",
    )
    args = parser.parse_args(argv)

    journal = read_input(args.input)
    if not journal.strip():
        sys.exit("error: journal input is empty")

    date_str = args.date or date_cls.today().isoformat()

    if args.dry_run:
        briefing = dry_run_briefing(journal)
    else:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            sys.exit(
                "error: ANTHROPIC_API_KEY not set. "
                "Set it or pass --dry-run for an offline stub."
            )
        briefing = call_claude(journal, date_str, args.model)

    validate(briefing)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{date_str}_Briefing"

    written: list[Path] = []
    if args.format in ("markdown", "both"):
        md_path = out_dir / f"{stem}.md"
        md_path.write_text(render_markdown(briefing, date_str), encoding="utf-8")
        written.append(md_path)
    if args.format in ("html", "both"):
        html_path = out_dir / f"{stem}.html"
        html_path.write_text(render_html(briefing, date_str), encoding="utf-8")
        written.append(html_path)

    for p in written:
        print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
