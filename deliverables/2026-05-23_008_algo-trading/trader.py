import os
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

from strategy import sma_crossover_signal, compute_rsi

# 5% of portfolio equity allocated per position
POSITION_SIZE_PCT = 0.05


def _make_clients(api_key: str, secret_key: str) -> tuple:
    trading = TradingClient(api_key, secret_key, paper=True)  # always paper
    data = StockHistoricalDataClient(api_key, secret_key)
    return trading, data


def get_bars(
    data_client: StockHistoricalDataClient, symbol: str, days: int = 120
) -> pd.DataFrame:
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


def _qty_to_buy(bars: pd.DataFrame, equity: float) -> int:
    if bars.empty:
        return 0
    price = float(bars["close"].iloc[-1])
    return max(int(equity * POSITION_SIZE_PCT / price), 1)


def run_strategy(
    api_key: str,
    secret_key: str,
    symbols: list,
    dry_run: bool = True,
    short_window: int = 20,
    long_window: int = 50,
) -> list:
    trading_client, data_client = _make_clients(api_key, secret_key)
    account = trading_client.get_account()
    equity = float(account.equity)
    results = []

    for symbol in symbols:
        bars = get_bars(data_client, symbol)
        if len(bars) < long_window + 1:
            results.append(
                {"symbol": symbol, "signal": "insufficient_data", "action": "none", "rsi": None}
            )
            continue

        signal = sma_crossover_signal(bars, short_window, long_window)
        rsi = compute_rsi(bars)
        position = get_position(trading_client, symbol)
        action = "none"

        if signal == "buy" and position is None:
            qty = _qty_to_buy(bars, equity)
            if not dry_run and qty > 0:
                order = trading_client.submit_order(
                    MarketOrderRequest(
                        symbol=symbol, qty=qty, side=OrderSide.BUY, time_in_force=TimeInForce.DAY
                    )
                )
                action = f"BUY {qty} shares (order {order.id[:8]}...)"
            else:
                action = f"would BUY {qty} shares [dry run]"

        elif signal == "sell" and position is not None:
            qty = abs(int(float(position.qty)))
            if not dry_run and qty > 0:
                order = trading_client.submit_order(
                    MarketOrderRequest(
                        symbol=symbol, qty=qty, side=OrderSide.SELL, time_in_force=TimeInForce.DAY
                    )
                )
                action = f"SELL {qty} shares (order {order.id[:8]}...)"
            else:
                action = f"would SELL {qty} shares [dry run]"

        results.append({"symbol": symbol, "signal": signal, "action": action, "rsi": round(rsi, 1)})

    return results
