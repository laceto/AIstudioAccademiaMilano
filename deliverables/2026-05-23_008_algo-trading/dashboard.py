"""
Streamlit dashboard — SMA Crossover Algo Trading (Alpaca Paper)

DISCLAIMER: This software does not constitute regulated financial advice.
It is based on AI knowledge and general business principles.
Paper trading only.
"""
import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.trading.client import TradingClient

from strategy import add_sma_columns, compute_rsi, sma_crossover_signal
from trader import get_bars, get_position, run_strategy

st.set_page_config(page_title="Algo Trading — SMA", layout="wide")
st.title("📈 Algo Trading Dashboard — SMA Crossover (Paper)")
st.warning(
    "⚠️ **DISCLAIMER:** This software does not constitute regulated financial advice. "
    "It is based on AI knowledge and general business principles. "
    "Paper trading only — do not use real capital without understanding the risks."
)

# Credentials
try:
    api_key = st.secrets["ALPACA_API_KEY"]
    secret_key = st.secrets["ALPACA_SECRET_KEY"]
except (KeyError, FileNotFoundError):
    api_key = os.environ.get("ALPACA_API_KEY", "")
    secret_key = os.environ.get("ALPACA_SECRET_KEY", "")

if not api_key or not secret_key:
    st.error(
        "Set `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` in `.streamlit/secrets.toml` or env vars."
    )
    st.stop()

trading_client = TradingClient(api_key, secret_key, paper=True)
data_client = StockHistoricalDataClient(api_key, secret_key)

# Sidebar
with st.sidebar:
    st.header("Settings")
    symbols = st.multiselect(
        "Symbols",
        ["AAPL", "MSFT", "GOOGL", "NVDA", "AMZN", "TSLA", "META", "AMD"],
        default=["AAPL", "MSFT", "GOOGL", "NVDA", "AMZN"],
    )
    short_window = st.slider("SMA Short", 5, 50, 20)
    long_window = st.slider("SMA Long", 20, 200, 50)
    chart_symbol = st.selectbox("Chart symbol", symbols) if symbols else None
    run_btn = st.button("▶ Run Strategy (dry run)", type="primary")

# Account overview
account = trading_client.get_account()
pnl = float(account.equity) - float(account.last_equity)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Portfolio Value", f"${float(account.portfolio_value):,.2f}")
c2.metric("Cash", f"${float(account.cash):,.2f}")
c3.metric("Buying Power", f"${float(account.buying_power):,.2f}")
c4.metric("Today P&L", f"${pnl:+,.2f}", delta=f"{pnl:+.2f}")

st.divider()

# Open positions
st.subheader("Open Positions")
positions = trading_client.get_all_positions()
if positions:
    pos_df = pd.DataFrame(
        [
            {
                "Symbol": p.symbol,
                "Qty": p.qty,
                "Entry": f"${float(p.avg_entry_price):.2f}",
                "Current": f"${float(p.current_price):.2f}",
                "Market Value": f"${float(p.market_value):,.2f}",
                "Unrealized P&L": f"${float(p.unrealized_pl):+,.2f}",
                "P&L %": f"{float(p.unrealized_plpc) * 100:+.2f}%",
            }
            for p in positions
        ]
    )
    st.dataframe(pos_df, use_container_width=True, hide_index=True)
else:
    st.info("No open positions")

st.divider()

# Signals
st.subheader("Current Signals")
if symbols:
    rows = []
    for sym in symbols:
        bars = get_bars(data_client, sym)
        if len(bars) < long_window + 1:
            rows.append({"Symbol": sym, "Signal": "⬜ WAIT", "RSI": "N/A", "Last Close": "N/A", "Has Position": ""})
            continue
        sig = sma_crossover_signal(bars, short_window, long_window)
        rsi = compute_rsi(bars)
        emoji = "🟢" if sig == "buy" else "🔴" if sig == "sell" else "⬜"
        has_pos = get_position(trading_client, sym) is not None
        rows.append(
            {
                "Symbol": sym,
                "Signal": f"{emoji} {sig.upper()}",
                "RSI": f"{rsi:.1f}",
                "Last Close": f"${float(bars['close'].iloc[-1]):.2f}",
                "Has Position": "✓" if has_pos else "",
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# Candlestick chart
if chart_symbol:
    st.divider()
    st.subheader(f"{chart_symbol} — Price + SMA {short_window}/{long_window}")
    bars = add_sma_columns(get_bars(data_client, chart_symbol), short_window, long_window)
    time_col = next((c for c in ["timestamp", "t", "date"] if c in bars.columns), bars.columns[0])
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
        go.Scatter(x=bars[time_col], y=bars["sma_short"], name=f"SMA {short_window}", line=dict(color="orange", width=1.5))
    )
    fig.add_trace(
        go.Scatter(x=bars[time_col], y=bars["sma_long"], name=f"SMA {long_window}", line=dict(color="royalblue", width=1.5))
    )
    fig.update_layout(xaxis_rangeslider_visible=False, height=480)
    st.plotly_chart(fig, use_container_width=True)

# Dry-run execution
if run_btn and symbols:
    st.divider()
    st.subheader("Dry Run Results")
    results = run_strategy(api_key, secret_key, symbols, dry_run=True, short_window=short_window, long_window=long_window)
    for r in results:
        st.write(f"**{r['symbol']}** — signal: `{r['signal']}` | RSI: {r['rsi']} | _{r['action']}_")
