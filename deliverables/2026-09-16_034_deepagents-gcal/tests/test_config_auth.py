"""Settings resolution and credential-loading guardrails."""

from __future__ import annotations

import json

import pytest

from deepagents_gcal.auth import SCOPE_EVENTS, SCOPE_READONLY, load_credentials, scopes_for
from deepagents_gcal.config import CalendarSettings
from deepagents_gcal.errors import AuthError


def test_defaults_are_conservative():
    settings = CalendarSettings()
    assert settings.calendar_id == "primary"
    assert settings.read_only is False
    assert settings.dry_run is False


def test_from_env_reads_every_documented_variable(monkeypatch):
    monkeypatch.setenv("GCAL_CREDENTIALS_FILE", "/secrets/client.json")
    monkeypatch.setenv("GCAL_TOKEN_FILE", "/secrets/token.json")
    monkeypatch.setenv("GCAL_CALENDAR_ID", "team@studio.it")
    monkeypatch.setenv("GCAL_TIMEZONE", "Europe/Lisbon")
    monkeypatch.setenv("GCAL_DRY_RUN", "yes")
    monkeypatch.setenv("GCAL_MAX_RESULTS", "50")
    monkeypatch.setenv("GCAL_WORK_START", "8")
    monkeypatch.setenv("GCAL_WORK_END", "20")
    settings = CalendarSettings.from_env()
    assert settings.credentials_file == "/secrets/client.json"
    assert settings.calendar_id == "team@studio.it"
    assert settings.dry_run is True
    assert settings.max_results == 50
    assert settings.working_hours == (8, 20)


def test_overrides_beat_the_environment(monkeypatch):
    monkeypatch.setenv("GCAL_READ_ONLY", "false")
    assert CalendarSettings.from_env(read_only=True).read_only is True


def test_invalid_boolean_is_rejected_loudly(monkeypatch):
    monkeypatch.setenv("GCAL_DRY_RUN", "maybe")
    with pytest.raises(ValueError):
        CalendarSettings.from_env()


def test_application_default_credentials_are_picked_up(monkeypatch):
    monkeypatch.delenv("GCAL_SERVICE_ACCOUNT_FILE", raising=False)
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/secrets/sa.json")
    assert CalendarSettings.from_env().service_account_file == "/secrets/sa.json"


def test_describe_never_leaks_secret_material(monkeypatch, tmp_path):
    token = tmp_path / "token.json"
    token.write_text(json.dumps({"refresh_token": "SUPER-SECRET"}))
    described = CalendarSettings(token_file=str(token)).describe()
    assert "SUPER-SECRET" not in json.dumps(described)
    assert set(described) == {
        "calendar_id",
        "timezone",
        "read_only",
        "dry_run",
        "auth_mode",
        "credentials_present",
    }


def test_scopes_follow_least_privilege():
    assert scopes_for(read_only=True) == [SCOPE_READONLY]
    assert SCOPE_EVENTS in scopes_for(read_only=False)


def test_headless_agent_never_opens_a_browser_flow(monkeypatch, tmp_path):
    monkeypatch.delenv("GCAL_TOKEN_JSON", raising=False)
    settings = CalendarSettings(
        credentials_file=str(tmp_path / "credentials.json"),
        token_file=str(tmp_path / "missing.json"),
    )
    with pytest.raises(AuthError) as excinfo:
        load_credentials(settings)
    assert "deepagents-gcal auth" in str(excinfo.value)


def test_inline_token_must_be_valid_json(monkeypatch):
    monkeypatch.setenv("GCAL_TOKEN_JSON", "not-json")
    with pytest.raises(AuthError):
        load_credentials(CalendarSettings())


def test_missing_service_account_file_is_reported(monkeypatch, tmp_path):
    monkeypatch.delenv("GCAL_TOKEN_JSON", raising=False)
    settings = CalendarSettings(service_account_file=str(tmp_path / "absent.json"))
    with pytest.raises(AuthError) as excinfo:
        load_credentials(settings)
    assert "Service-account key not found" in str(excinfo.value)
