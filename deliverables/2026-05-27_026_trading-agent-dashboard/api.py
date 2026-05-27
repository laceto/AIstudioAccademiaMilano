"""
Trading Agent Team REST API

Start: uvicorn api:app --host 0.0.0.0 --port 8000
Docs:  http://localhost:8000/docs

Authentication: X-API-Key header (configure via TRADING_API_KEY env var).
Leave TRADING_API_KEY unset to run without auth (local / trusted networks only).

Endpoints:
  GET  /health                    liveness
  GET  /api/agents                all agent statuses
  GET  /api/agents/{name}         single agent + config
  GET  /api/signals               all signals (?signal=buy|sell|hold)
  GET  /api/portfolio             portfolio snapshot (Alpaca paper)
  GET  /api/positions             open positions
  POST /api/run                   trigger strategy run
  GET  /api/analysis/{symbol}     run techa Orchestrator + cache result
  GET  /api/analyses              list all cached techa reports

DISCLAIMER: Paper trading only. This is not financial advice.
"""
import os
import sys
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent))

import agents as agent_module
import store

app = FastAPI(
    title="Trading Agent Team API",
    description=(
        "REST API for the Trading Agent Team dashboard (deliverable 025). "
        "Agents Alpha/Beta/Gamma use Alpaca paper mode. "
        "Agent Delta uses yfinance (Italian markets). "
        "/api/analysis/* integrates the techa LangGraph Orchestrator (deliverable 013)."
    ),
    version="2.0.0",
)

_API_KEY = os.environ.get("TRADING_API_KEY", "")


def _auth(x_api_key: Optional[str] = Header(default=None)) -> None:
    if _API_KEY and x_api_key != _API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header")


def _alpaca_creds() -> tuple[str, str]:
    api_key = os.environ.get("ALPACA_API_KEY", "")
    secret_key = os.environ.get("ALPACA_SECRET_KEY", "")
    return api_key, secret_key


# ── Meta ──────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["meta"])
def health() -> dict:
    state = store.load()
    return {
        "status": "ok",
        "agents_run": len(state.get("agents", {})),
        "analyses_cached": len(state.get("analyses", {})),
        "last_run": state.get("last_run"),
    }


# ── Agents ────────────────────────────────────────────────────────────────────

@app.get("/api/agents", tags=["agents"], dependencies=[Depends(_auth)])
def list_agents() -> dict:
    """Return status of every agent. Idle agents are included with their configs."""
    state = store.load()
    agents_data: dict = dict(state.get("agents", {}))
    for cfg in agent_module.AGENT_CONFIGS:
        if cfg["name"] not in agents_data:
            agents_data[cfg["name"]] = {
                "status": "idle",
                "name": cfg["name"],
                "description": cfg.get("description", ""),
                "data_source": cfg.get("data_source", "alpaca"),
                "symbols": cfg["symbols"],
                "signals": [],
                "summary": {},
            }
    return agents_data


@app.get("/api/agents/{name}", tags=["agents"], dependencies=[Depends(_auth)])
def get_agent(name: str) -> dict:
    cfg = next(
        (c for c in agent_module.AGENT_CONFIGS if c["name"].lower() == name.lower()), None
    )
    if cfg is None:
        valid = [c["name"] for c in agent_module.AGENT_CONFIGS]
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found. Valid: {valid}")
    state = store.load()
    data = state.get("agents", {}).get(
        cfg["name"], {"status": "idle", "signals": [], "summary": {}}
    )
    return {**data, "config": cfg}


# ── Signals ───────────────────────────────────────────────────────────────────

@app.get("/api/signals", tags=["signals"], dependencies=[Depends(_auth)])
def get_signals(
    signal: Optional[str] = Query(default=None, description="Filter: buy | sell | hold"),
    source: Optional[str] = Query(default=None, description="Filter by data_source: alpaca | yfinance"),
) -> dict:
    """Return all signals from all agents with optional filters."""
    state = store.load()
    sigs = agent_module.all_signals(state)
    if signal:
        sigs = [s for s in sigs if s.get("signal") == signal.lower()]
    if source:
        sigs = [s for s in sigs if s.get("data_source") == source.lower()]
    return {"count": len(sigs), "signals": sigs}


# ── Portfolio ─────────────────────────────────────────────────────────────────

