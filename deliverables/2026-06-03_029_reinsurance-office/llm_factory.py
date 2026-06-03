"""
LLM factory — provider/tier abstraction for the reinsurance office graph.

  provider: "anthropic" | "openai"
  tier:     "fast"  → haiku-4.5  / gpt-4o-mini  (intake, accounting entries)
            "smart" → sonnet-4.6 / gpt-4o        (medical, actuarial, sr exec)
"""
from typing import Literal

from langchain_core.language_models import BaseChatModel


def get_llm(
    provider: str,
    tier: Literal["fast", "smart"] = "fast",
    **kwargs,
) -> BaseChatModel:
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        model = "gpt-4o-mini" if tier == "fast" else "gpt-4o"
        return ChatOpenAI(model=model, **kwargs)

    from langchain_anthropic import ChatAnthropic
    model = "claude-haiku-4-5-20251001" if tier == "fast" else "claude-sonnet-4-6"
    return ChatAnthropic(model=model, **kwargs)
