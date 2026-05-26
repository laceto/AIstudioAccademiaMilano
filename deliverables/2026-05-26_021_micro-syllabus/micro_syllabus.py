"""Micro-Syllabus & Flashcard Generator.

Takes an intimidating learning goal and a daily time budget, returns a
7-day action plan (syllabus.md) and a 10-card Anki-importable deck
(flashcards.csv) in a single output folder.

Usage:
    python micro_syllabus.py --goal "Understand the basics of Docker" --minutes 15
    python micro_syllabus.py -g "Master macro tracking" -m 30 --out plans/macros
    python micro_syllabus.py -g "Learn Italian medical terms" -m 20 --dry-run

Requires:
    OPENAI_API_KEY in the environment for live runs.
    Pass --dry-run to render a deterministic stub without calling the API.

Output (default path: ./<slugified-goal>/):
    syllabus.md      — 7-day roadmap, sized to the daily time budget
    flashcards.csv   — exactly 10 conceptual cards, ready for Anki import
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from prompts import SYSTEM_PROMPT, build_user_prompt
from renderers import (
    FLASHCARD_COUNT,
    SYLLABUS_DAYS,
    render_flashcards_csv,
    render_syllabus_md,
    validate,
)

DEFAULT_MODEL = "gpt-4o"


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:60] or "syllabus"


def extract_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object in model output:\n{raw[:400]}")
    return json.loads(text[start : end + 1])


def call_openai(goal: str, minutes: int, model: str) -> dict:
    from openai import OpenAI  # lazy import so --dry-run works offline

    client = OpenAI()
    resp = client.chat.completions.create(
        model=model,
        temperature=0.4,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(goal, minutes)},
        ],
    )
    text = resp.choices[0].message.content or ""
    return extract_json(text)


def dry_run_payload(goal: str, minutes: int) -> dict:
    """Deterministic stub. Not insightful — exercises the pipeline."""
    syllabus = [
        {
            "day": i,
            "title": f"Stub day {i}",
            "core_concept": (
                f"Day {i} placeholder for the goal '{goal}'. Real runs use the "
                f"OpenAI API. This text exists only so the validator passes."
            ),
            "drill": f"Spend {minutes} minutes on a placeholder exercise for day {i}.",
            "why_it_matters": f"Day {i} would build on day {i - 1 or 1} toward the macro goal.",
        }
        for i in range(1, SYLLABUS_DAYS + 1)
    ]
    flashcards = [
        {
            "front": f"Stub question {i}? (front contains a \"quote\" and a comma, on purpose)",
            "back": f"Stub answer {i}. The renderer must CSV-escape these correctly.",
        }
        for i in range(1, FLASHCARD_COUNT + 1)
    ]
    return {
        "goal": goal,
        "minutes_per_day": minutes,
        "syllabus": syllabus,
        "flashcards": flashcards,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Micro-Syllabus & Flashcard Generator.")
    parser.add_argument("--goal", "-g", required=True, help="Learning goal or habit to build.")
    parser.add_argument(
        "--minutes",
        "-m",
        type=int,
        required=True,
        help="Daily time budget in minutes.",
    )
    parser.add_argument(
        "--out",
        "-o",
        help="Output folder. Default: ./<slugified-goal>/",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"OpenAI model (default: {DEFAULT_MODEL}).")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip the LLM call and emit a deterministic stub package.",
    )
    args = parser.parse_args(argv)

    if args.minutes <= 0:
        sys.exit("error: --minutes must be a positive integer")

    if args.dry_run:
        payload = dry_run_payload(args.goal, args.minutes)
    else:
        if not os.environ.get("OPENAI_API_KEY"):
            sys.exit(
                "error: OPENAI_API_KEY not set. "
                "Set it or pass --dry-run for an offline stub."
            )
        payload = call_openai(args.goal, args.minutes, args.model)

    validate(payload)

    out_dir = Path(args.out) if args.out else Path(slugify(args.goal))
    out_dir.mkdir(parents=True, exist_ok=True)

    md_path = out_dir / "syllabus.md"
    csv_path = out_dir / "flashcards.csv"
    md_path.write_text(render_syllabus_md(payload), encoding="utf-8")
    csv_path.write_text(render_flashcards_csv(payload), encoding="utf-8")

    print(f"wrote {md_path}")
    print(f"wrote {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
