"""
LLM factory — returns the right model for a given provider and tier.

  provider: "anthropic" | "openai"
  tier:     "fast"  → haiku-4.5  / gpt-4o-mini
            "smart" → sonnet-4.6 / gpt-4o

Usage in a LangGraph node:
    def my_node(state, config: RunnableConfig) -> dict:
        provider = config.get("configurable", {}).get("provider", "anthropic")
        llm = get_llm(provider, "fast", max_tokens=1024, temperature=0)
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

    # default: anthropic
    from langchain_anthropic import ChatAnthropic
    model = "claude-haiku-4-5-20251001" if tier == "fast" else "claude-sonnet-4-6"
    return ChatAnthropic(model=model, **kwargs)