@app.get("/api/portfolio", tags=["portfolio"], dependencies=[Depends(_auth)])
def get_portfolio() -> dict:
    """Latest Alpaca paper portfolio snapshot. Delta (yfinance) signals excluded."""
    state = store.load()
    portfolio = state.get("portfolio")
    if not portfolio:
        return {"message": "No portfolio data yet — run an Alpaca agent first (POST /api/run)"}
    return portfolio


@app.get("/api/positions", tags=["portfolio"], dependencies=[Depends(_auth)])
def get_positions() -> dict:
    state = store.load()
    return {"positions": state.get("portfolio", {}).get("positions", [])}


# ── Execution ─────────────────────────────────────────────────────────────────

class RunRequest(BaseModel):
    agent: Optional[str] = None  # None → run all four agents
    dry_run: bool = True


@app.post("/api/run", tags=["execution"], dependencies=[Depends(_auth)])
def trigger_run(req: RunRequest) -> dict:
    """
    Trigger strategy run for one or all agents.

    Delta (yfinance) agent runs without Alpaca credentials.
    Alpha / Beta / Gamma require ALPACA_API_KEY + ALPACA_SECRET_KEY.
    """
    api_key, secret_key = _alpaca_creds()

    if req.agent:
        cfg = next(
            (c for c in agent_module.AGENT_CONFIGS if c["name"].lower() == req.agent.lower()),
            None,
        )
        if cfg is None:
            raise HTTPException(status_code=404, detail=f"Agent '{req.agent}' not found")
        if cfg.get("data_source", "alpaca") == "alpaca" and not (api_key and secret_key):
            raise HTTPException(
                status_code=503,
                detail=f"Agent {cfg['name']} needs ALPACA_API_KEY + ALPACA_SECRET_KEY",
            )
        return agent_module.run_agent(cfg, api_key, secret_key, dry_run=req.dry_run)

    results = agent_module.run_all_agents(api_key, secret_key, dry_run=req.dry_run)
    return {"agents_run": len(results), "results": results}


# ── Techa Analysis (deliverable 013 integration) ──────────────────────────────

@app.get("/api/analyses", tags=["analysis"], dependencies=[Depends(_auth)])
def list_analyses() -> dict:
    """List all cached techa Orchestrator reports (symbol → cached_at + preview)."""
    state = store.load()
    analyses = state.get("analyses", {})
    summary = {
        sym: {
            "cached_at": data.get("cached_at"),
            "preview": (data.get("report") or "")[:200] + "…" if data.get("report") else None,
        }
        for sym, data in analyses.items()
    }
    return {"count": len(summary), "analyses": summary}


@app.get("/api/analysis/{symbol}", tags=["analysis"], dependencies=[Depends(_auth)])
def techa_analysis(
    symbol: str,
    lookback_days: int = Query(default=365, ge=60, le=730),
    benchmark: str = Query(default="^GSPC"),
    refresh: bool = Query(default=False, description="Force re-run even if cached"),
) -> dict:
    """
    Run the techa LangGraph Orchestrator on a symbol and return the GPT-4o report.
    Results are cached in state.json; use ?refresh=true to force a new run.

    Requires `techa` to be installed and OPENAI_API_KEY to be set.
    Integrates with deliverable 013 (2026-05-24_013_techa-streamlit).
    """
    symbol = symbol.upper()

    # Return cached result if available and refresh not requested
    if not refresh:
        cached = store.get_analysis(symbol)
        if cached:
            return {**cached, "from_cache": True}

    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if not openai_key:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY not set on this server")
    os.environ["OPENAI_API_KEY"] = openai_key

    try:
        from techa.agents.orchestrator import create_orchestrator
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail=(
                "techa is not installed. "
                "Run: pip install 'techa @ git+https://github.com/laceto/techa.git@main'"
            ),
        )

    try:
        graph = create_orchestrator(
            symbol=symbol,
            data_source="live",
            analysis_date=None,
            lookback_days=lookback_days,
            benchmark=benchmark,
            relative=False,
        )
        result = graph.invoke(graph._initial_state)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"techa failed: {type(exc).__name__}: {exc}")

    report = next(
        (
            result[k]
            for k in ("final_output", "report", "output", "summary")
            if k in result and isinstance(result[k], str)
        ),
        None,
    )
    data = {
        "symbol": symbol,
        "report": report,
        "lookback_days": lookback_days,
        "benchmark": benchmark,
        "raw": {k: v for k, v in result.items() if k != "final_output"},
        "from_cache": False,
    }
    store.update_analysis(symbol, data)
    return data
