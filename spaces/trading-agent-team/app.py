"""
Trading Agent Team Dashboard — Streamlit

Run:  streamlit run app.py
API:  uvicorn api:app --host 0.0.0.0 --port 8000  (separate terminal)

Agents:
  Alpha / Beta / Gamma — US large-caps via Alpaca paper
  Delta               — Italian blue-chips via yfinance (deliverable 013 symbols)

Deep analysis powered by techa (deliverable 013): techa Orchestrator + Pattern agent.

DISCLAIMER: Paper trading only. This is not financial advice.
"""
import os
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

import agents as agent_module
import data_provider
import store
from strategy import add_sma_columns

st.set_page_config(page_title="Trading Agent Team", layout="wide", page_icon="📊")

# ── Header ────────────────────────────────────────────────────────────────────
st.title("📊 Trading Agent Team Dashboard")
st.caption(
    "⚠️ **DISCLAIMER:** Paper trading only. Not financial advice. "
    "Alpha/Beta/Gamma use Alpaca paper mode. Delta uses yfinance (Borsa Italiana)."
)

# ── Credentials ───────────────────────────────────────────────────────────────
try:
    api_key = st.secrets.get("ALPACA_API_KEY", "")
    secret_key = st.secrets.get("ALPACA_SECRET_KEY", "")
    openai_key = st.secrets.get("OPENAI_API_KEY", "")
except Exception:
    api_key = secret_key = openai_key = ""

api_key = api_key or os.environ.get("ALPACA_API_KEY", "")
secret_key = secret_key or os.environ.get("ALPACA_SECRET_KEY", "")
openai_key = openai_key or os.environ.get("OPENAI_API_KEY", "")
TRADING_API_KEY = os.environ.get("TRADING_API_KEY", "")

alpaca_ok = bool(api_key and secret_key)
if not alpaca_ok:
    st.warning(
        "Alpaca credentials not set — Alpha/Beta/Gamma agents will be skipped. "
        "Delta (yfinance) still works. "
        "Set `ALPACA_API_KEY` + `ALPACA_SECRET_KEY` in `.streamlit/secrets.toml` or env vars."
    )

# ── Techa availability ────────────────────────────────────────────────────────
_TECHA_ERROR: str = ""
try:
    from techa.agents.orchestrator import create_orchestrator as _techa_orch
    from techa.agents.patterns import create_pattern_agent as _techa_patterns
    _TECHA = True
except Exception as _e:
    _TECHA = False
    _TECHA_ERROR = f"{type(_e).__name__}: {_e}"

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Controls")
    dry_run = st.toggle("Dry run mode", value=True)
    run_all = st.button("▶ Run All Agents", type="primary", use_container_width=True)

    st.divider()
    st.subheader("Single Agent Run")
    agent_names = [cfg["name"] for cfg in agent_module.AGENT_CONFIGS]
    selected_agent = st.selectbox("Agent", agent_names)
    run_one = st.button(f"▶ Run Agent {selected_agent}", use_container_width=True)

    st.divider()
    st.subheader("Chart")
    all_symbols = [s for cfg in agent_module.AGENT_CONFIGS for s in cfg["symbols"]]
    chart_symbol = st.selectbox("Symbol", all_symbols)
    chart_short = st.slider("SMA short", 5, 50, 20)
    chart_long = st.slider("SMA long", 20, 200, 50)

    st.divider()
    st.subheader("Status")
    st.write(f"Alpaca: {'✅' if alpaca_ok else '❌'}")
    st.write(f"OpenAI: {'✅' if openai_key else '❌'}")
    st.write(f"techa: {'✅' if _TECHA else '❌'}")
    if TRADING_API_KEY:
        st.success("API key configured")
    else:
        st.warning("TRADING_API_KEY not set — API open")
    st.code("uvicorn api:app --port 8000", language="bash")

# ── Trigger runs ──────────────────────────────────────────────────────────────
if run_all:
    with st.spinner("Running all agents…"):
        agent_module.run_all_agents(api_key, secret_key, dry_run=dry_run)
    st.success("All agents completed.")
    st.rerun()

if run_one:
    cfg = next(c for c in agent_module.AGENT_CONFIGS if c["name"] == selected_agent)
    with st.spinner(f"Running agent {selected_agent}…"):
        agent_module.run_agent(cfg, api_key, secret_key, dry_run=dry_run)
    st.success(f"Agent {selected_agent} completed.")
    st.rerun()

# ── Load shared state ─────────────────────────────────────────────────────────
state = store.load()
portfolio = state.get("portfolio", {})
agents_state = state.get("agents", {})
analyses = state.get("analyses", {})
last_run = state.get("last_run")

