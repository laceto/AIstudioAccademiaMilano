---
title: techa
emoji: 📈
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 8501
pinned: false
license: mit
short_description: LangGraph trading agents for technical analysis (TA-Lib + GPT-4o)
---

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

The app reads it from either `st.secrets` or the `OPENAI_API_KEY` environment variable.

---

## Deploy to Hugging Face Spaces (recommended)

The frontmatter above is the Space config — HF reads it on push. Steps:

1. **Create the Space.** [huggingface.co/new-space](https://huggingface.co/new-space) → name it `techa`, choose **Docker** as SDK, **Blank** template. Owner = `laceto` (or your HF user/org).
2. **Add the secret.** Space → Settings → *Variables and secrets* → New secret → `OPENAI_API_KEY = sk-...`. HF injects it as an env var into the container.
3. **Push these files** (everything in this folder) to the Space's git remote:
   ```bash
   cd deliverables/2026-05-24_013_techa-streamlit
   git init && git add . && git commit -m "init techa space"
   git remote add space https://huggingface.co/spaces/laceto/techa
   git push space main
   ```
4. **Wait for build** (~3–5 min cold — TA-Lib compiles from source on first build, then cached). The Space URL will be `https://huggingface.co/spaces/laceto/techa`.

Free CPU tier is enough — yfinance fetches + a single GPT-4o call per run.

---

## Other deploy paths

### Local (macOS / Linux)

Install TA-Lib first:

```bash
brew install ta-lib              # macOS
sudo apt install ta-lib          # Debian / Ubuntu (if available)
```

Then:

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...
streamlit run main.py
```

### Docker (Render / Railway / Fly.io)

Same Dockerfile works on any container host:

```bash
docker build -t techa-streamlit .
docker run -p 8501:8501 -e OPENAI_API_KEY=sk-... techa-streamlit
```

### Google Cloud Run

The Dockerfile honours `$PORT` (Cloud Run injects it), so no image changes are needed.

```bash
# 1. Store the OpenAI key in Secret Manager (one-off):
printf "sk-..." | gcloud secrets create openai-key --data-file=-

# 2. Deploy from source — Cloud Build picks up the Dockerfile:
gcloud run deploy techa \
  --source . \
  --region europe-west1 \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300 \
  --session-affinity \
  --allow-unauthenticated \
  --set-secrets OPENAI_API_KEY=openai-key:latest
```

Notes:
- **`--session-affinity`** is important — Streamlit uses WebSockets, and without affinity reconnects can bounce across instances.
- **`--memory 1Gi`** — the 512 MiB default is tight once TA-Lib, yfinance and the LangGraph runtime are loaded.
- **`--timeout 300`** — orchestrator runs can take 30–60 s; the 5-min cap leaves headroom.
- Cold start is ~2–4 s (image is already built; TA-Lib compile happens at *build* time, not runtime).
- Free tier: 2 M requests/month, 360 k vCPU-seconds.

### Streamlit Community Cloud

Not supported out of the box — `ta-lib` is not in the runtime's apt repos.
Use HF Spaces or a Docker host instead.

---

## Usage

1. Pick an agent in the sidebar.
2. Enter a ticker (Yahoo Finance format, e.g. `PST.MI`, `AAPL`, `TSLA`).
3. Adjust lookback, benchmark, signal filter.
4. Press **Run agent** — the markdown report renders inline, raw LangGraph state in an expander.

## Files

```
main.py            # Streamlit app
requirements.txt   # Python deps (installs techa from git)
packages.txt       # apt packages (best-effort, for non-Docker hosts)
Dockerfile         # Production-ready container, TA-Lib built from source
README.md          # This file + HF Spaces frontmatter
```

## Disclaimer

Automated technical analysis output. Not investment advice — validate every signal against independent research before trading.
