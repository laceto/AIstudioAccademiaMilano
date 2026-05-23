# Brainstorm Rules

## Context
A new request has arrived. Before any implementation, brainstorm first.

## Protocol
1. Use `/brainstorm` to open a structured session
2. Identify which staff agent owns the task:
   - **Stacy** → workflows, orchestration, operations
   - **Gianni** → APIs, infra, code architecture
   - **Chiara** → UI/UX, design, brand
   - **Francesca** → sales, community, monetization
   - **Marco** → payments, pricing, financial flows
   - **Luigi** → anything requiring final strategic decision
3. Determine if the output needs its own GitHub repo (`AIstudio_Project_<timestamp>`)
4. Flag risks — surface them against the five Risk Agents (Technical, Financial, Operational, Reputation, Compliance)
5. Check the 90-day roadmap (`to implement/execution_roadmap_90_days.md`) — stay within the current phase

## Output
Save the brainstorming output as a `.md` file before any code is written. Commit it.

## When Done
→ You have a documented decision and an agent assignment  
→ LOAD: `build-rules.md` if the task is implementation  
→ LOAD: `agent-rules.md` if the task is creating a new staff agent  
→ LOAD: `project-setup-rules.md` if the task is spinning up a new project repo  
→ LOAD: `docs-rules.md` if the task is documentation only
