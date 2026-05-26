"""The Niccolò Chronicles — turn a month of WhatsApp time-capsule chat
into one beautifully structured Markdown file.

Usage:

    # From a native WhatsApp .txt export
    python chronicles.py \\
        --chat sample/may-2026-niccolo/raw_export.txt \\
        --name Niccolò \\
        --age 5 \\
        --month 2026-05 \\
        --out output/

    # From a CSV converter
    python chronicles.py --chat export.csv --name Niccolò --age 5 --month 2026-05

    # Offline, deterministic stub (no API key required)
    python chronicles.py --dry-run --name Niccolò --age 5 --month 2026-05

Requires:
    OPENAI_API_KEY in the environment for live runs.
    Pass --dry-run to render a deterministic stub without calling the API.

Output (default folder = ./<name>_<month>/):
    Niccolo_Age_5_Month_May.md
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

from parsers import ChatEntry, filter_month, parse_chat
from prompts import SYSTEM_PROMPT, build_user_prompt
from renderers import chronicle_filename, render_chronicle_md, validate

DEFAULT_MODEL = "gpt-4o"

MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


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


def call_openai(child_name: str, age_years: int, month_label: str,
                entries: list[ChatEntry], model: str) -> dict:
    from openai import OpenAI  # lazy import so --dry-run works offline

    client = OpenAI()
    resp = client.chat.completions.create(
        model=model,
        temperature=0.5,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(
                child_name, age_years, month_label,
                [e.to_dict() for e in entries])},
        ],
    )
    text = resp.choices[0].message.content or ""
    return extract_json(text)


def dry_run_payload(child_name: str, age_years: int, month_label: str) -> dict:
    """Deterministic, schema-valid stub. Produces a real-shaped chronicle
    so the renderer can be exercised without an API key."""
    return {
        "child_name": child_name,
        "age_years": age_years,
        "month_label": month_label,
        "quotes": [
            {
                "date_label": "May 4",
                "title": "Why Pasta Is Round",
                "quote": "Pasta is round so the sauce can hold hands all the way around it.",
                "context": "At dinner, looking very seriously into the bowl.",
            },
            {
                "date_label": "May 12",
                "title": "Dinosaurs and Friends",
                "quote": "Papa, if a T-rex met a triceratops in the playground, would they say hi or would they fight?",
                "context": "",
            },
            {
                "date_label": "May 19",
                "title": "Where Songs Live",
                "quote": "Songs live inside the radio, but at night they sleep in the speakers.",
                "context": "Whispered while pointing at the kitchen radio.",
            },
            {
                "date_label": "May 26",
                "title": "The Moon's Bedtime",
                "quote": "Papa, does the moon go to sleep because it looks tired today?",
                "context": "Looking out of the window on a cloudy afternoon.",
            },
        ],
        "art_catalog": [
            {
                "date_label": "May 6",
                "title": "A Family of Suns",
                "filename": "IMG-20260506-WA0001.jpg",
                "review": "A wax-crayon drawing with three smiling suns of different sizes — likely a family portrait by analogy. Notable for the deliberate use of warm colours only (red, orange, yellow) and the first appearance of eyelashes on the faces.",
            },
            {
                "date_label": "May 12",
                "title": "The Giant Dinosaur",
                "filename": "IMG-20260512-WA0001.jpg",
                "review": "A marker drawing featuring a large green theropod with rows of sharp teeth. Notable for his developing fine-motor grip and his new interest in textural detail — every tooth is individually drawn.",
            },
            {
                "date_label": "May 18",
                "title": "Lego Spaceship Alpha",
                "filename": "IMG-20260518-WA0001.jpg",
                "review": "A symmetric lego build with two engine pods, a cockpit and a tail fin. Notable for the first appearance of bilateral symmetry — both wings have the same number of bricks in the same colours.",
            },
            {
                "date_label": "May 23",
                "title": "Underwater City",
                "filename": "IMG-20260523-WA0001.jpg",
                "review": "A multi-medium collage (marker + sticker) showing fish, a submarine and a house at the bottom of the sea. Notable for the introduction of a baseline ground and a horizon — a leap in spatial reasoning.",
            },
        ],
        "development_tracker": {
            "milestones": [
                "Rode bike without training wheels for the first time (May 9).",
                "Read his own name written on a birthday card without prompting (May 14).",
                "Slept in his own bed all week, no night visits (May 20-26).",
                "First time tying his shoes without help (May 24).",
            ],
            "challenges": [
                "Tantrum about wearing green socks instead of blue ones (May 7).",
                "Refused dinner three nights in a row over a tomato-on-pasta debate (May 13-15).",
                "Hard goodbye at preschool drop-off after a long weekend (May 18).",
            ],
            "habits": [
                {"category": "Sleep",
                 "observation": "Falling asleep within 15 minutes after the second bedtime story; no more requests for water at 22:00."},
                {"category": "Food",
                 "observation": "Now eats broccoli if it's 'cut into little trees' and described as forest food."},
                {"category": "Friendship",
                 "observation": "Mentions Marco from preschool by name every day this week; first sign of a real best-friend bond."},
                {"category": "Independence",
                 "observation": "Insists on choosing his own clothes in the morning, even when the outcome is striped trousers with polka-dot t-shirt."},
                {"category": "Language",
                 "observation": "Started using because-sentences correctly: 'I'm hungry because we walked for hours.'"},
                {"category": "Motor",
                 "observation": "Bike balance clicked mid-month; by the end of May he can pedal for 50m without stopping."},
                {"category": "Emotion",
                 "observation": "Names his own feelings now ('I'm frustrated, not angry') after the storybook we read about emotions."},
            ],
        },
        "letter_to_future_self": (
            f"Dear {child_name}, this is the month the world started to feel solid under your feet. "
            f"You learned to balance on the bike — and you learned that the moon, when it looks "
            f"tired, must also need its sleep. You asked the kind of questions only a five-year-old "
            f"can ask, the ones that stop a parent in the middle of cooking and make them write things "
            f"down on a phone so they don't disappear. There were green-sock tantrums and tomato wars "
            f"and one very hard Monday morning at preschool, but mostly there were small, ordinary "
            f"victories you didn't notice and we will never forget. We love who you are turning into. "
            f"We hope the version of you reading this remembers how brave it felt to let go of the "
            f"training wheels, even just for ten seconds, before the world caught you again."
        ),
    }


def parse_month(raw: str) -> tuple[int, int, str]:
    """Accept '2026-05' or '2026-5'. Return (year, month, 'May 2026')."""
    m = re.match(r"^(\d{4})-(\d{1,2})$", raw)
    if not m:
        raise ValueError(f"--month must be 'YYYY-MM', got {raw!r}")
    y, mm = int(m.group(1)), int(m.group(2))
    if not 1 <= mm <= 12:
        raise ValueError(f"month part must be 1..12, got {mm}")
    return y, mm, f"{MONTH_NAMES[mm]} {y}"


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--chat",
                        help="Path to WhatsApp export (.txt) or CSV.")
    parser.add_argument("--name", default="Niccolò",
                        help="The child's name (default: Niccolò).")
    parser.add_argument("--age", type=int, required=True,
                        help="The child's age in years (e.g. 5).")
    parser.add_argument("--month", required=True,
                        help="Target month in 'YYYY-MM' form (e.g. 2026-05).")
    parser.add_argument("--out", "-o",
                        help="Output folder. Default: ./<name>_<month>/")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"OpenAI model (default: {DEFAULT_MODEL}).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip the LLM call and render a deterministic stub.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.age <= 0:
        sys.exit("error: --age must be a positive integer")

    try:
        year, month, month_label = parse_month(args.month)
    except ValueError as exc:
        sys.exit(f"error: {exc}")

    if args.dry_run:
        payload = dry_run_payload(args.name, args.age, month_label)
    else:
        if not args.chat:
            sys.exit("error: --chat is required for live runs (or pass --dry-run).")
        if not os.environ.get("OPENAI_API_KEY"):
            sys.exit("error: OPENAI_API_KEY not set. "
                     "Set it or pass --dry-run for an offline stub.")
        all_entries = parse_chat(args.chat)
        entries = filter_month(all_entries, year, month)
        if not entries:
            sys.exit(f"error: no messages found in {month_label} inside {args.chat}")
        payload = call_openai(args.name, args.age, month_label,
                              entries, args.model)

    validate(payload)

    if args.out:
        out_dir = Path(args.out)
    else:
        safe = re.sub(r"[^A-Za-z0-9_-]+", "_", args.name).strip("_") or "Child"
        out_dir = Path(f"{safe}_{args.month}")
    out_dir.mkdir(parents=True, exist_ok=True)

    md_path = out_dir / chronicle_filename(args.name, args.age, month_label)
    md_path.write_text(render_chronicle_md(payload), encoding="utf-8")
    print(f"wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
