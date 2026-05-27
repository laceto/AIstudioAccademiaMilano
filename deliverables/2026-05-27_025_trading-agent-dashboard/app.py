"""
Trading Agent Team Dashboard — Streamlit

Run:  streamlit run app.py
API:  uvicorn api:app --host 0.0.0.0 --port 8000  (separate terminal)

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
import store
from strategy import add_sma_columns
from trader import get_bars, make_clients

st.set_page_config(page_title="Trading Agent Team", layout="wide", page_icon="📊")

# ── Header ────────────────────────────────────────────────────────────────────
st.title("📊 Trading Agent Team Dashboard")
st.caption(
    "⚠️ **DISCLAIMER:** Paper trading only. This is not financial advice. "
    "All orders use Alpaca paper mode — no real capital is at risk."
)

# ── Credentials ───────────────────────────────────────────────────────────────
try:
    api_key = st.secrets["ALPACA_API_KEY"]
    secret_key = st.secrets["ALPACA_SECRET_KEY"]
except (KeyError, FileNotFoundError):
    api_key = os.environ.get("ALPACA_API_KEY", "")
    secret_key = os.environ.get("ALPACA_SECRET_KEY", "")

TRADING_API_KEY = os.environ.get("TRADING_API_KEY", "")

if not api_key or not secret_key:
    st.error(
        "Set `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` in `.streamlit/secrets.toml` or env vars."
    )
    st.stop()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Controls")
    dry_run = st.toggle("Dry run mode", value=True, help="No real orders are submitted in dry run")
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
    chart_short = st.slider("SMA short window", 5, 50, 20)
    chart_long = st.slider("SMA long window", 20, 200, 50)

    st.divider()
    st.subheader("API Status")
    if TRADING_API_KEY:
        st.success("API key configured")
    else:
        st.warning("TRADING_API_KEY not set — API has no auth")
    st.code("uvicorn api:app --host 0.0.0.0 --port 8000", language="bash")
    st.caption("Docs → http://localhost:8000/docs")

# ── Trigger runs ──────────────────────────────────────────────────────────────
if run_all:
    with st.spinner("Running all agents — fetching Alpaca data..."):
        agent_module.run_all_agents(api_key, secret_key, dry_run=dry_run)
    st.success("All agents completed.")
    st.rerun()

if run_one:
    cfg = next(c for c in agent_module.AGENT_CONFIGS if c["name"] == selected_agent)
    with st.spinner(f"Running agent {selected_agent}..."):
        agent_module.run_agent(cfg, api_key, secret_key, dry_run=dry_run)
    st.success(f"Agent {selected_agent} completed.")
    st.rerun()

# ── Load shared state ─────────────────────────────────────────────────────────
state = store.load()
portfolio = state.get("portfolio", {})
agents_state = state.get("agents", {})
last_run = state.get("last_run")

# ── Portfolio KPIs ────────────────────────────────────────────────────────────
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
    st.info("No portfolio data yet — click **Run All Agents** to fetch account state.")

st.divider()

# ── Agent Status Grid ─────────────────────────────────────────────────────────
st.subheader("Agent Team")
cols = st.columns(len(agent_module.AGENT_CONFIGS))
for col, cfg in zip(cols, agent_module.AGENT_CONFIGS):
    name = cfg["name"]
    data = agents_state.get(name, {})
    status = data.get("status", "idle")
    icon = {"done": "✅", "running": "⏳", "error": "❌", "idle": "💤"}.get(status, "❓")
    summary = data.get("summary", {})

    with col:
        st.markdown(f"### {icon} Agent {name}")
        st.caption(cfg.get("description", ""))
        st.caption(f"Symbols: {', '.join(cfg['symbols'])}")
        st.caption(f"SMA {cfg['short_window']}/{cfg['long_window']}")
        if summary:
            b = summary.get("buy", 0)
            s = summary.get("sell", 0)
            h = summary.get("hold", 0)
            st.markdown(f"🟢 **{b}** buy &nbsp; 🔴 **{s}** sell &nbsp; ⬜ **{h}** hold")
        if data.get("last_run"):
            st.caption(f"Last run: {data['last_run'][:19]}")
        if data.get("error"):
            st.error(data["error"])

st.divider()

# ── Aggregated Signals Table ──────────────────────────────────────────────────
st.subheader("All Signals")
all_sigs = agent_module.all_signals(state)
if all_sigs:
    rows = []
    for sig in all_sigs:
        signal = sig.get("signal", "")
        emoji = "🟢" if signal == "buy" else "🔴" if signal == "sell" else "⬜"
        rows.append({
            "Agent": sig.get("agent", ""),
            "Symbol": sig.get("symbol", ""),
            "Signal": f"{emoji} {signal.upper()}",
            "RSI": sig.get("rsi", ""),
            "Price": f"${sig['price']:.2f}" if sig.get("price") else "N/A",
            "Action": sig.get("action", "none"),
            "Timestamp": sig.get("timestamp", "")[:19],
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    st.info("No signals yet — run agents to generate signals.")

st.divider()

# ── Open Positions ────────────────────────────────────────────────────────────
st.subheader("Open Positions")
positions = portfolio.get("positions", [])
if positions:
    pos_rows = [
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
    ]
    st.dataframe(pd.DataFrame(pos_rows), use_container_width=True, hide_index=True)
else:
    st.info("No open positions.")

st.divider()

# ── Candlestick Chart ─────────────────────────────────────────────────────────
st.subheader(f"{chart_symbol} — Price + SMA {chart_short}/{chart_long}")
try:
    _, data_client = make_clients(api_key, secret_key)
    bars = add_sma_columns(get_bars(data_client, chart_symbol), chart_short, chart_long)
    time_col = next(
        (c for c in ["timestamp", "t", "date"] if c in bars.columns), bars.columns[0]
    )
    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=bars[time_col],
            open=bars["open"],
            high=bars["high"],
            low=bars["low"],
            close=bars["close"],
            name="Price",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=bars[time_col],
            y=bars["sma_short"],
            name=f"SMA {chart_short}",
            line=dict(color="orange", width=1.5),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=bars[time_col],
            y=bars["sma_long"],
            name=f"SMA {chart_long}",
            line=dict(color="royalblue", width=1.5),
        )
    )
    fig.update_layout(xaxis_rangeslider_visible=False, height=480)
    st.plotly_chart(fig, use_container_width=True)
except Exception as exc:
    st.warning(f"Chart unavailable: {exc}")

st.divider()

# ── API Reference ─────────────────────────────────────────────────────────────
with st.expander("REST API Reference"):
    st.markdown("""
**Start the API server (separate terminal):**
```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Liveness probe |
| `GET` | `/api/agents` | All agent statuses + summaries |
| `GET` | `/api/agents/{name}` | Single agent detail + config |
| `GET` | `/api/signals` | All signals (`?signal=buy\|sell\|hold` to filter) |
| `GET` | `/api/portfolio` | Portfolio snapshot (equity, cash, P&L) |
| `GET` | `/api/positions` | Open positions |
| `POST` | `/api/run` | Trigger strategy run |

**Authentication:** `X-API-Key: <value>` header — set `TRADING_API_KEY` env var.

**POST /api/run payload:**
```json
{"agent": "Alpha", "dry_run": true}
```
Omit `agent` to run all three agents.

**Interactive docs:** http://localhost:8000/docs
""")
