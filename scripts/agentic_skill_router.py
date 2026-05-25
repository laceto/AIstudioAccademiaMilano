"""
UserPromptSubmit hook — agentic workflow skill router.

Detects LangGraph / LangChain / multi-agent keywords in the user prompt
and injects a mandatory reminder for Claude to invoke the relevant
framework skills BEFORE writing any implementation code.

Output: JSON with hookSpecificOutput.additionalContext if keywords match,
        empty otherwise (never blocks the prompt).
"""
import json
import sys

_KEYWORDS = [
    "langgraph",
    "langchain",
    "multi-agent",
    "multiagent",
    "agentic",
    "agent graph",
    "agent workflow",
    "agent pipeline",
    "state graph",
    "stategraph",
    "digital twin",
    "deep agent",
    "orchestrat",      # covers: orchestration, orchestrate, orchestrator
    "subagent",
    "sub-agent",
    "langgraph-",      # catches skill names typed by the user
]

_REMINDER = (
    "[agentic-skill-router] This prompt involves LangGraph / LangChain / multi-agent work. "
    "MANDATORY: invoke the /agentic-router skill first to get routing guidance, "
    "then load whichever framework skills it recommends before writing any code: "
    "langgraph-fundamentals, langgraph-dynamic-parallelism, langgraph-subagents, "
    "langgraph-persistence, langgraph-human-in-the-loop, "
    "deep-agents-core, deep-agents-orchestration, deep-agents-memory, "
    "langchain-fundamentals, langchain-rag, langchain-middleware. "
    "Do NOT write LangGraph/LangChain implementation code before invoking the skill."
)


def main() -> None:
    try:
        data = json.load(sys.stdin)
        prompt = data.get("prompt", "").lower()
    except Exception:
        return  # never block on parse errors

    if any(kw in prompt for kw in _KEYWORDS):
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": _REMINDER,
            }
        }))


if __name__ == "__main__":
    main()
