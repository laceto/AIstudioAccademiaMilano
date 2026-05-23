import pandas as pd


def sma_crossover_signal(
    bars: pd.DataFrame, short_window: int = 20, long_window: int = 50
) -> str:
    """SMA crossover signal. Returns 'buy', 'sell', or 'hold'."""
    if len(bars) < long_window + 1:
        return "hold"
    close = bars["close"]
    sma_short = close.rolling(short_window).mean()
    sma_long = close.rolling(long_window).mean()
    curr_short, curr_long = sma_short.iloc[-1], sma_long.iloc[-1]
    prev_short, prev_long = sma_short.iloc[-2], sma_long.iloc[-2]
    if prev_short <= prev_long and curr_short > curr_long:
        return "buy"
    if prev_short >= prev_long and curr_short < curr_long:
        return "sell"
    return "hold"


def compute_rsi(bars: pd.DataFrame, period: int = 14) -> float:
    """Returns the latest RSI value (0-100)."""
    close = bars["close"]
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, float("inf"))
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1])


def add_sma_columns(
    bars: pd.DataFrame, short_window: int = 20, long_window: int = 50
) -> pd.DataFrame:
    """Returns a copy of bars with sma_short and sma_long columns."""
    bars = bars.copy()
    bars["sma_short"] = bars["close"].rolling(short_window).mean()
    bars["sma_long"] = bars["close"].rolling(long_window).mean()
    return bars
