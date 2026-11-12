"""Ask the agent one question.

    export ANTHROPIC_API_KEY=...       # or set GCAL_AGENT_MODEL to your provider
    export GCAL_CREDENTIALS_FILE=./credentials.json
    deepagents-gcal auth               # once
    python examples/01_quickstart.py
"""

from deepagents_gcal import create_calendar_agent

agent = create_calendar_agent(dry_run=True)  # drop dry_run to touch the real calendar

result = agent.invoke(
    {"messages": [{"role": "user", "content": "What's on my calendar tomorrow?"}]},
    config={"configurable": {"thread_id": "quickstart"}},
)
print(result["messages"][-1].content)
