"""
ISS-003: Unified credential manager for all external auth (OAuth tokens,
API keys). Gmail OAuth and OpenAI API key are the same problem.

ALL TESTS EXPECTED TO FAIL — scripts/credential_manager.py does not exist yet.
Run: pytest tests/test_iss003_credential_manager.py -v
"""

import os

import pytest

# FAILS on import — module does not exist
from scripts.credential_manager import CredentialManager  # noqa: E402


# —— Supported providers —————————————————————————————————————————————————————

@pytest.mark.parametrize("provider", ["gmail_oauth", "openai_api_key", "streamlit_github_oauth"])
def test_credential_manager_supports_known_provider(provider):
    """FAILS: CredentialManager does not exist."""
    mgr = CredentialManager()
    assert mgr.supports(provider)


def test_credential_manager_rejects_unknown_provider():
    """FAILS: CredentialManager does not exist."""
    mgr = CredentialManager()
    assert not mgr.supports("unknown_provider_xyz")


# —— Security: secrets never leak ———————————————————————————————————————————————

def test_credential_manager_repr_hides_secrets():
    """FAILS: CredentialManager does not exist."""
    mgr = CredentialManager()
    mgr.store("openai_api_key", "sk-supersecretkey123")
    representation = repr(mgr)
    assert "sk-supersecretkey123" not in representation
    assert "sk-" not in representation


def test_credential_str_hides_secrets():
    """FAILS: CredentialManager does not exist."""
    mgr = CredentialManager()
    mgr.store("openai_api_key", "sk-supersecretkey123")
    assert "sk-supersecretkey123" not in str(mgr)


def test_credential_never_written_to_disk_as_plaintext(tmp_path):
    """FAILS: CredentialManager does not exist."""
    mgr = CredentialManager(storage_dir=tmp_path)
    mgr.store("openai_api_key", "sk-supersecretkey123")
    for f in tmp_path.rglob("*"):
        if f.is_file():
            assert "sk-supersecretkey123" not in f.read_text(errors="ignore")


# —— Lifecycle —————————————————————————————————————————————————————————————————————

def test_store_and_retrieve_api_key():
    """FAILS: CredentialManager does not exist."""
    mgr = CredentialManager()
    mgr.store("openai_api_key", "sk-test")
    assert mgr.get("openai_api_key") == "sk-test"


def test_credential_expires_after_session():
    """FAILS: CredentialManager does not exist."""
    mgr = CredentialManager(ttl_seconds=0)
    mgr.store("openai_api_key", "sk-test")
    assert mgr.get("openai_api_key") is None


def test_get_missing_credential_returns_none():
    """FAILS: CredentialManager does not exist."""
    mgr = CredentialManager()
    assert mgr.get("gmail_oauth") is None


def test_is_available_returns_true_when_stored():
    """FAILS: CredentialManager does not exist."""
    mgr = CredentialManager()
    mgr.store("openai_api_key", "sk-test")
    assert mgr.is_available("openai_api_key") is True


def test_is_available_returns_false_when_not_stored():
    """FAILS: CredentialManager does not exist."""
    mgr = CredentialManager()
    assert mgr.is_available("openai_api_key") is False


def test_revoke_clears_credential():
    """FAILS: CredentialManager does not exist."""
    mgr = CredentialManager()
    mgr.store("openai_api_key", "sk-test")
    mgr.revoke("openai_api_key")
    assert mgr.get("openai_api_key") is None
