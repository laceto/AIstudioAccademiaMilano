"""Validate a Chronicle payload and render it to Markdown."""

from __future__ import annotations

import unicodedata
from typing import Any

ALLOWED_HABIT_CATEGORIES = {
    "Sleep", "Food", "Friendship", "Independence",
    "Language", "Motor", "Emotion", "Other",
}

FORBIDDEN_MARKDOWN = ("*", "_", "#", "`")

# (category, emoji, header_text)
HABIT_SECTIONS = [
    ("Sleep",        "😴", "Sleep"),
    ("Food",         "🍎", "Food"),
    ("Friendship",   "🤝", "Friendship"),
    ("Independence", "🧗", "Independence"),
    ("Language",     "🗣️", "Language"),
    ("Motor",        "🚲", "Motor"),
    ("Emotion",      "❤️", "Emotion"),
    ("Other",        "✨", "Other"),
]


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise ValueError(msg)


def _non_empty_str(d: dict, key: str, where: str) -> str:
    v = d.get(key)
    _require(isinstance(v, str) and v.strip(),
             f"{where}: missing or empty string field {key!r}")
    return v


def validate(payload: dict[str, Any]) -> None:
    for k in ("child_name", "age_years", "month_label",
              "quotes", "art_catalog", "development_tracker",
              "letter_to_future_self"):
        _require(k in payload, f"Payload missing key: {k}")

    _non_empty_str(payload, "child_name", "payload")
    _non_empty_str(payload, "month_label", "payload")

    age = payload["age_years"]
    _require(isinstance(age, int) and not isinstance(age, bool) and age > 0,
             f"age_years must be a positive integer, got {age!r}")

    quotes = payload["quotes"]
    _require(isinstance(quotes, list), "quotes must be a list")
    for i, q in enumerate(quotes):
        where = f"quotes[{i}]"
        _require(isinstance(q, dict), f"{where} must be an object")
        _non_empty_str(q, "date_label", where)
        _non_empty_str(q, "title", where)
        _non_empty_str(q, "quote", where)
        _require("context" in q and isinstance(q["context"], str),
                 f"{where}: context must be a string (may be empty)")

    art = payload["art_catalog"]
    _require(isinstance(art, list), "art_catalog must be a list")
    for i, a in enumerate(art):
        where = f"art_catalog[{i}]"
        _require(isinstance(a, dict), f"{where} must be an object")
        _non_empty_str(a, "date_label", where)
        _non_empty_str(a, "title", where)
        _non_empty_str(a, "review", where)
        _require("filename" in a and isinstance(a["filename"], str),
                 f"{where}: filename must be a string (may be empty)")

    tracker = payload["development_tracker"]
    _require(isinstance(tracker, dict), "development_tracker must be an object")
    for sub in ("milestones", "challenges", "habits"):
        _require(sub in tracker, f"development_tracker missing {sub!r}")
    for sub in ("milestones", "challenges"):
        items = tracker[sub]
        _require(isinstance(items, list),
                 f"development_tracker.{sub} must be a list")
        for j, it in enumerate(items):
            _require(isinstance(it, str) and it.strip(),
                     f"development_tracker.{sub}[{j}] must be a non-empty string")
    habits = tracker["habits"]
    _require(isinstance(habits, list), "development_tracker.habits must be a list")
    for j, h in enumerate(habits):
        where = f"development_tracker.habits[{j}]"
        _require(isinstance(h, dict), f"{where} must be an object")
        cat = h.get("category")
        _require(cat in ALLOWED_HABIT_CATEGORIES,
                 f"{where}: category must be one of "
                 f"{sorted(ALLOWED_HABIT_CATEGORIES)}, got {cat!r}")
        _non_empty_str(h, "observation", where)

    letter = payload["letter_to_future_self"]
    _require(isinstance(letter, str) and len(letter.strip()) >= 200,
             "letter_to_future_self must be at least 200 characters")
    for ch in FORBIDDEN_MARKDOWN:
        _require(ch not in letter,
                 f"letter_to_future_self must not contain Markdown character {ch!r}")


