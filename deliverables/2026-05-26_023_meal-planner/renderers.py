"""Validate a Meal-Planner payload and render it to Weekly_Menu_<Season>.md."""

from __future__ import annotations

from typing import Any

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DINNER_KINDS = {"cook", "leftover", "fresh_quick"}
SEASON_TITLES = {
    "spring_summer": "Spring / Summer",
    "autumn_winter": "Autumn / Winter",
}
GROCERY_SECTIONS = [
    ("produce",        "🟢 Produce",         "Strictly seasonal fruits and vegetables"),
    ("grains_legumes", "🔵 Grains & Legumes", "Whole-grain pasta, farro, chickpeas, lentils, etc."),
    ("proteins",       "🐟 Proteins",         "Fish, white meat, eggs, fresh cheeses"),
    ("pantry_staples", "🫒 Pantry Staples",   "Olive oil, herbs, nuts, vinegar"),
]


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise ValueError(msg)


def _string_field(d: dict, key: str, where: str) -> str:
    v = d.get(key)
    _require(isinstance(v, str) and v.strip(), f"{where}: missing or empty string field {key!r}")
    return v


def validate(payload: dict[str, Any]) -> None:
    for k in ("season", "headline", "breakfast_rotation", "dinner_schedule", "grocery_list"):
        _require(k in payload, f"Payload missing key: {k}")

    season = payload["season"]
    _require(season in SEASON_TITLES, f"season must be one of {sorted(SEASON_TITLES)}, got {season!r}")
    _string_field(payload, "headline", "payload")

    # ---- breakfast rotation ----
    rot = payload["breakfast_rotation"]
    _require(isinstance(rot, list) and 2 <= len(rot) <= 3,
             f"breakfast_rotation must have 2 or 3 entries, got {len(rot) if isinstance(rot, list) else 'non-list'}")
    seen_days: set[str] = set()
    for i, item in enumerate(rot, start=1):
        where = f"breakfast_rotation[{i}]"
        _string_field(item, "name", where)
        _string_field(item, "description", where)
        days = item.get("days")
        _require(isinstance(days, list) and len(days) >= 1, f"{where}: days must be a non-empty list")
        for d in days:
            _require(d in DAYS, f"{where}: invalid day {d!r}")
            _require(d not in seen_days, f"{where}: day {d!r} already covered by another breakfast")
            seen_days.add(d)
    _require(seen_days == set(DAYS),
             f"breakfast_rotation must cover all 7 days exactly once; missing {sorted(set(DAYS) - seen_days)}")

    # ---- dinner schedule ----
    sched = payload["dinner_schedule"]
    _require(isinstance(sched, list) and len(sched) == 7,
             f"dinner_schedule must have exactly 7 entries, got {len(sched) if isinstance(sched, list) else 'non-list'}")
    for i, entry in enumerate(sched):
        where = f"dinner_schedule[{i}]"
        _require(entry.get("day") == DAYS[i], f"{where}: day must be {DAYS[i]!r}, got {entry.get('day')!r}")
        _string_field(entry, "name", where)
        _string_field(entry, "description", where)
        kind = entry.get("kind")
        _require(kind in DINNER_KINDS, f"{where}: kind must be one of {sorted(DINNER_KINDS)}, got {kind!r}")
        if kind == "cook":
            _string_field(entry, "batch_cooking_note", where)
        # pairs_with set on cook days, must be next day; otherwise null
        pw = entry.get("pairs_with")
        if kind == "cook":
            _require(i < 6, f"{where}: Sunday cannot be 'cook' (no day to roll over into)")
            _require(pw == DAYS[i + 1],
                     f"{where}: pairs_with must equal next day {DAYS[i + 1]!r}, got {pw!r}")
        else:
            _require(pw is None, f"{where}: only 'cook' days may set pairs_with")

    # rollover invariant: every cook day is followed by a leftover day with matching name
    for i in range(6):
        if sched[i]["kind"] == "cook":
            nxt = sched[i + 1]
            _require(nxt["kind"] == "leftover",
                     f"dinner_schedule[{i + 1}] must be 'leftover' (follows a cook on {DAYS[i]}), got {nxt['kind']!r}")
            _require(nxt["name"] == sched[i]["name"],
                     f"dinner_schedule[{i + 1}] leftover name must match {sched[i]['name']!r}, got {nxt['name']!r}")

    # Sunday must not start a new batch-cook
    _require(sched[6]["kind"] in {"fresh_quick", "leftover"},
             f"Sunday must be 'fresh_quick' or 'leftover', got {sched[6]['kind']!r}")

    # ---- grocery list ----
    g = payload["grocery_list"]
    _require(isinstance(g, dict), "grocery_list must be an object")
    for key, _, _ in GROCERY_SECTIONS:
        items = g.get(key)
        _require(isinstance(items, list), f"grocery_list.{key} must be a list")
        for j, it in enumerate(items):
            _require(isinstance(it, str) and it.strip(),
                     f"grocery_list.{key}[{j}] must be a non-empty string")


