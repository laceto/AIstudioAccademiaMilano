# Deliverable 008 — Algo Trading Bot (SMA Crossover, Alpaca Paper)

> Purpose: Entry-level algorithmic trading system using Alpaca paper trading. SMA crossover strategy with CLI runner and Streamlit dashboard.
> Owner Agent: Chiara (Implementation) + Marco (Finance Review)
> Status: active

> ⚠️ **DISCLAIMER:** This software does not constitute regulated financial advice. It is based on AI knowledge and general business principles. Use only with Alpaca paper trading accounts. Real-money trading requires your own due diligence and risk management. AI Studio accepts no liability.

---

## What you get

| File | Purpose |
|---|---|
| `strategy.py` | Pure SMA crossover + RSI logic (no API calls) |
| `trader.py` | Alpaca execution layer — fetches bars, checks positions, submits orders |
| `main.py` | CLI runner: shows signals or executes paper orders |
| `dashboard.py` | Streamlit dashboard: account, positions, signals, candlestick chart |
| `requirements.txt` | Python dependencies |

---

## Setup

### 1. Get Alpaca paper trading keys

Sign up free at [alpaca.markets](https://alpaca.markets) → Paper Trading → API Keys.

### 2. Set credentials

**Option A — env vars:**
```bash
export ALPACA_API_KEY=your_key
export ALPACA_SECRET_KEY=your_secret
```

**Option B — Streamlit secrets** (for dashboard):
```toml
# .streamlit/secrets.toml
ALPACA_API_KEY = "your_key"
ALPACA_SECRET_KEY = "your_secret"
```

### 3. Install
```bash
pip install -r requirements.txt
```

---

## Run

### See signals only (no orders)
```bash
python main.py
```

### Execute paper orders
```bash
python main.py --live
```

### Custom symbols and SMA windows
```bash
python main.py --symbols TSLA META AMD --short 10 --long 30 --live
```

### Streamlit dashboard
```bash
streamlit run dashboard.py
```

---

## Strategy

**SMA Crossover (default: 20/50)**

| Event | Signal | Action |
|---|---|---|
| SMA20 crosses **above** SMA50 (Golden Cross) | `buy` | Open position if none exists |
| SMA20 crosses **below** SMA50 (Death Cross) | `sell` | Close position if one exists |
| No crossover | `hold` | Do nothing |

Position sizing: **5% of portfolio equity** per symbol (`POSITION_SIZE_PCT` in `trader.py`).

Default symbols: AAPL, MSFT, GOOGL, NVDA, AMZN.

`paper=True` is hardcoded in `trader.py` — you cannot accidentally trade real money.

---

## Customise

Change position size in `trader.py`:
```python
POSITION_SIZE_PCT = 0.05  # 5% of portfolio per position
```

Adjust SMA windows via CLI flags or the Streamlit sidebar sliders.

Add your own strategy in `strategy.py` — just return `'buy'`, `'sell'`, or `'hold'`.

---

## SDK reference

[alpaca-py on GitHub](https://github.com/alpacahq/alpaca-py)
