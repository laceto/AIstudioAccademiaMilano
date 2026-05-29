---
title: Trading Agent Team
emoji: 📊
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
license: other
short_description: US + Italian market trading signals (paper trading only)
---

# Trading Agent Team Dashboard

Four named agents covering US and Italian markets using SMA crossover + RSI signals.

| Agent | Market | Symbols | Data source |
|---|---|---|---|
| Alpha | US large-cap tech | AAPL, MSFT, GOOGL | Alpaca paper |
| Beta | US semiconductors & EV | NVDA, AMD, TSLA | Alpaca paper |
| Gamma | US internet mega-cap | AMZN, META | Alpaca paper |
| **Delta** | **Italian blue-chips** | **ENI.MI, A2A.MI, PST.MI** | **yfinance (no creds needed)** |

**Delta works without any credentials** — yfinance pulls Borsa Italiana data freely.
Alpha/Beta/Gamma require Alpaca paper trading credentials (set as Space secrets).

## Secrets (optional)

| Secret | Purpose |
|---|---|
| `ALPACA_API_KEY` | Enables Alpha/Beta/Gamma agents |
| `ALPACA_SECRET_KEY` | Enables Alpha/Beta/Gamma agents |
| `OPENAI_API_KEY` | Enables techa deep-analysis panel |

## Disclaimer

⚠️ **Paper trading only. Not financial advice.**
All orders use Alpaca's paper (simulated) mode. No real capital is involved.
