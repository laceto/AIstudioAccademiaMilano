"""
ISS-002: intent_registry.yaml must exist so Stacy routes any known intent
instantly without Gianni resolving manually.

ALL TESTS EXPECTED TO FAIL — implementation does not exist yet.
Run: pytest tests/test_iss002_intent_registry.py -v
"""

from pathlib import Path

import pytest
import yaml

REGISTRY_PATH = Path("process/intent_registry.yaml")

REQUIRED_INTENT_FIELDS = {"skills", "delivery_options"}
KNOWN_INTENTS = [
    "website_creation",
    "pdf_creation",
    "invoice_generation",
    "email_delivery",
    "strategic_consultation",
    "chatbot_creation",
]


# —— File existence —————————————————————————————————————————————————————

def test_intent_registry_file_exists():
    """FAILS: process/intent_registry.yaml does not exist yet."""
    assert REGISTRY_PATH.exists(), f"{REGISTRY_PATH} not found"


def test_intent_registry_is_valid_yaml():
    """FAILS: file does not exist, yaml.safe_load will raise."""
    content = yaml.safe_load(REGISTRY_PATH.read_text())
    assert isinstance(content, dict)


# —— Schema ————————————————————————————————————————————————————————————————

@pytest.mark.parametrize("intent", KNOWN_INTENTS)
def test_known_intent_present_in_registry(intent):
    """FAILS: registry file does not exist."""
    registry = yaml.safe_load(REGISTRY_PATH.read_text())
    assert intent in registry, f"Intent '{intent}' missing from registry"


@pytest.mark.parametrize("intent", KNOWN_INTENTS)
def test_intent_entry_has_required_fields(intent):
    """FAILS: registry file does not exist."""
    registry = yaml.safe_load(REGISTRY_PATH.read_text())
    entry = registry[intent]
    missing = REQUIRED_INTENT_FIELDS - set(entry.keys())
    assert not missing, f"Intent '{intent}' missing fields: {missing}"


@pytest.mark.parametrize("intent", KNOWN_INTENTS)
def test_intent_skills_list_is_non_empty(intent):
    """FAILS: registry file does not exist."""
    registry = yaml.safe_load(REGISTRY_PATH.read_text())
    skills = registry[intent]["skills"]
    assert isinstance(skills, list) and len(skills) > 0


@pytest.mark.parametrize("intent", KNOWN_INTENTS)
def test_intent_delivery_options_is_non_empty(intent):
    """FAILS: registry file does not exist."""
    registry = yaml.safe_load(REGISTRY_PATH.read_text())
    options = registry[intent]["delivery_options"]
    assert isinstance(options, list) and len(options) > 0


# —— Consistency with global_settings ————————————————————————————————————————————

def test_registry_intents_match_global_settings_map(global_settings):
    """FAILS: registry file does not exist."""
    registry = yaml.safe_load(REGISTRY_PATH.read_text())
    settings_intents = set(global_settings["intent_to_skill_map"].keys())
    registry_intents = set(registry.keys())
    assert settings_intents == registry_intents, (
        f"Mismatch: in settings not in registry: {settings_intents - registry_intents}, "
        f"in registry not in settings: {registry_intents - settings_intents}"
    )


def test_registry_skills_match_global_settings_skills(global_settings):
    """FAILS: registry file does not exist."""
    registry = yaml.safe_load(REGISTRY_PATH.read_text())
    known_skills = set(global_settings["skills"].keys())
    for intent, entry in registry.items():
        for skill in entry["skills"]:
            assert skill in known_skills, (
                f"Skill '{skill}' in registry intent '{intent}' "
                f"not found in global_settings skills"
            )