def render_chronicle_md(payload: dict[str, Any]) -> str:
    validate(payload)
    name = payload["child_name"]
    month = payload["month_label"]
    age = payload["age_years"]

    lines: list[str] = []
    lines.append(f"# The {name} Chronicles — {month}")
    lines.append("")
    lines.append(f"_Age {age}. One month of voice notes, drawings and small wonders, "
                 f"sorted into something worth keeping._")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ----- Section 1: The Quote Board -----
    lines.append(f"## 📜 1. The Quote Board — \"{name} Says\"")
    lines.append("")
    if payload["quotes"]:
        for q in payload["quotes"]:
            lines.append(f"### {q['title']} _({q['date_label']})_")
            lines.append("")
            lines.append(f"> {q['quote']}")
            if q["context"].strip():
                lines.append("")
                lines.append(f"_{q['context'].strip()}_")
            lines.append("")
    else:
        lines.append("_(no quotes captured this month)_")
        lines.append("")

    # ----- Section 2: The Art & Creation Catalog -----
    lines.append("---")
    lines.append("")
    lines.append("## 🎨 2. The Art & Creation Catalog")
    lines.append("")
    if payload["art_catalog"]:
        for a in payload["art_catalog"]:
            fname = a["filename"].strip()
            suffix = f"  \n  _file: `{fname}`_" if fname else ""
            lines.append(
                f"- **{a['date_label']} — \"{a['title']}\":** {a['review']}{suffix}"
            )
        lines.append("")
    else:
        lines.append("_(no drawings or creations captured this month)_")
        lines.append("")

    # ----- Section 3: The Development & Habit Tracker -----
    lines.append("---")
    lines.append("")
    lines.append("## 📈 3. The Development & Habit Tracker")
    lines.append("")
    tracker = payload["development_tracker"]

    lines.append("### 🏆 Milestones this month")
    lines.append("")
    if tracker["milestones"]:
        for m in tracker["milestones"]:
            lines.append(f"- {m}")
    else:
        lines.append("- _(none logged)_")
    lines.append("")

    lines.append("### ⚠️ Challenges this month")
    lines.append("")
    if tracker["challenges"]:
        for c in tracker["challenges"]:
            lines.append(f"- {c}")
    else:
        lines.append("- _(none logged)_")
    lines.append("")

    lines.append("### 🌱 Observed habits")
    lines.append("")
    lines.append("| Area | Observation |")
    lines.append("|------|-------------|")
    if tracker["habits"]:
        # Render in the canonical category order so the table is stable.
        order = {cat: i for i, (cat, _, _) in enumerate(HABIT_SECTIONS)}
        by_cat = sorted(tracker["habits"], key=lambda h: order.get(h["category"], 99))
        emoji_for = {cat: emoji for cat, emoji, _ in HABIT_SECTIONS}
        for h in by_cat:
            emoji = emoji_for.get(h["category"], "•")
            lines.append(f"| {emoji} **{h['category']}** | {h['observation']} |")
    else:
        lines.append("| — | _(no habit observations logged)_ |")
    lines.append("")

    # ----- Section 4: A Letter to Future Niccolò -----
    lines.append("---")
    lines.append("")
    lines.append(f"## ✉️ 4. A Letter to Future {name}")
    lines.append("")
    lines.append(payload["letter_to_future_self"].strip())
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"_Generated by The {name} Chronicles. "
                 f"One file per month. Bind them at 18._")
    return "\n".join(lines)


def chronicle_filename(child_name: str, age_years: int, month_label: str) -> str:
    """Produce `Niccolo_Age_5_Month_May.md` style filenames.

    Accents are ASCII-folded (Niccolò -> Niccolo) so the filename is
    portable across filesystems. `month_label` may include a year
    ("May 2026") — only the month word is used in the filename.
    """
    folded = unicodedata.normalize("NFKD", child_name).encode("ascii", "ignore").decode("ascii")
    safe_name = "".join(
        ch if (ch.isalnum() or ch in "-_") else "_"
        for ch in folded.strip()
    ).strip("_") or "Child"
    month_word = month_label.strip().split()[0]
    return f"{safe_name}_Age_{age_years}_Month_{month_word}.md"
