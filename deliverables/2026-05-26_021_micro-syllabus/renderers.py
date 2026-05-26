"""Validate a Micro-Syllabus payload and render it to syllabus.md + flashcards.csv."""

from __future__ import annotations

import csv
import io
from typing import Any

SYLLABUS_DAYS = 7
FLASHCARD_COUNT = 10
_DAY_STRING_KEYS = ("title", "core_concept", "drill", "why_it_matters")


def validate(payload: dict[str, Any]) -> None:
    for k in ("goal", "minutes_per_day", "syllabus", "flashcards"):
        if k not in payload:
            raise ValueError(f"Payload missing key: {k}")

    if not isinstance(payload["minutes_per_day"], int) or payload["minutes_per_day"] <= 0:
        raise ValueError("minutes_per_day must be a positive integer")

    syllabus = payload["syllabus"]
    if not isinstance(syllabus, list) or len(syllabus) != SYLLABUS_DAYS:
        raise ValueError(f"syllabus must have exactly {SYLLABUS_DAYS} entries, got {len(syllabus) if isinstance(syllabus, list) else 'non-list'}")
    for i, entry in enumerate(syllabus, start=1):
        if entry.get("day") != i:
            raise ValueError(f"Syllabus entry #{i} has day={entry.get('day')!r}, expected {i}")
        for k in _DAY_STRING_KEYS:
            if k not in entry or not isinstance(entry[k], str) or not entry[k].strip():
                raise ValueError(f"Day {i} missing or empty field: {k}")

    cards = payload["flashcards"]
    if not isinstance(cards, list) or len(cards) != FLASHCARD_COUNT:
        raise ValueError(f"flashcards must have exactly {FLASHCARD_COUNT} entries, got {len(cards) if isinstance(cards, list) else 'non-list'}")
    for i, card in enumerate(cards, start=1):
        for k in ("front", "back"):
            if k not in card or not isinstance(card[k], str) or not card[k].strip():
                raise ValueError(f"Flashcard #{i} missing or empty field: {k}")


def render_syllabus_md(payload: dict[str, Any]) -> str:
    validate(payload)
    days_md = []
    for entry in payload["syllabus"]:
        days_md.append(
            f"## Day {entry['day']} — {entry['title']}\n\n"
            f"### The 5-Minute Core Concept\n\n"
            f"{entry['core_concept']}\n\n"
            f"### The Drill ({payload['minutes_per_day']} min)\n\n"
            f"{entry['drill']}\n\n"
            f"### Why It Matters\n\n"
            f"{entry['why_it_matters']}\n"
        )
    return (
        f"# 7-Day Micro-Syllabus\n\n"
        f"**Goal:** {payload['goal']}  \n"
        f"**Daily time budget:** {payload['minutes_per_day']} minutes\n\n"
        f"---\n\n"
        + "\n---\n\n".join(days_md)
    )


def render_flashcards_csv(payload: dict[str, Any]) -> str:
    """Strict Anki-compatible CSV.

    - UTF-8, no BOM
    - LF line endings (Anki accepts both, but consistent for git)
    - Every field quoted, internal double-quotes doubled per RFC 4180
    - No header row — Anki defaults to no header for `.csv` import
    """
    validate(payload)
    buf = io.StringIO()
    writer = csv.writer(
        buf,
        quoting=csv.QUOTE_ALL,
        lineterminator="\n",
        quotechar='"',
        doublequote=True,
    )
    for card in payload["flashcards"]:
        writer.writerow([card["front"].strip(), card["back"].strip()])
    return buf.getvalue()