# ── Portfolio KPIs (Alpaca only) ──────────────────────────────────────────────
st.subheader("Portfolio Overview")
if portfolio:
    pnl = portfolio.get("today_pnl", 0.0)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Equity", f"${portfolio.get('equity', 0):,.2f}")
    c2.metric("Cash", f"${portfolio.get('cash', 0):,.2f}")
    c3.metric("Buying Power", f"${portfolio.get('buying_power', 0):,.2f}")
    c4.metric("Today P&L", f"${pnl:+,.2f}", delta=f"{pnl:+.2f}")
    if last_run:
        st.caption(f"Last updated: {last_run[:19]}")
else:
    st.info("No portfolio data — run Alpha/Beta/Gamma agents to fetch Alpaca account state.")

st.divider()

# ── Agent Team Grid ───────────────────────────────────────────────────────────
st.subheader("Agent Team")
cols = st.columns(len(agent_module.AGENT_CONFIGS))
for col, cfg in zip(cols, agent_module.AGENT_CONFIGS):
    name = cfg["name"]
    src = cfg.get("data_source", "alpaca")
    data = agents_state.get(name, {})
    status = data.get("status", "idle")
    icon = {"done": "✅", "running": "⏳", "error": "❌", "idle": "💤"}.get(status, "❓")
    src_badge = "🇺🇸 Alpaca" if src == "alpaca" else "🌍 yfinance"
    summary = data.get("summary", {})

    with col:
        st.markdown(f"### {icon} Agent {name}")
        st.caption(f"{src_badge}")
        st.caption(cfg.get("description", ""))
        if cfg.get("brief_driven"):
            try:
                from brief_loader import fetch_brief as _fb
                _brief = _fb()
                _date = _brief.get("date", "")
                _err = _brief.get("error")
                if _err:
                    st.caption(f"⚠️ Brief unavailable: {_err}")
                else:
                    _flips = _brief.get("signal_flips", {})
                    _n_long = sum(1 for f in _flips.values() if f["direction"] == "bull_flip")
                    _n_short = sum(1 for f in _flips.values() if f["direction"] == "bear_flip")
                    st.caption(f"📋 Brief {_date} · ⚡ {len(_flips)} flips · 🟦 {_n_long} long · 🟥 {_n_short} short")
            except Exception:
                st.caption("📋 Brief: loading…")
        else:
            st.caption(f"Symbols: {', '.join(cfg['symbols'])}")
        if "short_window" in cfg:
            st.caption(f"SMA {cfg['short_window']}/{cfg['long_window']}")
        if summary:
            b = summary.get("buy", 0)
            s = summary.get("sell", 0)
            h = summary.get("hold", 0)
            st.markdown(f"🟢 **{b}** &nbsp;🔴 **{s}** &nbsp;⬜ **{h}**")
        if data.get("last_run"):
            st.caption(f"Last run: {data['last_run'][:19]}")
        if data.get("error"):
            st.error(data["error"])

st.divider()

