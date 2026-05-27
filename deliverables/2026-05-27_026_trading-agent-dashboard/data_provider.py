"""
Unified OHLCV bar provider — Alpaca paper or yfinance.

AGENT_CONFIGS["data_source"] controls which backend each agent uses:
  "alpaca"   — requires Alpaca credentials, US markets only
  "yfinance" — free, no credentials, covers global markets (use for .MI, .DE, etc.)

Falls back to yfinance automatically when data_client is None, so yfinance agents
work even when Alpaca credentials are absent.
"""
from datetime import datetime, timedelta

import pandas as pd


def get_bars_yfinance(symbol: str, days: int = 120) -> pd.DataFrame:
    try:
        import yfinance as yf
    except ImportError:
        raise ImportError("yfinance not installed — run: pip install yfinance>=0.2")

    end = datetime.now()
    start = end - timedelta(days=days)
    raw = yf.download(symbol, start=start, end=end, progress=False, auto_adjust=True)
    if raw.empty:
        return pd.DataFrame()

    # yfinance can return MultiIndex columns for a single ticker
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    raw.columns = [c.lower() for c in raw.columns]
    raw = raw.reset_index()
    raw = raw.rename(columns={"date": "timestamp", "Date": "timestamp"})
    wanted = [c for c in ["timestamp", "open", "high", "low", "close", "volume"] if c in raw.columns]
    return raw[wanted]


def get_bars_alpaca(data_client, symbol: str, days: int = 120) -> pd.DataFrame:
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    request = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Day,
        start=datetime.now() - timedelta(days=days),
        end=datetime.now(),
    )
    bars = data_client.get_stock_bars(request).df
    if isinstance(bars.index, pd.MultiIndex):
        bars = bars.loc[symbol]
    return bars.reset_index()


def get_bars(
    symbol: str,
    days: int = 120,
    data_source: str = "alpaca",
    data_client=None,
) -> pd.DataFrame:
    """Fetch OHLCV bars, routing to Alpaca or yfinance based on data_source."""
    if data_source == "yfinance" or data_client is None:
        return get_bars_yfinance(symbol, days)
    return get_bars_alpaca(data_client, symbol, days)


def symbol_data_source(symbol: str, agent_configs: list[dict]) -> str:
    """Return the data_source for a given symbol by looking it up in agent configs."""
    for cfg in agent_configs:
        if symbol in cfg.get("symbols", []):
            return cfg.get("data_source", "alpaca")
    return "alpaca"
