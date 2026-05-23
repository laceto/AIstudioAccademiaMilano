"""Shared fixtures for AI Studio Accademia Milano test suite."""

import json
from pathlib import Path

import pytest


@pytest.fixture
def global_settings() -> dict:
    path = Path("config/global_settings.json")
    return json.loads(path.read_text())


@pytest.fixture
def sample_invoice_fields() -> dict:
    return {
        "invoice_number": "INV-TEST-001",
        "client_name": "Test Client Srl",
        "amount": 500.0,
        "currency": "EUR",
        "service": "Web design services",
        "date": "2026-05-23",
    }


@pytest.fixture
def advisory_report_with_disclaimer() -> str:
    return (
        "# Strategic Report\n\n"
        "Some advice here.\n\n"
        "*This report draws on AI knowledge and general business principles. "
        "It does not constitute regulated financial or legal advice.*"
    )


@pytest.fixture
def advisory_report_without_disclaimer() -> str:
    return "# Strategic Report\n\nSome advice here."
