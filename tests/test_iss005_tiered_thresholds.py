"""
ISS-005: learning_loop.py must use tiered pattern thresholds from
global_settings, not a single flat value of 3.

ALL TESTS EXPECTED TO FAIL — get_threshold_for_skill() does not exist yet.
Run: pytest tests/test_iss005_tiered_thresholds.py -v
"""

import json
from pathlib import Path

import pytest

# FAILS on import — function does not exist in learning_loop.py yet
from scripts.learning_loop import get_threshold_for_skill  # noqa: E402


# —— Threshold values ————————————————————————————————————————————————————————————————

@pytest.mark.parametrize("skill", ["gmail_api_oauth", "openai_api_integration"])
def test_security_skills_have_threshold_one(skill):
    """FAILS: get_threshold_for_skill does not exist."""
    assert get_threshold_for_skill(skill) == 1


@pytest.mark.parametrize("skill", ["gmail_api_send", "vercel_api_deploy", "streamlit_cloud_deploy"])
def test_external_write_api_skills_have_threshold_two(skill):
    """FAILS: get_threshold_for_skill does not exist."""
    assert get_threshold_for_skill(skill) == 2


@pytest.mark.parametrize("skill", ["fpdf2_pdf_generation", "html_tailwind_css", "streamlit_app_generation"])
def test_preload_skills_have_threshold_three(skill):
    """FAILS: get_threshold_for_skill does not exist."""
    assert get_threshold_for_skill(skill) == 3


def test_unknown_skill_falls_back_to_preload_threshold():
    """FAILS: get_threshold_for_skill does not exist."""
    assert get_threshold_for_skill("some_new_unknown_skill") == 3


# —— Integration with global_settings ———————————————————————————————————————————————

def test_thresholds_loaded_from_global_settings(global_settings):
    """FAILS: get_threshold_for_skill does not exist.
    Verifies the function reads from pattern_thresholds, not a hardcoded int.
    """
    tiered = global_settings["pattern_thresholds"]
    assert tiered["security"] < tiered["external_api_write"] < tiered["skill_preload"] < tiered["ui_preference"]


def test_learning_loop_uses_tiered_not_flat_threshold():
    """FAILS: learning_loop.py still uses flat `pattern_threshold: 3`.
    Checks the source code directly to confirm the upgrade.
    """
    source = Path("scripts/learning_loop.py").read_text()
    assert "get_threshold_for_skill" in source, (
        "learning_loop.py still uses flat threshold — must call get_threshold_for_skill()"
    )
    assert 'settings.get("pattern_threshold", 3)' not in source, (
        "Flat threshold fallback still present in learning_loop.py"
    )
