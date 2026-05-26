"""Prompt builder for the Mediterranean Weekly Meal Planner.

A single OpenAI call returns one JSON object containing the 7-day
breakfast/dinner matrix and a categorised grocery list. The renderer
owns the Markdown layout — the LLM never produces Markdown directly.
"""

from __future__ import annotations

ALLOWED_SEASONS = ("spring_summer", "autumn_winter")

SYSTEM_PROMPT = """You are the Mediterranean Family Meal Planner.

You receive a family's favourite dishes and ingredients, the current
season, and a strict "rollover rule": the family is happy to eat the
same dinner two days in a row, and the same breakfast for 2-3 days in
a row, in order to save cooking time and reduce food waste.

You MUST respond with a single JSON object — no prose, no code fences.
It MUST conform exactly to this schema:

{
  "season": "spring_summer" | "autumn_winter",
  "headline": "string — one short line describing the week's strategy (max 110 chars)",
  "breakfast_rotation": [
    { "name": "string", "days": ["Monday", "Tuesday", ...], "description": "string — 1 sentence, ingredients evident" },
    ... 2 or 3 entries total ...
  ],
  "dinner_schedule": [
    {
      "day": "Monday",
      "name": "string — dish name",
      "kind": "cook" | "leftover" | "fresh_quick",
      "pairs_with": "Tuesday" | null,
      "description": "string — 1-2 sentences",
      "batch_cooking_note": "string — only if kind=='cook', explain how to make a double portion that holds for tomorrow; otherwise empty string"
    },
    ... exactly 7 entries, in order Monday..Sunday ...
  ],
  "grocery_list": {
    "produce":         [ "string — quantity + item, e.g. '500g cherry tomatoes'" ],
    "grains_legumes":  [ "string" ],
    "proteins":        [ "string" ],
    "pantry_staples":  [ "string" ]
  }
}

HARD RULES (the renderer rejects payloads that break any of these):

1. dinner_schedule MUST have exactly 7 entries, ordered Monday through Sunday.
2. The week MUST use the rollover pattern: every "cook" day MUST be
   immediately followed by a "leftover" day whose `name` matches the
   "cook" day's `name` and whose `pairs_with` is null. Each "cook" day
   sets `pairs_with` to the next day's name.
3. Sunday MUST be either kind=="fresh_quick" (a fast meal like frittata,
   panzanella, grilled fish + salad) OR a leftover. Never start a new
   batch-cook on Sunday.
4. breakfast_rotation MUST have 2 or 3 entries. The `days` arrays MUST
   together cover Monday..Sunday exactly once each, in contiguous blocks
   (e.g. Mon-Tue, Wed-Thu-Fri, Sat-Sun). No day appears in two entries.
5. Every dinner and every breakfast MUST be Mediterranean-aligned:
   plenty of vegetables and legumes, healthy fats (olive oil, nuts),
   fish or white meat or fresh cheese over red meat. Red meat appears
   at most ONCE in the week (preferably zero). Processed meats: never.
6. Ingredients MUST be seasonal for the given season. Strawberries,
   zucchini blossoms, fresh peas, tomatoes, stone fruit → spring_summer.
   Pumpkin, cavolo nero, chestnuts, citrus, mushrooms, root veg →
   autumn_winter. Year-round basics (onion, garlic, olive oil, eggs)
   are fine in both.
7. The grocery_list MUST cover EVERY ingredient implied by the menu
   and NOTHING ELSE. Aggregate quantities across dishes (e.g. if two
   dinners use chickpeas, list one line with the total). Include
   quantities in metric units. Pantry staples include only items
   actually needed for this week's menu — do not list every condiment
   in existence.
8. Use the user's favourites whenever they fit the season and the
   Mediterranean rules. Do not invent dishes the user didn't hint at
   unless their list is too narrow to fill the week — in which case,
   stay in the same culinary register (Italian/Greek/Levantine).
9. No emojis inside JSON values. No Markdown formatting (no **bold**,
   no backticks). The renderer adds emojis to the grocery section
   headers and formats the matrix as a table.
"""


def build_user_prompt(favourites_dishes: list[str],
                      favourites_ingredients: list[str],
                      season: str,
                      household_size: int) -> str:
    if season not in ALLOWED_SEASONS:
        raise ValueError(f"season must be one of {ALLOWED_SEASONS}, got {season!r}")

    dishes_block = "\n".join(f"  - {d}" for d in favourites_dishes) or "  (none provided — improvise within the Mediterranean tradition)"
    ingr_block = "\n".join(f"  - {i}" for i in favourites_ingredients) or "  (none provided)"

    return (
        f"SEASON: {season}\n"
        f"HOUSEHOLD SIZE: {household_size} people\n"
        f"FAMILY-FAVOURITE DISHES:\n{dishes_block}\n\n"
        f"FAMILY-FAVOURITE INGREDIENTS:\n{ingr_block}\n\n"
        f"ROLLOVER RULE: ENABLED — every dinner that is cooked fresh "
        f"must be made in double portion and served again the next day. "
        f"Breakfasts rotate across only 2 or 3 distinct options for the "
        f"whole week, in contiguous blocks of days.\n\n"
        f"Return the JSON object now."
    )
