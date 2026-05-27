"""
Trading Agent Team REST API

Start: uvicorn api:app --host 0.0.0.0 --port 8000
Docs:  http://localhost:8000/docs

Authentication: X-API-Key header (configure via TRADING_API_KEY env var).
Leave TRADING_API_KEY unset to run without auth (local / trusted networks only).

DISCLAIMER: Paper trading only. This is not financial advice.
"""
import os
import sys
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent))

import agents as agent_module
import store

app = FastAPI(
    title="Trading Agent Team API",
    description=(
        "REST API for the Trading Agent Team dashboard. "
        "All strategy runs use Alpaca paper mode — no real capital."
    ),
    version="1.0.0",
)

_API_KEY = os.environ.get("TRADING_API_KEY", "")


def _auth(x_api_key: Optional[str] = Header(default=None)) -> None:
    if _API_KEY and x_api_key != _API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header")


# ── Meta ──────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}


# ── Agents ────────────────────────────────────────────────────────────────────

@app.get("/api/agents", tags=["agents"], dependencies=[Depends(_auth)])
def list_agents() -> dict:
    """Return status of every agent in the team. Idle agents are included."""
    state = store.load()
    agents_data: dict = dict(state.get("agents", {}))
    for cfg in agent_module.AGENT_CONFIGS:
        if cfg["name"] not in agents_data:
            agents_data[cfg["name"]] = {
                "status": "idle",
                "name": cfg["name"],
                "description": cfg.get("description", ""),
                "symbols": cfg["symbols"],
                "signals": [],
                "summary": {},
            }
    return agents_data


@app.get("/api/agents/{name}", tags=["agents"], dependencies=[Depends(_auth)])
def get_agent(name: str) -> dict:
    """Return detail for a single agent including its full config."""
    cfg = next(
        (c for c in agent_module.AGENT_CONFIGS if c["name"].lower() == name.lower()), None
    )
    if cfg is None:
        valid = [c["name"] for c in agent_module.AGENT_CONFIGS]
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found. Valid: {valid}")
    state = store.load()
    data = state.get("agents", {}).get(cfg["name"], {"status": "idle", "signals": [], "summary": {}})
    return {**data, "config": cfg}


# ── Signals ───────────────────────────────────────────────────────────────────

@app.get("/api/signals", tags=["signals"], dependencies=[Depends(_auth)])
def get_signals(signal: Optional[str] = None) -> dict:
    """
    Return all signals from all agents.
    Optional query param `?signal=buy|sell|hold` to filter.
    """
    state = store.load()
    sigs = agent_module.all_signals(state)
    if signal:
        sigs = [s for s in sigs if s.get("signal") == signal.lower()]
    return {"count": len(sigs), "signals": sigs}


# ── Portfolio ─────────────────────────────────────────────────────────────────

@app.get("/api/portfolio", tags=["portfolio"], dependencies=[Depends(_auth)])
def get_portfolio() -> dict:
    """Return the latest portfolio snapshot (equity, cash, P&L, positions)."""
    state = store.load()
    portfolio = state.get("portfolio")
    if not portfolio:
        return {"message": "No portfolio data yet — POST /api/run first"}
    return portfolio


@app.get("/api/positions", tags=["portfolio"], dependencies=[Depends(_auth)])
def get_positions() -> dict:
    """Return open positions from the latest portfolio snapshot."""
    state = store.load()
    portfolio = state.get("portfolio", {})
    return {"positions": portfolio.get("positions", [])}


# ── Execution ─────────────────────────────────────────────────────────────────

class RunRequest(BaseModel):
    agent: Optional[str] = None  # None → run all agents
    dry_run: bool = True


@app.post("/api/run", tags=["execution"], dependencies=[Depends(_auth)])
def trigger_run(req: RunRequest) -> dict:
    """
    Trigger a strategy run.

    - `agent`: name of a specific agent (Alpha / Beta / Gamma), or omit to run all.
    - `dry_run`: when true, signals are computed but no orders are submitted.
    """
    api_key = os.environ.get("ALPACA_API_KEY", "")
    secret_key = os.environ.get("ALPACA_SECRET_KEY", "")
    if not api_key or not secret_key:
        raise HTTPException(
            status_code=503,
            detail="ALPACA_API_KEY and ALPACA_SECRET_KEY must be set on the server",
        )

    if req.agent:
        cfg = next(
            (c for c in agent_module.AGENT_CONFIGS if c["name"].lower() == req.agent.lower()),
            None,
        )
        if cfg is None:
            raise HTTPException(status_code=404, detail=f"Agent '{req.agent}' not found")
        return agent_module.run_agent(cfg, api_key, secret_key, dry_run=req.dry_run)

    results = agent_module.run_all_agents(api_key, secret_key, dry_run=req.dry_run)
    return {"agents_run": len(results), "results": results}
