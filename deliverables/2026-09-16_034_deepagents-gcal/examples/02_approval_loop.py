"""Drive the human-approval gate yourself.

Writes interrupt the graph; you inspect the pending call and resume with a
decision: approve, edit (supply `edited_action`), or reject (optional `message`).
"""

from langgraph.types import Command

from deepagents_gcal import create_calendar_agent

agent = create_calendar_agent(dry_run=True)
config = {"configurable": {"thread_id": "approval-demo"}}

result = agent.invoke(
    {"messages": [{"role": "user", "content": "Book 'Retro' tomorrow at 16:00 for 45 minutes"}]},
    config=config,
)

while result.get("__interrupt__"):
    for request in result["__interrupt__"][0].value["action_requests"]:
        print(f"pending: {request['name']} {request['args']}")
    answer = input("approve? [y/N] ").strip().lower()
    decision = {"type": "approve"} if answer == "y" else {"type": "reject", "message": "not now"}
    result = agent.invoke(Command(resume={"decisions": [decision]}), config=config)

print(result["messages"][-1].content)