def render_menu_md(payload: dict[str, Any]) -> str:
    validate(payload)
    season_title = SEASON_TITLES[payload["season"]]

    # ---- header ----
    lines: list[str] = []
    lines.append(f"# Mediterranean Weekly Menu — {season_title}")
    lines.append("")
    lines.append(f"_{payload['headline'].strip()}_")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ---- Section A: 7-day matrix table ----
    lines.append("## Section A — The 7-Day Matrix")
    lines.append("")

    # build a per-day breakfast lookup
    breakfast_by_day: dict[str, str] = {}
    for item in payload["breakfast_rotation"]:
        for d in item["days"]:
            breakfast_by_day[d] = item["name"]

    lines.append("| Day | Breakfast | Dinner | Strategy |")
    lines.append("|-----|-----------|--------|----------|")
    for entry in payload["dinner_schedule"]:
        day = entry["day"]
        kind = entry["kind"]
        strategy = {
            "cook": f"🍳 Cook fresh — double portion (rolls into {entry['pairs_with']})",
            "leftover": "♻️ Leftover from yesterday",
            "fresh_quick": "⚡ Quick & fresh",
        }[kind]
        lines.append(
            f"| **{day}** | {breakfast_by_day[day]} | {entry['name']} | {strategy} |"
        )
    lines.append("")

    # ---- breakfast rotation detail ----
    lines.append("### Breakfast rotation")
    lines.append("")
    for item in payload["breakfast_rotation"]:
        days_str = ", ".join(item["days"])
        lines.append(f"- **{item['name']}** _({days_str})_ — {item['description']}")
    lines.append("")

    # ---- dinner detail with batch notes ----
    lines.append("### Dinner detail")
    lines.append("")
    for entry in payload["dinner_schedule"]:
        kind = entry["kind"]
        badge = {"cook": "🍳", "leftover": "♻️", "fresh_quick": "⚡"}[kind]
        lines.append(f"**{badge} {entry['day']} — {entry['name']}**  ")
        lines.append(f"{entry['description']}")
        if kind == "cook":
            lines.append("")
            lines.append(f"> 💡 _Batch-cook note:_ {entry['batch_cooking_note']}")
        lines.append("")

    # ---- Section B: grocery list ----
    lines.append("---")
    lines.append("")
    lines.append("## Section B — The Smart Grocery List")
    lines.append("")
    lines.append("_Organised the way the supermarket is laid out, "
                 "covering only what this week's menu needs._")
    lines.append("")

    g = payload["grocery_list"]
    for key, header, blurb in GROCERY_SECTIONS:
        items = g.get(key, [])
        lines.append(f"### {header}")
        lines.append(f"_{blurb}_")
        lines.append("")
        if items:
            for it in items:
                lines.append(f"- [ ] {it}")
        else:
            lines.append("- [ ] _(nothing needed this week)_")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("_Generated by the Mediterranean Weekly Meal Planner. "
                 "Print it, stick it to the fridge, take the list to the market._")
    return "\n".join(lines)


def menu_filename(season: str) -> str:
    title = SEASON_TITLES[season].replace(" / ", "_").replace(" ", "_")
    return f"Weekly_Menu_{title}.md"
