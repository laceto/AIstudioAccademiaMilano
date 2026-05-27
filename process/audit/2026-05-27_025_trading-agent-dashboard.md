---
request_id: "025"
date: "2026-05-27"
intent: algo_trading
outcome: success
agents_invoked:
  - name: Stacy
    role: intent_classifier
    action: classified as algo_trading @ 24.90
    duration_sec: 1
    status: success
  - name: Gianni
    role: technical_scoper
    action: designed multi-agent team architecture with shared JSON store
    duration_sec: 2
    status: success
  - name: Chiara
    role: implementer
    action: built app.py (Streamlit), api.py (FastAPI), agents.py, store.py, strategy.py, trader.py
    duration_sec: 10
    status: success
  - name: Stacy QA
    role: qa
    action: verified disclaimer, paper=True, no secrets in code, API auth
    duration_sec: 1
    status: success
  - name: Marco
    role: invoicing
    action: invoiced at algo_trading price 24.90
    duration_sec: 1
    status: success
  - name: Francesca
    role: delivery
    action: committed + pushed to claude/trading-agent-dashboard-app-c2pbx
    duration_sec: 2
    status: success
skills_used:
  - streamlit_dashboard
  - fastapi_rest_api
  - alpaca_trading
  - sma_rsi_strategy
  - shared_state_store
learning_flags:
  new_skills:
    - multi_agent_trading_team
    - shared_json_store_pattern
    - fastapi_streamlit_split_architecture
  new_mcp: []
  risk_score: 1
---

# Delivery 025 — Trading Agent Team Dashboard + API

## Summary

Three named trading agents (Alpha, Beta, Gamma) each covering a different basket of
symbols with their own SMA crossover parameters. A shared JSON state store (`state.json`)
lets both the Streamlit dashboard and the FastAPI server read consistent, fresh data
without duplicating Alpaca calls.

## Deliverable

`deliverables/2026-05-27_025_trading-agent-dashboard/`

| File | Purpose |
|------|---------|
| `app.py` | Streamlit team dashboard — portfolio KPIs, agent grid, signal table, chart |
| `api.py` | FastAPI REST API — 7 endpoints, optional X-API-Key auth |
| `agents.py` | Agent team definitions + run logic (SMA crossover + RSI) |
| `store.py` | Thread-safe atomic JSON state store |
| `strategy.py` | SMA crossover + RSI signal computation |
| `trader.py` | Alpaca client utilities (paper=True hardcoded) |
| `requirements.txt` | alpaca-py, streamlit, fastapi, uvicorn, plotly, pandas |

## How to run

```bash
cd deliverables/2026-05-27_025_trading-agent-dashboard
pip install -r requirements.txt

# Dashboard
ALPACA_API_KEY=xxx ALPACA_SECRET_KEY=yyy streamlit run app.py

# API (separate terminal)
ALPACA_API_KEY=xxx ALPACA_SECRET_KEY=yyy TRADING_API_KEY=secret uvicorn api:app --host 0.0.0.0 --port 8000
```

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Liveness |
| GET | /api/agents | All agent statuses |
| GET | /api/agents/{name} | Single agent |
| GET | /api/signals | All signals (?signal=buy filter) |
| GET | /api/portfolio | Portfolio snapshot |
| GET | /api/positions | Open positions |
| POST | /api/run | Trigger run (body: agent, dry_run) |

## Price

algo_trading: 24.90 EUR
