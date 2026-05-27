"""
Trading Agent Team — three named agents covering different symbol baskets.

Each agent runs an SMA crossover + RSI strategy with its own parameters.
Results are persisted to store.py (state.json) so the Streamlit dashboard
and FastAPI server always read consistent, shared state.
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import store
from strategy import sma_crossover_signal, compute_rsi
from trader import make_clients, get_bars, get_position, qty_to_buy

AGENT_CONFIGS: list[dict] = [
    {
        "name": "Alpha",
        "description": "Large-cap tech — momentum (SMA 20/50)",
        "symbols": ["AAPL", "MSFT", "GOOGL"],
        "short_window": 20,
        "long_window": 50,
    },
    {
        "name": "Beta",
        "description": "Semiconductor & EV — fast trend (SMA 10/30)",
        "symbols": ["NVDA", "AMD", "TSLA"],
        "short_window": 10,
        "long_window": 30,
    },
    {
        "name": "Gamma",
        "description": "Internet mega-cap — slow trend (SMA 15/40)",
        "symbols": ["AMZN", "META"],
        "short_window": 15,
        "long_window": 40,
    },
]


def run_agent(cfg: dict, api_key: str, secret_key: str, dry_run: bool = True) -> dict:
    name = cfg["name"]
    store.update_agent(name, {
        "status": "running",
        "name": name,
        "description": cfg.get("description", ""),
        "last_run": datetime.now().isoformat(),
        "signals": [],
        "summary": {},
    })

    try:
        trading_client, data_client = make_clients(api_key, secret_key)
        account = trading_client.get_account()
        equity = float(account.equity)
        signals: list[dict] = []

        for symbol in cfg["symbols"]:
            bars = get_bars(data_client, symbol)
            if len(bars) < cfg["long_window"] + 1:
                signals.append({
                    "symbol": symbol,
                    "signal": "insufficient_data",
                    "rsi": None,
                    "price": None,
                    "action": "none",
                    "timestamp": datetime.now().isoformat(),
                })
                continue

            sig = sma_crossover_signal(bars, cfg["short_window"], cfg["long_window"])
            rsi = compute_rsi(bars)
            position = get_position(trading_client, symbol)
            price = float(bars["close"].iloc[-1])
            action = "none"

            if sig == "buy" and position is None:
                qty = qty_to_buy(bars, equity)
                action = f"would BUY {qty} shares [dry run]" if dry_run else f"BUY {qty} shares"
            elif sig == "sell" and position is not None:
                qty = abs(int(float(position.qty)))
                action = f"would SELL {qty} shares [dry run]" if dry_run else f"SELL {qty} shares"

            signals.append({
                "symbol": symbol,
                "signal": sig,
                "rsi": round(rsi, 1),
                "price": round(price, 2),
                "action": action,
                "timestamp": datetime.now().isoformat(),
            })

        # Refresh shared portfolio state from this Alpaca session
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

        buy_count = sum(1 for s in signals if s["signal"] == "buy")
        sell_count = sum(1 for s in signals if s["signal"] == "sell")
        hold_count = sum(1 for s in signals if s["signal"] == "hold")

        result = {
            "status": "done",
            "name": name,
            "description": cfg.get("description", ""),
            "last_run": datetime.now().isoformat(),
            "signals": signals,
            "summary": {
                "total": len(signals),
                "buy": buy_count,
                "sell": sell_count,
                "hold": hold_count,
            },
        }
        store.update_agent(name, result)
        return result

    except Exception as exc:
        err = {
            "status": "error",
            "name": name,
            "description": cfg.get("description", ""),
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
