"""
ISS-004: Templates library so Chiara stops building from scratch.
Two templates must exist and be callable: invoice PDF and chatbot app.

ALL TESTS EXPECTED TO FAIL — templates/ does not exist yet.
Run: pytest tests/test_iss004_templates.py -v
"""

import pytest

# FAILS on import — modules do not exist
from templates.pdf.invoice_standard import InvoiceTemplate      # noqa: E402
from templates.streamlit.chatbot import ChatbotTemplate          # noqa: E402


# —— InvoiceTemplate ————————————————————————————————————————————————————————————————

def test_invoice_template_instantiates_with_valid_fields(sample_invoice_fields):
    """FAILS: InvoiceTemplate does not exist."""
    t = InvoiceTemplate(**sample_invoice_fields)
    assert t is not None


def test_invoice_template_is_valid_with_all_fields(sample_invoice_fields):
    """FAILS: InvoiceTemplate does not exist."""
    t = InvoiceTemplate(**sample_invoice_fields)
    assert t.is_valid() is True


def test_invoice_template_raises_without_client_name():
    """FAILS: InvoiceTemplate does not exist."""
    with pytest.raises((TypeError, ValueError)):
        InvoiceTemplate(invoice_number="INV-001", amount=100.0, service="X", date="2026-01-01")


def test_invoice_template_raises_without_amount():
    """FAILS: InvoiceTemplate does not exist."""
    with pytest.raises((TypeError, ValueError)):
        InvoiceTemplate(invoice_number="INV-001", client_name="X", service="X", date="2026-01-01")


def test_invoice_template_render_returns_pdf_bytes(sample_invoice_fields):
    """FAILS: InvoiceTemplate does not exist."""
    t = InvoiceTemplate(**sample_invoice_fields)
    pdf_bytes = t.render()
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    assert pdf_bytes[:4] == b"%PDF", "Output is not a valid PDF"


def test_invoice_template_render_contains_client_name(sample_invoice_fields):
    """FAILS: InvoiceTemplate does not exist."""
    t = InvoiceTemplate(**sample_invoice_fields)
    pdf_bytes = t.render()
    assert b"Test Client" in pdf_bytes or b"Test Client" in pdf_bytes.decode("latin-1", errors="ignore").encode()


def test_invoice_template_render_is_fast(sample_invoice_fields):
    """FAILS: InvoiceTemplate does not exist. Target: under 3s (down from 12s scratch build)."""
    import time
    t = InvoiceTemplate(**sample_invoice_fields)
    start = time.perf_counter()
    t.render()
    elapsed = time.perf_counter() - start
    assert elapsed < 3.0, f"Template render took {elapsed:.2f}s, expected < 3.0s"


# —— ChatbotTemplate —————————————————————————————————————————————————————————————————

@pytest.mark.parametrize("provider,model", [
    ("openai",    "gpt-4o"),
    ("anthropic", "claude-sonnet-4-6"),
    ("groq",      "llama-3.3-70b-versatile"),
])
def test_chatbot_template_accepts_known_providers(provider, model):
    """FAILS: ChatbotTemplate does not exist."""
    t = ChatbotTemplate(provider=provider, model=model)
    assert t.is_valid() is True


def test_chatbot_template_raises_on_unknown_provider():
    """FAILS: ChatbotTemplate does not exist."""
    with pytest.raises(ValueError, match="Unsupported provider"):
        ChatbotTemplate(provider="unknown_llm", model="whatever")


@pytest.mark.parametrize("provider,model,expected_import", [
    ("openai",    "gpt-4o",                   "from openai import OpenAI"),
    ("anthropic", "claude-sonnet-4-6",        "from anthropic import Anthropic"),
    ("groq",      "llama-3.3-70b-versatile",  "from groq import Groq"),
])
def test_chatbot_template_render_contains_correct_import(provider, model, expected_import):
    """FAILS: ChatbotTemplate does not exist."""
    t = ChatbotTemplate(provider=provider, model=model)
    code = t.render()
    assert expected_import in code


def test_chatbot_template_render_always_uses_streamlit_secrets():
    """FAILS: ChatbotTemplate does not exist. API key must never be hardcoded."""
    for provider, model in [("openai", "gpt-4o"), ("anthropic", "claude-sonnet-4-6")]:
        t = ChatbotTemplate(provider=provider, model=model)
        code = t.render()
        assert "st.secrets" in code, f"{provider} template does not use st.secrets"
        assert "api_key =" not in code.replace("st.secrets", ""), "Hardcoded api_key found"


def test_chatbot_template_render_always_has_system_prompt_input():
    """FAILS: ChatbotTemplate does not exist."""
    t = ChatbotTemplate(provider="openai", model="gpt-4o")
    code = t.render()
    assert "system_prompt" in code
    assert "text_area" in code


def test_chatbot_template_render_always_streams():
    """FAILS: ChatbotTemplate does not exist."""
    t = ChatbotTemplate(provider="openai", model="gpt-4o")
    code = t.render()
    assert "stream" in code
