"""
Canonical LLM factory for AI Studio Accademia Milano.

Deliverable-local copies should re-export from here:
    from scripts.llm_factory import get_llm  # absolute
    # or, if the repo root is on sys.path:
    from llm_factory import get_llm

Tiers:
  fast  → claude-haiku-4-5-20251001 / gpt-4o-mini
  smart → claude-sonnet-4-6         / gpt-4o
"""
from __future__ import annotations

from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel


def get_llm(
    provider: str = "anthropic",
    tier: Literal["fast", "smart"] = "fast",
    **kwargs,
) -> BaseChatModel:
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        model = "gpt-4o-mini" if tier == "fast" else "gpt-4o"
        return ChatOpenAI(model=model, **kwargs)
    # default: anthropic
    from langchain_anthropic import ChatAnthropic
    model = "claude-haiku-4-5-20251001" if tier == "fast" else "claude-sonnet-4-6"
    return ChatAnthropic(model=model, **kwargs)
