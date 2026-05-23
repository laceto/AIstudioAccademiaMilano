"""
ISS-006: Advisory reports must include a disclaimer and, where possible,
source citations. Chiara must never ship an advisory output without it.

ALL TESTS EXPECTED TO FAIL — validate_advisory_output() does not exist yet.
Run: pytest tests/test_iss006_source_citation.py -v
"""

import pytest

# FAILS on import — function does not exist in learning_loop.py yet
from scripts.learning_loop import validate_advisory_output  # noqa: E402


DISCLAIMER_PHRASES = [
    "does not constitute regulated financial",
    "does not constitute regulated",
    "AI knowledge and general business principles",
    "not constitute.*advice",
]


# —— Disclaimer enforcement ——————————————————————————————————————————————————————

def test_advisory_without_disclaimer_raises(advisory_report_without_disclaimer):
    """FAILS: validate_advisory_output does not exist."""
    with pytest.raises(ValueError, match="disclaimer"):
        validate_advisory_output(advisory_report_without_disclaimer)


def test_advisory_with_disclaimer_passes(advisory_report_with_disclaimer):
    """FAILS: validate_advisory_output does not exist."""
    assert validate_advisory_output(advisory_report_with_disclaimer) is True


def test_empty_report_raises():
    """FAILS: validate_advisory_output does not exist."""
    with pytest.raises(ValueError):
        validate_advisory_output("")


def test_report_with_only_disclaimer_raises():
    """FAILS: validate_advisory_output does not exist.
    A disclaimer alone is not a valid report — must have actual content.
    """
    disclaimer_only = "*This report does not constitute regulated financial advice.*"
    with pytest.raises(ValueError, match="content"):
        validate_advisory_output(disclaimer_only)


# —— Disclaimer placement ——————————————————————————————————————————————————————————

def test_disclaimer_must_appear_at_top_or_bottom():
    """FAILS: validate_advisory_output does not exist.
    Disclaimer buried in the middle of a report is not acceptable.
    """
    buried = (
        "# Report\n\nAdvice paragraph one.\n\n"
        "*This report does not constitute regulated financial advice.*\n\n"
        "Advice paragraph two.\n\nAdvice paragraph three."
    )
    with pytest.raises(ValueError, match="placement"):
        validate_advisory_output(buried)


# —— Minimum content length ———————————————————————————————————————————————————————

def test_report_below_minimum_word_count_raises():
    """FAILS: validate_advisory_output does not exist.
    A strategic report under 100 words (excluding disclaimer) is rejected.
    """
    short = "Short advice. " * 5 + "\n\n*This report does not constitute regulated financial advice.*"
    with pytest.raises(ValueError, match="too short"):
        validate_advisory_output(short, min_words=100)
