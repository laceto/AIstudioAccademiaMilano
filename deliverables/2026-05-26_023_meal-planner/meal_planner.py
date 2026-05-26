"""Mediterranean Weekly Meal Planner.

Takes a family's favourite dishes and ingredients plus the current
season, returns a single Markdown file with a batch-cooking 7-day
breakfast/dinner matrix and a categorised grocery list.

Usage:
    python meal_planner.py \\
        --season spring_summer \\
        --dishes "Pasta alla Norma" "Baked sea bass" "Lentil soup" "Frittata" \\
        --ingredients "olive oil" chickpeas tomatoes zucchini ricotta walnuts

    python meal_planner.py --season autumn_winter --household 2 --out plans/winter --dry-run

Requires:
    OPENAI_API_KEY in the environment for live runs.
    Pass --dry-run to render a deterministic stub without calling the API.

Output (default path: ./<season>/):
    Weekly_Menu_Spring_Summer.md   (or Weekly_Menu_Autumn_Winter.md)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from prompts import ALLOWED_SEASONS, SYSTEM_PROMPT, build_user_prompt
from renderers import DAYS, menu_filename, render_menu_md, validate

DEFAULT_MODEL = "gpt-4o"


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:60] or "menu"


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


def call_openai(dishes: list[str], ingredients: list[str], season: str,
                household: int, model: str) -> dict:
    from openai import OpenAI  # lazy import so --dry-run works offline

    client = OpenAI()
    resp = client.chat.completions.create(
        model=model,
        temperature=0.4,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(
                dishes, ingredients, season, household)},
        ],
    )
    text = resp.choices[0].message.content or ""
    return extract_json(text)


def dry_run_payload(season: str) -> dict:
    """Deterministic, schema-valid stub. Not a real menu — just exercises
    the validator/renderer pipeline without needing an API key."""
    is_summer = season == "spring_summer"

    breakfast_rotation = [
        {
            "name": ("Greek yoghurt with strawberries, walnuts and honey"
                     if is_summer else
                     "Oatmeal with stewed apple, walnuts and cinnamon"),
            "days": ["Monday", "Tuesday", "Wednesday"],
            "description": ("Plain Greek yoghurt topped with sliced strawberries, "
                            "a handful of walnuts and a drizzle of honey."
                            if is_summer else
                            "Steel-cut oats simmered with milk, finished with stewed "
                            "apple, walnuts and a dusting of cinnamon."),
        },
        {
            "name": "Whole-grain toast with ricotta, olive oil and tomato",
            "days": ["Thursday", "Friday"],
            "description": ("A thick slice of whole-grain bread, fresh ricotta, "
                            "good olive oil and ripe tomato slices, finished with "
                            "salt and oregano."),
        },
        {
            "name": ("Spanish-style tomato bread with soft-boiled egg"
                     if is_summer else
                     "Polenta with poached egg and sautéed greens"),
            "days": ["Saturday", "Sunday"],
            "description": ("Toasted sourdough rubbed with garlic and ripe tomato, "
                            "topped with a 6-minute egg and flaky salt."
                            if is_summer else
                            "Creamy polenta topped with sautéed cavolo nero, "
                            "a poached egg and a glug of olive oil."),
        },
    ]

    if is_summer:
        cook_a = "Pasta alla Norma (eggplant + tomato + ricotta salata)"
        cook_a_note = ("Make a double batch of the eggplant-tomato sauce; keep half "
                       "in a sealed jar. On Tuesday, boil fresh pasta and reheat the "
                       "sauce — 12 minutes start to finish.")
        cook_b = "Baked sea bass with cherry tomatoes, zucchini and capers"
        cook_b_note = ("Bake two whole sea bass at once with extra vegetables. "
                       "Thursday: flake the second fish into a warm zucchini-and-"
                       "white-bean salad — eat cold or barely warm.")
        cook_c = "Chickpea, tomato and spinach stew"
        cook_c_note = ("Cook a deep pot; portion half into the fridge in glass. "
                       "Saturday: reheat, stir in a spoon of pesto and serve with "
                       "grilled bread.")
        sunday = "Zucchini, ricotta and herb frittata with a tomato salad"
        sunday_desc = "A frittata uses up the last of the week's eggs, ricotta and zucchini. Tomato salad on the side."
    else:
        cook_a = "Lentil and farro soup with rosemary"
        cook_a_note = ("Cook a double pot of lentil-farro soup. Tuesday: reheat — "
                       "it actually tastes better on day two. Finish each bowl with "
                       "raw olive oil and grated pecorino.")
        cook_b = "Baked cod with potatoes, olives and cherry tomatoes"
        cook_b_note = ("Bake two trays at once. Thursday: flake the second portion "
                       "into a warm potato salad with capers and parsley.")
        cook_c = "Pumpkin and chickpea stew with cavolo nero"
        cook_c_note = ("Cook a deep pot. Saturday: reheat with a spoon of harissa "
                       "and serve over couscous.")
        sunday = "Mushroom and herb frittata with bitter-leaf salad"
        sunday_desc = "A frittata clears the last of the week's eggs, mushrooms and cheese. Radicchio or chicory salad alongside."

    dinner_schedule = [
        {"day": "Monday",    "name": cook_a, "kind": "cook",        "pairs_with": "Tuesday",
         "description": "Cooked fresh tonight, eaten again tomorrow.",
         "batch_cooking_note": cook_a_note},
        {"day": "Tuesday",   "name": cook_a, "kind": "leftover",    "pairs_with": None,
         "description": "Reheat last night's batch. Eat with a green salad.",
         "batch_cooking_note": ""},
        {"day": "Wednesday", "name": cook_b, "kind": "cook",        "pairs_with": "Thursday",
         "description": "Cooked fresh; second portion repurposed tomorrow.",
         "batch_cooking_note": cook_b_note},
        {"day": "Thursday",  "name": cook_b, "kind": "leftover",    "pairs_with": None,
         "description": "Yesterday's protein, served in a new form (cold/warm salad).",
         "batch_cooking_note": ""},
        {"day": "Friday",    "name": cook_c, "kind": "cook",        "pairs_with": "Saturday",
         "description": "A deep pot of legumes — comforting and cheap.",
         "batch_cooking_note": cook_c_note},
        {"day": "Saturday",  "name": cook_c, "kind": "leftover",    "pairs_with": None,
         "description": "Friday's stew, even better today.",
         "batch_cooking_note": ""},
        {"day": "Sunday",    "name": sunday, "kind": "fresh_quick", "pairs_with": None,
         "description": sunday_desc, "batch_cooking_note": ""},
    ]

    if is_summer:
        grocery = {
            "produce": [
                "1.2 kg eggplants",
                "1 kg cherry tomatoes",
                "600 g zucchini",
                "300 g baby spinach",
                "2 lemons",
                "1 bunch basil",
                "1 bunch flat-leaf parsley",
                "1 head garlic",
                "2 red onions",
                "500 g strawberries",
                "4 medium tomatoes (for bread/salad)",
                "1 small head lettuce (for green salad)",
            ],
            "grains_legumes": [
                "500 g whole-grain penne or rigatoni",
                "1 loaf whole-grain sourdough",
                "400 g dried chickpeas (or 2 x 400 g jars)",
                "200 g cannellini beans (1 jar)",
            ],
            "proteins": [
                "2 whole sea bass (≈ 500 g each), cleaned",
                "8 eggs",
                "250 g fresh ricotta",
                "80 g ricotta salata (for grating)",
                "200 g plain Greek yoghurt",
            ],
            "pantry_staples": [
                "Extra-virgin olive oil (top up if low)",
                "Capers in salt (small jar)",
                "Dried oregano",
                "Sea salt flakes",
                "Honey (small jar)",
                "100 g walnuts",
                "Pesto alla genovese (1 small jar)",
            ],
        }
    else:
        grocery = {
            "produce": [
                "1 small pumpkin (≈ 1.2 kg)",
                "300 g cavolo nero",
                "500 g floury potatoes",
                "400 g cherry tomatoes",
                "200 g chestnut mushrooms",
                "2 apples",
                "2 lemons",
                "1 head radicchio (or chicory)",
                "1 bunch rosemary",
                "1 bunch flat-leaf parsley",
                "1 head garlic",
                "2 red onions",
            ],
            "grains_legumes": [
                "300 g farro",
                "300 g brown lentils",
                "400 g dried chickpeas (or 2 x 400 g jars)",
                "200 g couscous",
                "1 small loaf whole-grain sourdough",
            ],
            "proteins": [
                "2 fillets of cod (≈ 250 g each)",
                "8 eggs",
                "200 g plain Greek yoghurt",
                "60 g pecorino romano (for grating)",
            ],
            "pantry_staples": [
                "Extra-virgin olive oil (top up if low)",
                "Black olives (Taggiasche), 1 small jar",
                "Capers in salt (small jar)",
                "Harissa paste (1 small jar)",
                "Dried oregano",
                "Cinnamon",
                "100 g walnuts",
            ],
        }

    return {
        "season": season,
        "headline": ("Three cook-once-eat-twice dinners, a quick Sunday frittata, "
                     "and three rotating breakfasts."),
        "breakfast_rotation": breakfast_rotation,
        "dinner_schedule": dinner_schedule,
        "grocery_list": grocery,
    }


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mediterranean Weekly Meal Planner.")
    parser.add_argument(
        "--season",
        required=True,
        choices=list(ALLOWED_SEASONS),
        help="spring_summer or autumn_winter (decides what's in season).",
    )
    parser.add_argument(
        "--dishes",
        nargs="*",
        default=[],
        help="Family-favourite dishes, space-separated, quote multi-word items.",
    )
    parser.add_argument(
        "--ingredients",
        nargs="*",
        default=[],
        help="Family-favourite ingredients to lean on.",
    )
    parser.add_argument(
        "--household",
        type=int,
        default=4,
        help="Number of people the menu must feed (affects grocery quantities). Default 4.",
    )
    parser.add_argument("--out", "-o", help="Output folder. Default: ./<season>/")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"OpenAI model (default: {DEFAULT_MODEL}).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip the LLM call and render a deterministic stub.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.household <= 0:
        sys.exit("error: --household must be a positive integer")

    if args.dry_run:
        payload = dry_run_payload(args.season)
    else:
        if not os.environ.get("OPENAI_API_KEY"):
            sys.exit(
                "error: OPENAI_API_KEY not set. "
                "Set it or pass --dry-run for an offline stub."
            )
        payload = call_openai(args.dishes, args.ingredients, args.season,
                              args.household, args.model)

    validate(payload)

    out_dir = Path(args.out) if args.out else Path(args.season)
    out_dir.mkdir(parents=True, exist_ok=True)

    md_path = out_dir / menu_filename(args.season)
    md_path.write_text(render_menu_md(payload), encoding="utf-8")
    print(f"wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
