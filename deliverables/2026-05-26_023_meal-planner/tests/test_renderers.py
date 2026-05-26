"""Tests for the meal-planner validator and renderer."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

# Make the deliverable importable when running pytest from anywhere.
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from meal_planner import dry_run_payload  # noqa: E402
from renderers import menu_filename, render_menu_md, validate  # noqa: E402


# ----- happy path -----

def test_dry_run_payload_summer_validates():
    validate(dry_run_payload("spring_summer"))


def test_dry_run_payload_winter_validates():
    validate(dry_run_payload("autumn_winter"))


def test_render_includes_table_and_grocery_sections():
    md = render_menu_md(dry_run_payload("spring_summer"))
    assert "## Section A — The 7-Day Matrix" in md
    assert "## Section B — The Smart Grocery List" in md
    assert "🟢 Produce" in md
    assert "🔵 Grains & Legumes" in md
    assert "🐟 Proteins" in md
    assert "🫒 Pantry Staples" in md
    # All 7 days appear as row labels
    for day in ["Monday", "Tuesday", "Wednesday", "Thursday",
                "Friday", "Saturday", "Sunday"]:
        assert f"**{day}**" in md


def test_render_marks_cook_days_with_pair_target():
    md = render_menu_md(dry_run_payload("autumn_winter"))
    # Monday is cook, pairs with Tuesday
    assert "Cook fresh — double portion (rolls into Tuesday)" in md


def test_menu_filename():
    assert menu_filename("spring_summer") == "Weekly_Menu_Spring_Summer.md"
    assert menu_filename("autumn_winter") == "Weekly_Menu_Autumn_Winter.md"


# ----- validator negative cases -----

def test_rejects_wrong_dinner_count():
    p = dry_run_payload("spring_summer")
    p["dinner_schedule"] = p["dinner_schedule"][:6]
    with pytest.raises(ValueError, match="exactly 7 entries"):
        validate(p)


def test_rejects_dinner_out_of_order():
    p = dry_run_payload("spring_summer")
    p["dinner_schedule"][0], p["dinner_schedule"][1] = p["dinner_schedule"][1], p["dinner_schedule"][0]
    with pytest.raises(ValueError, match="day must be 'Monday'"):
        validate(p)


def test_rejects_cook_not_followed_by_leftover():
    p = dry_run_payload("spring_summer")
    # Force Tuesday to NOT be a leftover
    p["dinner_schedule"][1] = {
        "day": "Tuesday",
        "name": "Different dish",
        "kind": "fresh_quick",
        "pairs_with": None,
        "description": "Wrong rollover.",
        "batch_cooking_note": "",
    }
    with pytest.raises(ValueError, match="must be 'leftover'"):
        validate(p)


def test_rejects_cook_on_sunday():
    p = dry_run_payload("spring_summer")
    p["dinner_schedule"][6] = {
        "day": "Sunday",
        "name": "Big Sunday cook",
        "kind": "cook",
        "pairs_with": "Monday",
        "description": "Bad — no rollover target.",
        "batch_cooking_note": "won't work",
    }
    with pytest.raises(ValueError, match="Sunday cannot be 'cook'"):
        validate(p)


def test_rejects_breakfast_day_coverage_gap():
    p = dry_run_payload("spring_summer")
    # Remove Sunday from the third rotation entry
    p["breakfast_rotation"][2]["days"] = ["Saturday"]
    with pytest.raises(ValueError, match="cover all 7 days"):
        validate(p)


def test_rejects_breakfast_day_overlap():
    p = dry_run_payload("spring_summer")
    # Duplicate Monday into the second rotation entry
    p["breakfast_rotation"][1]["days"].insert(0, "Monday")
    with pytest.raises(ValueError, match="already covered"):
        validate(p)


def test_rejects_too_many_breakfast_rotations():
    p = dry_run_payload("spring_summer")
    p["breakfast_rotation"].append({
        "name": "Fourth option",
        "days": ["Monday"],
        "description": "too many",
    })
    with pytest.raises(ValueError, match="2 or 3 entries"):
        validate(p)


def test_rejects_invalid_season():
    p = dry_run_payload("spring_summer")
    p["season"] = "winter"
    with pytest.raises(ValueError, match="season must be one of"):
        validate(p)


def test_rejects_missing_batch_note_on_cook():
    p = dry_run_payload("spring_summer")
    p["dinner_schedule"][0]["batch_cooking_note"] = ""
    with pytest.raises(ValueError, match="batch_cooking_note"):
        validate(p)


def test_rejects_pairs_with_on_leftover():
    p = dry_run_payload("spring_summer")
    p["dinner_schedule"][1]["pairs_with"] = "Wednesday"
    with pytest.raises(ValueError, match="only 'cook' days may set pairs_with"):
        validate(p)


def test_rejects_wrong_pairs_with():
    p = dry_run_payload("spring_summer")
    p["dinner_schedule"][0]["pairs_with"] = "Friday"
    with pytest.raises(ValueError, match="pairs_with must equal next day"):
        validate(p)


def test_rejects_empty_grocery_item():
    p = dry_run_payload("spring_summer")
    p["grocery_list"]["produce"].append("")
    with pytest.raises(ValueError, match="produce\\[\\d+\\]"):
        validate(p)
