"""Alpaca paper-trading client utilities. paper=True is hardcoded — no real capital."""
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

POSITION_SIZE_PCT = 0.05


def make_clients(api_key: str, secret_key: str) -> tuple:
    trading = TradingClient(api_key, secret_key, paper=True)
    data = StockHistoricalDataClient(api_key, secret_key)
    return trading, data


def get_bars(data_client: StockHistoricalDataClient, symbol: str, days: int = 120) -> pd.DataFrame:
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


def get_position(trading_client: TradingClient, symbol: str) -> Optional[object]:
    try:
        return trading_client.get_open_position(symbol)
    except Exception:
        return None


def qty_to_buy(bars: pd.DataFrame, equity: float) -> int:
    if bars.empty:
        return 0
    price = float(bars["close"].iloc[-1])
    return max(int(equity * POSITION_SIZE_PCT / price), 1)
