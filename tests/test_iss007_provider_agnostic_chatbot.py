"""
ISS-007: The Streamlit chatbot template must be provider-agnostic.
Swapping from OpenAI to Anthropic or Groq should not require a rebuild.

ALL TESTS EXPECTED TO FAIL — ChatbotTemplate does not exist yet.
Run: pytest tests/test_iss007_provider_agnostic_chatbot.py -v
"""

import ast

import pytest

# FAILS on import — module does not exist
from templates.streamlit.chatbot import ChatbotTemplate  # noqa: E402


PROVIDERS = [
    ("openai",    "gpt-4o",                   "OPENAI_API_KEY"),
    ("anthropic", "claude-sonnet-4-6",        "ANTHROPIC_API_KEY"),
    ("groq",      "llama-3.3-70b-versatile",  "GROQ_API_KEY"),
]


# —— Provider compatibility —————————————————————————————————————————————————————————————

@pytest.mark.parametrize("provider,model,expected_key", PROVIDERS)
def test_render_produces_valid_python(provider, model, expected_key):
    """FAILS: ChatbotTemplate does not exist."""
    t = ChatbotTemplate(provider=provider, model=model)
    code = t.render()
    try:
        ast.parse(code)
    except SyntaxError as e:
        pytest.fail(f"Generated code for {provider} has syntax error: {e}")


@pytest.mark.parametrize("provider,model,expected_key", PROVIDERS)
def test_render_references_correct_api_key_name(provider, model, expected_key):
    """FAILS: ChatbotTemplate does not exist."""
    t = ChatbotTemplate(provider=provider, model=model)
    code = t.render()
    assert expected_key in code, f"Expected secret key name '{expected_key}' not found in {provider} template"


@pytest.mark.parametrize("provider,model,expected_key", PROVIDERS)
def test_all_providers_have_streaming(provider, model, expected_key):
    """FAILS: ChatbotTemplate does not exist. Every provider must stream."""
    t = ChatbotTemplate(provider=provider, model=model)
    code = t.render()
    assert "stream" in code


@pytest.mark.parametrize("provider,model,expected_key", PROVIDERS)
def test_all_providers_have_system_prompt(provider, model, expected_key):
    """FAILS: ChatbotTemplate does not exist."""
    t = ChatbotTemplate(provider=provider, model=model)
    code = t.render()
    assert "system_prompt" in code
    assert "text_area" in code


@pytest.mark.parametrize("provider,model,expected_key", PROVIDERS)
def test_all_providers_have_chat_history(provider, model, expected_key):
    """FAILS: ChatbotTemplate does not exist."""
    t = ChatbotTemplate(provider=provider, model=model)
    code = t.render()
    assert "session_state" in code
    assert "messages" in code


# —— Swapping providers is cheap ————————————————————————————————————————————————————————————

def test_switching_provider_only_changes_provider_specific_lines():
    """FAILS: ChatbotTemplate does not exist.
    The Streamlit UI code (sidebar, chat history, input) must be identical
    across providers — only the client instantiation and API call differ.
    """
    openai_code    = ChatbotTemplate(provider="openai",    model="gpt-4o").render().splitlines()
    anthropic_code = ChatbotTemplate(provider="anthropic", model="claude-sonnet-4-6").render().splitlines()

    shared = set(openai_code) & set(anthropic_code)
    total  = max(len(openai_code), len(anthropic_code))

    # At least 70% of lines must be identical (only provider glue changes)
    assert len(shared) / total >= 0.70, (
        f"Too many lines differ between providers: {len(shared)}/{total} shared "
        f"({100*len(shared)/total:.0f}%). Expected ≥ 70%."
    )


def test_unknown_provider_raises_with_helpful_message():
    """FAILS: ChatbotTemplate does not exist."""
    with pytest.raises(ValueError) as exc_info:
        ChatbotTemplate(provider="bard", model="whatever")
    assert "bard" in str(exc_info.value).lower()
    assert "supported" in str(exc_info.value).lower()
