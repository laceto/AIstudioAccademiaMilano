---
request_id: "028"
date: "2026-05-27"
intent: internal_team_showcase
outcome: success
agents_invoked:
  - name: Stacy
    role: Input Orchestrator
    action: Classified intent as internal_team_showcase, no pricing block needed
    duration_sec: 1
    status: ok
  - name: Gianni
    role: Request Analyzer
    action: "Stack: Streamlit + custom HTML/CSS; reads brand.json + global_settings.json"
    duration_sec: 2
    status: ok
  - name: Chiara
    role: Product Generator
    action: Built deliverables/2026-05-27_025_team-showcase/app.py (single-file Streamlit)
    duration_sec: 45
    status: ok
  - name: Stacy QA
    role: Output Validator
    action: Format and completeness check passed; no advisory disclaimer needed (internal)
    duration_sec: 2
    status: ok
  - name: Marco
    role: Transaction Manager
    action: Internal tooling — no invoice generated (price = 0.00)
    duration_sec: 1
    status: ok
  - name: Francesca
    role: Delivery Agent
    action: Committed and pushed on claude/team-coding-app-AiuDv
    duration_sec: 5
    status: ok
skills_used:
  - streamlit_app_builder
  - brand_config_reader
  - custom_css_theming
learning_flags:
  new_skills: []
  new_mcp: []
  risk_score: 1
---

# Team Showcase App — Deliverable 025

Single-page Streamlit app that visualises the entire AI Studio Accademia Milano
team structure: 6-agent delivery pipeline, 5 risk agents, 3 specialist agents,
and 4 department teams (RAG, Research, Input Gateway, V2 Squad).

## Features
- Hero banner with live KPI stats (deliverables shipped, tasks logged, success rate)
- Colour-coded pipeline cards with per-agent task counts from `global_settings.json`
- Risk agents section with actuarial formulae
- Specialist agents: Valentina, Lorenzo, IT Staff
- Department teams: RAG, Research, Input Gateway, V2 Squad
- Open Issues tracker (P1/P2/P3 colour-coded)
- Dark theme, responsive columns, zero external dependencies beyond Streamlit

## Run
```bash
streamlit run deliverables/2026-05-27_025_team-showcase/app.py
```
