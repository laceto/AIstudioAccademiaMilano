# techa — Streamlit front-end

Deploys the [laceto/techa](https://github.com/laceto/techa) trading agents as an interactive Streamlit app.

Four agents exposed in the sidebar:

| Agent | Purpose |
|---|---|
| **Orchestrator** | Runs indicators + patterns + TA in parallel, synthesises a GPT-4o report |
| **Indicator** | Trend / momentum / volatility snapshot from OHLCV |
| **TA** | MA crossover + range breakout vs benchmark |
| **Pattern** | Scans tickers for 61 TA-Lib candlestick patterns |

## Credentials

| Variable | Where to get it | Required |
|---|---|---|
| `OPENAI_API_KEY` | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) | Yes |

Provide it via `.streamlit/secrets.toml` or env var:

```toml
OPENAI_API_KEY = "sk-..."
```

## System dependency: TA-Lib

`techa` depends on the **TA-Lib C library**, which is not pip-installable on its own.

### Local (macOS / Linux)

```bash
# macOS
brew install ta-lib
# Debian / Ubuntu
sudo apt install ta-lib
```

Then:

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...
streamlit run main.py
```

### Docker (recommended for production)

A `Dockerfile` is included that builds TA-Lib from source:

```bash
docker build -t techa-streamlit .
docker run -p 8501:8501 -e OPENAI_API_KEY=sk-... techa-streamlit
```

Works on any container host: Render, Railway, Fly.io, Cloud Run, Fargate.

### Streamlit Community Cloud

`packages.txt` includes `ta-lib`. If the apt package is unavailable in the
runtime image, fall back to a host that runs the `Dockerfile` (e.g. Render).

## Usage

1. Pick an agent in the sidebar.
2. Enter a ticker (Yahoo Finance format, e.g. `PST.MI`, `AAPL`, `TSLA`).
3. Adjust lookback, benchmark, signal filter.
4. Press **Run agent** — the markdown report renders inline, with the raw
   LangGraph state collapsed in an expander.

## Files

```
main.py            # Streamlit app
requirements.txt   # Python deps (installs techa from git)
packages.txt       # apt packages for Streamlit Cloud
Dockerfile         # Production-ready container w/ TA-Lib from source
```

## Disclaimer

Automated technical analysis output. Not investment advice — validate every
signal against independent research before trading.