# ── Aggregated Signal Table ───────────────────────────────────────────────────
st.subheader("Today's Signals")
all_sigs = agent_module.all_signals(state)
if all_sigs:
    rows = []
    for sig in all_sigs:
        signal = sig.get("signal", "")
        side = sig.get("side", "long")
        side_badge = "🟦 LONG" if side == "long" else "🟥 SHORT"
        if side == "long":
            emoji = "🟢" if signal == "buy" else "🔴" if signal == "sell" else "⬜"
        else:
            emoji = "🔴" if signal == "sell" else "🟢" if signal == "buy" else "⬜"

        # Delta-specific fields
        conviction = sig.get("conviction")
        methods = sig.get("methods", [])
        regime_flip = sig.get("regime_flip", False)
        daily_ret = sig.get("daily_return")

        pats = sig.get("patterns", [])
        pat_str = ", ".join(pats[:3]) + ("…" if len(pats) > 3 else "") if pats else "—"
        methods_str = ", ".join(methods) if methods else "—"

        rows.append({
            "Agent": sig.get("agent", ""),
            "Symbol": sig.get("symbol", ""),
            "Side": side_badge,
            "Signal": f"{emoji} {signal.upper()}",
            "Conviction": f"{conviction:+.2f}" if conviction is not None else "—",
            "Day %": f"{daily_ret:+.1%}" if daily_ret is not None else "—",
            "Methods": methods_str,
            "Regime ⚡": "✅" if regime_flip else "",
            "RSI": sig.get("rsi", "—") or "—",
            "Price": f"${sig['price']:.2f}" if sig.get("price") else "—",
            "Patterns": pat_str,
            "Action": sig.get("action", "none"),
            "Time": sig.get("timestamp", "")[:19],
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    if not _TECHA:
        st.caption("Install techa to populate the Patterns column (Alpha/Beta/Gamma only).")
else:
    st.info("No signals yet — click **Run All Agents** to generate signals.")

st.divider()

# ── Historical Signal Flips (myfinance2 daily_brief.txt git history) ──────────
st.subheader("Historical Signal Flips")
_n_days = st.slider("Days back", min_value=2, max_value=20, value=7, key="hist_days")

with st.spinner(f"Loading last {_n_days} briefs from myfinance2…"):
    try:
        from brief_loader import fetch_brief_history as _fbh
        _history = _fbh(n_days=_n_days)
    except Exception as _e:
        _history = []
        st.warning(f"Could not load history: {_e}")

if _history:
    _hist_rows = []
    for _brief in _history:
        _date = _brief.get("date", "—")
        _bull_map = {c["symbol"]: c for c in _brief.get("bull", [])}
        _bear_map = {c["symbol"]: c for c in _brief.get("bear", [])}
        _reg = _brief.get("regime_flips", {})
        for _sym, _flip in _brief.get("signal_flips", {}).items():
            _dir = _flip["direction"]
            _side = "long" if _dir == "bull_flip" else "short"
            _side_badge = "🟦 LONG" if _side == "long" else "🟥 SHORT"
            _methods = ", ".join(_flip["methods"])
            _cand = _bull_map.get(_sym) or _bear_map.get(_sym) or {}
            _conv = _cand.get("conviction")
            _dret = _cand.get("daily_return")
            _hist_rows.append({
                "Date": _date,
                "Symbol": _sym,
                "Side": _side_badge,
                "Signal": "🟢 BUY" if _side == "long" else "🔴 SELL",
                "Conviction": f"{_conv:+.2f}" if _conv is not None else "—",
                "Day %": f"{_dret:+.1%}" if _dret is not None else "—",
                "Methods": _methods,
                "Regime ⚡": "✅" if _sym in _reg else "",
            })
    if _hist_rows:
        st.dataframe(pd.DataFrame(_hist_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No signal flips found in the selected period.")
else:
    st.info("No historical data available.")

st.divider()

# ── Open Positions (Alpaca) ───────────────────────────────────────────────────
st.subheader("Open Positions (Alpaca)")
positions = portfolio.get("positions", [])
if positions:
    st.dataframe(
        pd.DataFrame([
            {
                "Symbol": p["symbol"],
                "Qty": p["qty"],
                "Entry": f"${p['entry_price']:.2f}",
                "Current": f"${p['current_price']:.2f}",
                "Market Value": f"${p['market_value']:,.2f}",
                "Unrealized P&L": f"${p['unrealized_pl']:+,.2f}",
                "P&L %": f"{p['unrealized_plpc']:+.2f}%",
            }
            for p in positions
        ]),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No open positions.")

st.divider()

# ── Candlestick Chart ─────────────────────────────────────────────────────────
st.subheader(f"{chart_symbol} — Price + SMA {chart_short}/{chart_long}")
try:
    src = data_provider.symbol_data_source(chart_symbol, agent_module.AGENT_CONFIGS)
    # For Alpaca symbols, use data_provider with an Alpaca data client if available
    if src == "alpaca" and alpaca_ok:
        from trader import make_clients
        _, _dc = make_clients(api_key, secret_key)
        bars = data_provider.get_bars(chart_symbol, data_source="alpaca", data_client=_dc)
    else:
        bars = data_provider.get_bars(chart_symbol, data_source="yfinance")

    bars = add_sma_columns(bars, chart_short, chart_long)
    time_col = next(
        (c for c in ["timestamp", "t", "date"] if c in bars.columns), bars.columns[0]
    )
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=bars[time_col], open=bars["open"], high=bars["high"],
        low=bars["low"], close=bars["close"], name="Price",
    ))
    fig.add_trace(go.Scatter(
        x=bars[time_col], y=bars["sma_short"],
        name=f"SMA {chart_short}", line=dict(color="orange", width=1.5),
    ))
    fig.add_trace(go.Scatter(
        x=bars[time_col], y=bars["sma_long"],
        name=f"SMA {chart_long}", line=dict(color="royalblue", width=1.5),
    ))
    fig.update_layout(xaxis_rangeslider_visible=False, height=480)
    st.plotly_chart(fig, use_container_width=True)
    st.caption(f"Data source: {src}")
except Exception as exc:
    st.warning(f"Chart unavailable: {exc}")

st.divider()

# ── Techa Deep Analysis ───────────────────────────────────────────────────────
st.subheader("🔬 Deep Analysis — techa Orchestrator")

# Collect all symbols: Delta signal-flip symbols first, then US symbols
_brief_symbols: list[str] = []
try:
    from brief_loader import fetch_brief as _fb2
    _b2 = _fb2()
    _brief_symbols = list(_b2.get("signal_flips", {}).keys())
except Exception:
    pass
_all_orch_symbols = _brief_symbols + all_symbols

def _benchmark_for(symbol: str) -> str:
    return "FTSEMIB.MI" if symbol.endswith(".MI") else "^GSPC"

if not _TECHA:
    st.error(f"techa import failed: `{_TECHA_ERROR}`")
    st.info("Requires TA-Lib C library + OpenAI.")
else:
    tab_run, tab_cache = st.tabs(["Run Analysis", "Cached Reports"])

    with tab_run:
        if not openai_key:
            st.warning("Set `OPENAI_API_KEY` in Space Secrets to run the Orchestrator.")
        else:
            os.environ["OPENAI_API_KEY"] = openai_key
            t_sym = st.selectbox("Symbol", _all_orch_symbols, key="t_sym")
            t_bm = _benchmark_for(t_sym)
            t_lb = st.slider("Lookback days", 90, 730, 365, key="t_lb")
            st.caption(f"Benchmark: `{t_bm}` · data source: live (yfinance)")
            t_run = st.button("▶ Run techa Orchestrator", type="primary", key="t_btn")

            if t_run:
                with st.spinner(
                    f"Running Orchestrator on {t_sym} — "
                    "indicators + patterns + ta in parallel…"
                ):
                    try:
                        graph = _techa_orch(
                            symbol=t_sym,
                            data_source="live",
                            benchmark=t_bm,
                            lookback_days=t_lb,
                            relative=False,
                        )
                        result = graph.invoke(graph._initial_state)
                        report = result.get("final_output", "")
                        store.update_analysis(t_sym, {
                            "symbol": t_sym,
                            "report": report,
                            "benchmark": t_bm,
                            "lookback_days": t_lb,
                        })
                        if report:
                            st.markdown(report)
                        with st.expander("Raw output"):
                            st.json({k: v for k, v in result.items() if k != "final_output"})
                    except Exception as exc:
                        st.error(f"techa failed: {type(exc).__name__}: {exc}")

    with tab_cache:
        if not analyses:
            st.info("No cached reports yet — run an analysis above.")
        else:
            for sym, data in analyses.items():
                with st.expander(f"**{sym}** — {data.get('cached_at', '')[:19]}"):
                    if data.get("report"):
                        st.markdown(data["report"])
                    else:
                        st.json(data)

st.divider()

# ── Sector Context (lacetohf/sector-analysis) ─────────────────────────────────
st.subheader("🌐 Sector Context")
try:
    import sector_context as _sc
    rows, is_fresh, latest_date = _sc.load_sector_context()
    if rows:
        if not is_fresh:
            st.warning(
                f"⚠️ Sector data is stale (latest: {latest_date}). "
                "The rss_feed pipeline may not have run recently."
            )
        else:
            st.caption(f"Source: `lacetohf/sector-analysis` — snapshot {latest_date}")
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No sector data available in lacetohf/sector-analysis yet.")
except ImportError:
    st.info(
        "Install `datasets` to enable the Sector Context panel:\n"
        "```bash\npip install datasets\n```"
    )
except Exception as exc:
    st.warning(f"Sector context unavailable: {exc}")

st.divider()

# ── API Reference ─────────────────────────────────────────────────────────────
with st.expander("REST API Reference"):
    st.markdown("""
```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Liveness + state summary |
| `GET` | `/api/agents` | All agent statuses |
| `GET` | `/api/agents/{name}` | Single agent + config |
| `GET` | `/api/signals` | All signals (`?signal=buy`, `?source=yfinance`) |
| `GET` | `/api/portfolio` | Alpaca paper portfolio |
| `GET` | `/api/positions` | Open positions |
| `POST` | `/api/run` | Trigger strategy run |
| `GET` | `/api/analyses` | List cached techa reports |
| `GET` | `/api/analysis/{symbol}` | Run/fetch techa Orchestrator report (`?refresh=true`) |

**Auth:** `X-API-Key: <TRADING_API_KEY>` header.

**POST /api/run:**
```json
{"agent": "Delta", "dry_run": true}
```
Omit `agent` to run all four. Delta works without Alpaca credentials.
""")
