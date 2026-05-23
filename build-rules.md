# Build Rules

## Context
You are implementing a service, API, automation, or agent for this AI enterprise. Brainstorming is already done.

## Stack Defaults
- **LangChain** — natural language workflows and chains
- **LangGraph** — multi-agent orchestration, stateful graphs
- **DeepAgents** — analog-to-digital real-world solutions
- **Python projects**: use `pyproject.toml`, not `requirements.txt` alone
- **Default model**: `claude-sonnet-4-6`; escalate to `claude-opus-4-7` for complex reasoning

## Delivery Standard
Every build must produce a tangible deployed output — software, API, automation, agent, or workflow. No consulting theater.

## Risk Gate (mandatory before shipping)
Before marking anything done, verify against the five risk agents:

| Agent | Check |
|---|---|
| Technical Auditor | Code quality, security, stability |
| Financial Controller | Pricing won't run at a loss |
| Operational Monitor | No broken automation chains |
| Reputation Guardian | Output quality is defensible |
| Compliance Agent | Data handling and API ToS are clean |

Flag any open risks in a `.md` file alongside the implementation. Full definitions in `to implement/ai_risk_management_team.md`.

## When Done
→ Risk gate passed  
→ LOAD: `docs-rules.md` to document the new service  
→ LOAD: `project-setup-rules.md` if a new repo is needed
