"""Tests for The Niccolò Chronicles parser, validator and renderer."""

from __future__ import annotations

import copy
import sys
from datetime import date
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from chronicles import dry_run_payload, parse_month  # noqa: E402
from parsers import (  # noqa: E402
    ChatEntry, filter_month, parse_csv, parse_whatsapp_txt,
)
from renderers import (  # noqa: E402
    chronicle_filename, render_chronicle_md, validate,
)


# ============================================================
# Renderer / validator — happy path
# ============================================================

def test_dry_run_payload_validates():
    validate(dry_run_payload("Niccolò", 5, "May 2026"))


def test_render_includes_all_four_sections():
    md = render_chronicle_md(dry_run_payload("Niccolò", 5, "May 2026"))
    assert '📜 1. The Quote Board — "Niccolò Says"' in md
    assert "🎨 2. The Art & Creation Catalog" in md
    assert "📈 3. The Development & Habit Tracker" in md
    assert "✉️ 4. A Letter to Future Niccolò" in md


def test_render_preserves_quote_verbatim():
    md = render_chronicle_md(dry_run_payload("Niccolò", 5, "May 2026"))
    assert "does the moon go to sleep because it looks tired today?" in md


def test_render_includes_habit_table_with_categories():
    md = render_chronicle_md(dry_run_payload("Niccolò", 5, "May 2026"))
    assert "| Area | Observation |" in md
    assert "**Sleep**" in md
    assert "**Motor**" in md


def test_chronicle_filename_ascii_folded():
    # The accented name folds to ASCII so the filename is portable.
    assert chronicle_filename("Niccolò", 5, "May 2026") == "Niccolo_Age_5_Month_May.md"


def test_chronicle_filename_plain_ascii():
    assert chronicle_filename("Anna", 3, "December 2026") == "Anna_Age_3_Month_December.md"


def test_chronicle_filename_strips_year():
    # only the month word, never the year, appears in the filename
    assert chronicle_filename("Anna", 3, "May 2026").endswith("Month_May.md")


# ============================================================
# Validator — negative cases
# ============================================================

def test_rejects_missing_letter():
    p = dry_run_payload("Niccolò", 5, "May 2026")
    del p["letter_to_future_self"]
    with pytest.raises(ValueError, match="Payload missing key: letter_to_future_self"):
        validate(p)


def test_rejects_short_letter():
    p = dry_run_payload("Niccolò", 5, "May 2026")
    p["letter_to_future_self"] = "Too short."
    with pytest.raises(ValueError, match="at least 200 characters"):
        validate(p)


def test_rejects_markdown_in_letter():
    p = dry_run_payload("Niccolò", 5, "May 2026")
    p["letter_to_future_self"] = (
        "Dear Niccolò, this is **bold** and should be rejected. "
        + "Padding " * 40
    )
    with pytest.raises(ValueError, match="Markdown character"):
        validate(p)


def test_rejects_zero_age():
    p = dry_run_payload("Niccolò", 5, "May 2026")
    p["age_years"] = 0
    with pytest.raises(ValueError, match="age_years must be a positive integer"):
        validate(p)


def test_rejects_bool_as_age():
    p = dry_run_payload("Niccolò", 5, "May 2026")
    p["age_years"] = True  # subtle: True is int in Python
    with pytest.raises(ValueError, match="age_years must be a positive integer"):
        validate(p)


def test_rejects_empty_quote_text():
    p = dry_run_payload("Niccolò", 5, "May 2026")
    p["quotes"][0]["quote"] = ""
    with pytest.raises(ValueError, match=r"quotes\[0\]: missing or empty string field 'quote'"):
        validate(p)


def test_rejects_quote_missing_context_key():
    p = dry_run_payload("Niccolò", 5, "May 2026")
    del p["quotes"][0]["context"]
    with pytest.raises(ValueError, match=r"quotes\[0\]: context must be a string"):
        validate(p)


def test_rejects_invalid_habit_category():
    p = dry_run_payload("Niccolò", 5, "May 2026")
    p["development_tracker"]["habits"][0]["category"] = "Vibes"
    with pytest.raises(ValueError, match="category must be one of"):
        validate(p)


def test_rejects_art_with_empty_review():
    p = dry_run_payload("Niccolò", 5, "May 2026")
    p["art_catalog"][0]["review"] = ""
    with pytest.raises(ValueError, match=r"art_catalog\[0\]: missing or empty string field 'review'"):
        validate(p)


def test_rejects_milestone_empty_string():
    p = dry_run_payload("Niccolò", 5, "May 2026")
    p["development_tracker"]["milestones"].append("")
    with pytest.raises(ValueError, match=r"milestones\[\d+\] must be a non-empty string"):
        validate(p)


