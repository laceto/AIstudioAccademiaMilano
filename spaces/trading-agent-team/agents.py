"""
Trading Agent Team — four named agents covering US and Italian markets.

Alpha / Beta / Gamma  — US large-caps via Alpaca paper (executes dry-run orders)
Delta                 — Italian stocks from myfinance2 daily brief via yfinance;
                        bull candidates → LONG analysis, bear candidates → SHORT analysis

Each agent runs SMA crossover + RSI. Shared state is written to store.py
(state.json) so the Streamlit dashboard and FastAPI server stay in sync.

If `techa` is installed, each signal is enriched with a candlestick-pattern
scan from techa's Pattern agent (pure TA-Lib, no LLM overhead).
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import store
import data_provider
from strategy import sma_crossover_signal, compute_rsi
from trader import make_clients, get_position, qty_to_buy
from brief_loader import fetch_brief

# ── Agent roster ──────────────────────────────────────────────────────────────
AGENT_CONFIGS: list[dict] = [
    {
        "name": "Alpha",
        "description": "US large-cap tech — momentum (SMA 20/50)",
        "symbols": ["AAPL", "MSFT", "GOOGL"],
        "short_window": 20,
        "long_window": 50,
        "data_source": "alpaca",
    },
    {
        "name": "Beta",
        "description": "US semiconductor & EV — fast trend (SMA 10/30)",
        "symbols": ["NVDA", "AMD", "TSLA"],
        "short_window": 10,
        "long_window": 30,
        "data_source": "alpaca",
    },
    {
        "name": "Gamma",
        "description": "US internet mega-cap — slow trend (SMA 15/40)",
        "symbols": ["AMZN", "META"],
        "short_window": 15,
        "long_window": 40,
        "data_source": "alpaca",
    },
    {
        "name": "Delta",
        "description": "Italian brief — bull (LONG) + bear (SHORT) · myfinance2 daily brief · yfinance · analysis only",
        "symbols": [],               # populated at runtime from the daily brief
        "short_window": 20,
        "long_window": 60,
        "data_source": "yfinance",   # Alpaca does not cover Borsa Italiana
        "brief_driven": True,
    },
]

# ── Optional techa pattern enrichment ────────────────────────────────────────
def _techa_patterns(symbols: list[str]) -> dict[str, list[str]]:
    """
    Return a dict of {symbol: [pattern_names]} using techa's Pattern agent.
    Returns empty dicts per symbol if techa is not installed or fails.
    Pure TA-Lib — no LLM call, safe to run on every agent cycle.
    """
    try:
        from techa.agents.patterns import create_pattern_agent
        graph = create_pattern_agent(symbols, signal_filter="all")
        result = graph.invoke(graph._initial_state)
        # techa Pattern agent returns patterns keyed by ticker
        raw = result.get("patterns") or result.get("output") or {}
        if isinstance(raw, dict):
            return {sym: raw.get(sym, []) for sym in symbols}
        return {sym: [] for sym in symbols}
    except Exception:
        return {sym: [] for sym in symbols}


# ── Brief-driven symbol resolution ───────────────────────────────────────────
def _resolve_symbols(cfg: dict) -> tuple[list[str], dict[str, str]]:
    """Return (all_symbols, side_map) where side_map[symbol] = 'long'|'short'."""
    if not cfg.get("brief_driven"):
        return cfg["symbols"], {s: "long" for s in cfg["symbols"]}

    brief = fetch_brief()
    bull = brief.get("bull", [])
    bear = brief.get("bear", [])
    side_map = {s: "long" for s in bull}
    side_map.update({s: "short" for s in bear})
    return bull + bear, side_map


# ── Core run logic ────────────────────────────────────────────────────────────
def run_agent(cfg: dict, api_key: str, secret_key: str, dry_run: bool = True) -> dict:
    name = cfg["name"]
    src = cfg.get("data_source", "alpaca")

    store.update_agent(name, {
        "status": "running",
        "name": name,
        "description": cfg.get("description", ""),
        "data_source": src,
        "last_run": datetime.now().isoformat(),
        "signals": [],
        "summary": {},
    })

    try:
        symbols, side_map = _resolve_symbols(cfg)

        # Alpaca agents get full trading + data client; yfinance agents get neither
        if src == "alpaca":
            trading_client, data_client = make_clients(api_key, secret_key)
            account = trading_client.get_account()
            equity = float(account.equity)
        else:
            trading_client = data_client = None
            equity = 100_000.0  # nominal for position-size display only

        # Optional: gather candlestick patterns for all symbols in one techa call
        patterns = _techa_patterns(symbols)

        signals: list[dict] = []
        for symbol in symbols:
            side = side_map.get(symbol, "long")
            bars = data_provider.get_bars(
                symbol,
                data_source=src,
                data_client=data_client,
            )
            if len(bars) < cfg["long_window"] + 1:
                signals.append({
                    "symbol": symbol,
                    "side": side,
                    "signal": "insufficient_data",
                    "rsi": None,
                    "price": None,
                    "action": "none",
                    "patterns": [],
                    "data_source": src,
                    "timestamp": datetime.now().isoformat(),
                })
                continue

            sig = sma_crossover_signal(bars, cfg["short_window"], cfg["long_window"])
            rsi = compute_rsi(bars)
            price = float(bars["close"].iloc[-1])
            sym_patterns = patterns.get(symbol, [])

            # Determine action — aware of long/short side
            action = "none"
            if src == "alpaca" and trading_client:
                position = get_position(trading_client, symbol)
                if side == "long":
                    if sig == "buy" and position is None:
                        qty = qty_to_buy(bars, equity)
                        action = f"would BUY {qty} shares [dry run]" if dry_run else f"BUY {qty} shares"
                    elif sig == "sell" and position is not None:
                        qty = abs(int(float(position.qty)))
                        action = f"would SELL {qty} shares [dry run]" if dry_run else f"SELL {qty} shares"
                else:  # short
                    if sig == "sell" and position is None:
                        qty = qty_to_buy(bars, equity)
                        action = f"would SHORT {qty} shares [dry run]" if dry_run else f"SHORT {qty} shares"
                    elif sig == "buy" and position is not None:
                        qty = abs(int(float(position.qty)))
                        action = f"would COVER {qty} shares [dry run]" if dry_run else f"COVER {qty} shares"
            else:
                # yfinance agents are analysis-only
                if side == "long":
                    if sig == "buy":
                        qty = qty_to_buy(bars, equity)
                        action = f"signal: LONG ~{qty} shares [analysis only]"
                    elif sig == "sell":
                        action = "signal: EXIT LONG [analysis only]"
                else:  # short
                    if sig == "sell":
                        qty = qty_to_buy(bars, equity)
                        action = f"signal: SHORT ~{qty} shares [analysis only]"
                    elif sig == "buy":
                        action = "signal: COVER SHORT [analysis only]"

            signals.append({
                "symbol": symbol,
                "side": side,
                "signal": sig,
                "rsi": round(rsi, 1),
                "price": round(price, 2),
                "action": action,
                "patterns": sym_patterns,
                "data_source": src,
                "timestamp": datetime.now().isoformat(),
            })

        # Update shared portfolio state (Alpaca agents only)
        if src == "alpaca" and trading_client:
            positions_raw = trading_client.get_all_positions()
            pnl = float(account.equity) - float(account.last_equity)
            store.update_portfolio({
                "equity": float(account.equity),
                "cash": float(account.cash),
                "buying_power": float(account.buying_power),
                "today_pnl": pnl,
                "positions": [
                    {
                        "symbol": p.symbol,
                        "qty": float(p.qty),
                        "entry_price": float(p.avg_entry_price),
                        "current_price": float(p.current_price),
                        "market_value": float(p.market_value),
                        "unrealized_pl": float(p.unrealized_pl),
                        "unrealized_plpc": round(float(p.unrealized_plpc) * 100, 2),
                    }
                    for p in positions_raw
                ],
            })

        summary = {
            "total": len(signals),
            "buy": sum(1 for s in signals if s["signal"] == "buy"),
            "sell": sum(1 for s in signals if s["signal"] == "sell"),
            "hold": sum(1 for s in signals if s["signal"] == "hold"),
        }
        result = {
            "status": "done",
            "name": name,
            "description": cfg.get("description", ""),
            "data_source": src,
            "last_run": datetime.now().isoformat(),
            "signals": signals,
            "summary": summary,
        }
        store.update_agent(name, result)
        return result

    except Exception as exc:
        err = {
            "status": "error",
            "name": name,
            "description": cfg.get("description", ""),
            "data_source": src,
            "error": str(exc),
            "last_run": datetime.now().isoformat(),
            "signals": [],
            "summary": {},
        }
        store.update_agent(name, err)
        return err


def run_all_agents(api_key: str, secret_key: str, dry_run: bool = True) -> list[dict]:
    return [run_agent(cfg, api_key, secret_key, dry_run) for cfg in AGENT_CONFIGS]


def all_signals(state: dict) -> list[dict]:
    result = []
    for agent_data in state.get("agents", {}).values():
        agent_name = agent_data.get("name", "unknown")
        for sig in agent_data.get("signals", []):
            result.append({**sig, "agent": agent_name})
    return result
