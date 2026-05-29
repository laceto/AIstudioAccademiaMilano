"""
Trading Agent Team — four named agents covering US and Italian markets.

Alpha / Beta / Gamma  — US large-caps via Alpaca paper (SMA crossover + RSI)
Delta                 — Italian stocks from myfinance2 daily brief; signals
                        read directly from the brief (no SMA recomputation).
                        Bull candidates → LONG, bear candidates → SHORT.
                        Signal methods (rbo_20, rema_50100, rtt_5020, …) and
                        regime flips are surfaced as metadata per signal.
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
        "description": "Italian brief — signals from myfinance2 daily_brief.txt · yfinance prices · analysis only",
        "symbols": [],          # populated at runtime from the brief
        "data_source": "yfinance",
        "brief_driven": True,
    },
]

# ── Optional techa pattern enrichment ────────────────────────────────────────
def _techa_patterns(symbols: list[str]) -> dict[str, list[str]]:
    try:
        from techa.agents.patterns import create_pattern_agent
        graph = create_pattern_agent(symbols, signal_filter="all")
        result = graph.invoke(graph._initial_state)
        raw = result.get("patterns") or result.get("output") or {}
        if isinstance(raw, dict):
            return {sym: raw.get(sym, []) for sym in symbols}
    except Exception:
        pass
    return {sym: [] for sym in symbols}


# ── Delta: signals straight from the brief ────────────────────────────────────
def run_delta_from_brief(cfg: dict) -> dict:
    """Build Delta signals entirely from the myfinance2 daily brief.

    No SMA crossover. No RSI recomputation. Signals are:
      bull candidate → signal='buy',  side='long'
      bear candidate → signal='sell', side='short'

    Metadata per signal includes: conviction, score_delta, daily_return,
    momentum, methods (signal flip methods that fired), regime_flip (bool).
    Current price is fetched from yfinance as best-effort for display only.
    """
    name = cfg["name"]
    store.update_agent(name, {
        "status": "running", "name": name,
        "description": cfg.get("description", ""),
        "data_source": "yfinance",
        "last_run": datetime.now().isoformat(),
        "signals": [], "summary": {},
    })

    try:
        brief = fetch_brief()
        if brief.get("error"):
            raise RuntimeError(f"Brief unavailable: {brief['error']}")

        # signal_flips is the primary source: {symbol: {direction, methods}}
        signal_flips = brief.get("signal_flips", {})
        regime_flips = brief.get("regime_flips", {})

        # Build lookup maps from candidates for enrichment
        bull_map = {c["symbol"]: c for c in brief.get("bull", [])}
        bear_map = {c["symbol"]: c for c in brief.get("bear", [])}

        signals: list[dict] = []

        for symbol, flip in signal_flips.items():
            direction = flip["direction"]          # "bull_flip" or "bear_flip"
            methods = flip["methods"]
            side = "long" if direction == "bull_flip" else "short"
            sig_name = "buy" if side == "long" else "sell"

            # Enrich from candidates if available
            candidate = bull_map.get(symbol) or bear_map.get(symbol) or {}
            conviction = candidate.get("conviction")
            score_delta = candidate.get("score_delta", 0)
            daily_return = candidate.get("daily_return")
            momentum = candidate.get("momentum")

            regime = regime_flips.get(symbol)
            regime_flip = regime is not None

            # Best-effort current price from yfinance
            price: float | None = None
            try:
                bars = data_provider.get_bars_yfinance(symbol, days=5)
                if not bars.empty:
                    price = round(float(bars["close"].iloc[-1]), 2)
            except Exception:
                pass

            # Human-readable action summary
            action_parts = [f"{'LONG' if side == 'long' else 'SHORT'}"]
            action_parts.append(f"methods: {', '.join(methods)}")
            if conviction is not None:
                action_parts.append(f"conviction {conviction:+.2f}")
            if score_delta:
                action_parts.append(f"Δscore {score_delta:+.0f}")
            if regime_flip:
                rrg = regime.get("rrg", 0)
                action_parts.append(f"regime {'▲' if rrg > 0 else '▼'} ({regime['date']})")
            action = " · ".join(action_parts) + " [analysis only]"

            signals.append({
                "symbol": symbol,
                "side": side,
                "signal": sig_name,
                "conviction": conviction,
                "score_delta": score_delta,
                "daily_return": daily_return,
                "momentum": momentum,
                "methods": methods,
                "regime_flip": regime_flip,
                "price": price,
                "rsi": None,
                "patterns": [],
                "action": action,
                "data_source": "yfinance",
                "timestamp": datetime.now().isoformat(),
            })

        summary = {
            "total": len(signals),
            "buy": sum(1 for s in signals if s["signal"] == "buy"),
            "sell": sum(1 for s in signals if s["signal"] == "sell"),
            "hold": 0,
            "brief_date": brief.get("date", ""),
        }
        result = {
            "status": "done", "name": name,
            "description": cfg.get("description", ""),
            "data_source": "yfinance",
            "brief_date": brief.get("date", ""),
            "last_run": datetime.now().isoformat(),
            "signals": signals, "summary": summary,
        }
        store.update_agent(name, result)
        return result

    except Exception as exc:
        err = {
            "status": "error", "name": name,
            "description": cfg.get("description", ""),
            "data_source": "yfinance",
            "error": str(exc),
            "last_run": datetime.now().isoformat(),
            "signals": [], "summary": {},
        }
        store.update_agent(name, err)
        return err


# ── Alpha / Beta / Gamma: SMA crossover + RSI ────────────────────────────────
def run_agent(cfg: dict, api_key: str, secret_key: str, dry_run: bool = True) -> dict:
    if cfg.get("brief_driven"):
        return run_delta_from_brief(cfg)

    name = cfg["name"]
    src = cfg.get("data_source", "alpaca")

    store.update_agent(name, {
        "status": "running", "name": name,
        "description": cfg.get("description", ""),
        "data_source": src,
        "last_run": datetime.now().isoformat(),
        "signals": [], "summary": {},
    })

    try:
        if src == "alpaca":
            trading_client, data_client = make_clients(api_key, secret_key)
            account = trading_client.get_account()
            equity = float(account.equity)
        else:
            trading_client = data_client = None
            equity = 100_000.0

        patterns = _techa_patterns(cfg["symbols"])
        signals: list[dict] = []

        for symbol in cfg["symbols"]:
            bars = data_provider.get_bars(symbol, data_source=src, data_client=data_client)
            if len(bars) < cfg["long_window"] + 1:
                signals.append({
                    "symbol": symbol, "side": "long",
                    "signal": "insufficient_data",
                    "rsi": None, "price": None, "action": "none",
                    "patterns": [], "data_source": src,
                    "timestamp": datetime.now().isoformat(),
                })
                continue

            sig = sma_crossover_signal(bars, cfg["short_window"], cfg["long_window"])
            rsi = compute_rsi(bars)
            price = round(float(bars["close"].iloc[-1]), 2)
            sym_patterns = patterns.get(symbol, [])

            action = "none"
            if src == "alpaca" and trading_client:
                position = get_position(trading_client, symbol)
                if sig == "buy" and position is None:
                    qty = qty_to_buy(bars, equity)
                    action = f"would BUY {qty} shares [dry run]" if dry_run else f"BUY {qty} shares"
                elif sig == "sell" and position is not None:
                    qty = abs(int(float(position.qty)))
                    action = f"would SELL {qty} shares [dry run]" if dry_run else f"SELL {qty} shares"
            else:
                if sig == "buy":
                    action = f"signal: BUY ~{qty_to_buy(bars, equity)} shares [analysis only]"
                elif sig == "sell":
                    action = "signal: SELL [analysis only]"

            signals.append({
                "symbol": symbol, "side": "long",
                "signal": sig, "rsi": round(rsi, 1), "price": price,
                "action": action, "patterns": sym_patterns,
                "data_source": src,
                "timestamp": datetime.now().isoformat(),
            })

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
                        "symbol": p.symbol, "qty": float(p.qty),
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
            "status": "done", "name": name,
            "description": cfg.get("description", ""),
            "data_source": src,
            "last_run": datetime.now().isoformat(),
            "signals": signals, "summary": summary,
        }
        store.update_agent(name, result)
        return result

    except Exception as exc:
        err = {
            "status": "error", "name": name,
            "description": cfg.get("description", ""),
            "data_source": src,
            "error": str(exc),
            "last_run": datetime.now().isoformat(),
            "signals": [], "summary": {},
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
