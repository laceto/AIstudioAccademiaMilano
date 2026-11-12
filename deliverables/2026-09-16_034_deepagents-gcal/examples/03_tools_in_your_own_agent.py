"""Use the calendar tools without this package's agent.

`build_calendar_tools` returns plain LangChain tools — hand them to deepagents,
`create_agent`, or a LangGraph node of your own.
"""

from deepagents import create_deep_agent

from deepagents_gcal import GoogleCalendarClient, build_calendar_tools

client = GoogleCalendarClient.from_env(read_only=True)  # no write tools exist at all

agent = create_deep_agent(
    model="anthropic:claude-sonnet-5",
    tools=build_calendar_tools(client),
    system_prompt="You are a scheduling analyst. Answer only from the calendar you can read.",
)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "How many hours of meetings do I have this week?"}]}
)
print(result["messages"][-1].content)