def test_rejects_tracker_missing_subkey():
    p = dry_run_payload("Niccolò", 5, "May 2026")
    del p["development_tracker"]["habits"]
    with pytest.raises(ValueError, match="development_tracker missing 'habits'"):
        validate(p)


# ============================================================
# Parser — WhatsApp txt
# ============================================================

SAMPLE_WHATSAPP_TXT = """\
[12/05/26, 14:32:15] Luigi: Niccolò just asked if the moon goes to sleep because it looks tired today.
[12/05/26, 14:33:00] Luigi: IMG-20260512-WA0001.jpg (file attached)
The Giant Dinosaur
[12/05/26, 18:22:51] Luigi: Rode bike without training wheels
[13/05/26, 09:15:00] Luigi: PTT-20260513-WA0001.opus (file attached)
[13/05/26, 09:16:00] Luigi: He asked why birds don't fall when they sleep on branches.
"""


def test_parse_whatsapp_txt_basic_count():
    entries = parse_whatsapp_txt(SAMPLE_WHATSAPP_TXT)
    assert len(entries) == 5


def test_parse_whatsapp_txt_dates_normalised():
    entries = parse_whatsapp_txt(SAMPLE_WHATSAPP_TXT)
    assert entries[0].date == date(2026, 5, 12)
    assert entries[3].date == date(2026, 5, 13)


def test_parse_whatsapp_txt_attachment_extracted():
    entries = parse_whatsapp_txt(SAMPLE_WHATSAPP_TXT)
    photo = entries[1]
    assert photo.attachment == "IMG-20260512-WA0001.jpg"
    assert photo.kind == "image"
    # The caption ("The Giant Dinosaur") should be joined to the message text.
    assert "Giant Dinosaur" in photo.text
    # The "(file attached)" boilerplate should be stripped.
    assert "(file attached)" not in photo.text


def test_parse_whatsapp_txt_voice_kind():
    entries = parse_whatsapp_txt(SAMPLE_WHATSAPP_TXT)
    voice = entries[3]
    assert voice.attachment == "PTT-20260513-WA0001.opus"
    assert voice.kind == "voice"


def test_parse_whatsapp_txt_plain_format_with_dash():
    txt = "12/05/26, 14:32 - Luigi: short milestone message\n"
    entries = parse_whatsapp_txt(txt)
    assert len(entries) == 1
    assert entries[0].date == date(2026, 5, 12)
    assert entries[0].text == "short milestone message"


def test_parse_whatsapp_txt_two_digit_year_normalisation():
    txt = "[01/01/99, 09:00:00] Luigi: vintage message\n"
    entries = parse_whatsapp_txt(txt)
    assert entries[0].date == date(1999, 1, 1)


def test_filter_month_excludes_other_months():
    entries = parse_whatsapp_txt(
        SAMPLE_WHATSAPP_TXT
        + "[03/06/26, 10:00:00] Luigi: this is June, not May\n"
    )
    may_only = filter_month(entries, 2026, 5)
    assert len(may_only) == 5
    assert all(e.date.month == 5 for e in may_only)


# ============================================================
# Parser — CSV
# ============================================================

SAMPLE_CSV = (
    "date,time,author,message,attachment\n"
    "2026-05-12,14:32,Luigi,Niccolò asked about the moon,\n"
    "2026-05-12,14:33,Luigi,The Giant Dinosaur,IMG-20260512-WA0001.jpg\n"
    "12/05/26,18:22,Luigi,Rode bike without training wheels,\n"
)


def test_parse_csv_basic():
    entries = parse_csv(SAMPLE_CSV)
    assert len(entries) == 3
    assert entries[1].attachment == "IMG-20260512-WA0001.jpg"
    assert entries[1].kind == "image"
    # mixed date formats both resolve to the same day
    assert entries[0].date == entries[2].date == date(2026, 5, 12)


# ============================================================
# CLI helper — month parser
# ============================================================

def test_parse_month_iso():
    y, m, label = parse_month("2026-05")
    assert (y, m, label) == (2026, 5, "May 2026")


def test_parse_month_single_digit_month():
    y, m, label = parse_month("2026-7")
    assert (y, m, label) == (2026, 7, "July 2026")


def test_parse_month_rejects_garbage():
    with pytest.raises(ValueError, match="--month must be 'YYYY-MM'"):
        parse_month("May 2026")


def test_parse_month_rejects_out_of_range():
    with pytest.raises(ValueError, match="month part must be 1..12"):
        parse_month("2026-13")
