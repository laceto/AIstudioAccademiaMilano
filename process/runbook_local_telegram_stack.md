# Runbook — Running the Telegram Stack Locally

**Status:** active plan, replaces Railway hosting
**Context:** the Railway trial expired; all three services went offline on 2026-07-10.
Rollback is gone (24h image retention on Trial), so this is a fresh start from source.
Nothing was lost — no volumes were attached, and the FAISS vectorstore is committed
to the repo at `data/vectorstore/repo/`.

---

## Why local actually works here

Telegram bots can run in one of two modes:

| Mode | Needs a public HTTPS URL? | Used by |
|------|---------------------------|---------|
| **Webhook** — Telegram POSTs to you | **Yes** | `gateway/api.py`, `scripts/rag/api_server.py` |
| **Polling** — you call `getUpdates` | **No** | `gateway/bot_telegram.py`, `gateway/rag_bot_telegram.py` |

The repo already has a **polling bot for both channels**. So the whole stack runs on a
laptop with **no public URL, no ngrok, no port forwarding, no inbound firewall rules** —
every connection is outbound. This is why local is a genuinely reasonable choice here and
not just a downgrade.

```
                    ┌─────────────────── your laptop ───────────────────┐
                    │                                                    │
Telegram ──poll──►  │  gateway/bot_telegram.py ──► gateway/queue/*.json  │
   ▲                │                                      │             │
   │                │                              gateway/worker.py     │
   └───sendMessage──┼──────────────────────────────────────┘             │
                    │                                                    │
Telegram ──poll──►  │  gateway/rag_bot_telegram.py ──http──► :8000       │
   ▲                │                                  scripts/rag/      │
   └───reply────────┼──────────────────────────────────  api_server.py   │
                    └────────────────────────────────────────────────────┘
```

Four processes. Two Telegram bots (**separate tokens — this matters, see Step 0**).
The RAG API binds to `localhost` only and is never exposed.

---

## Prerequisites

- **Python 3.11 or 3.12** (`numpy 2.3.4` / `pandas 2.3.3` need ≥3.11; the Dockerfiles use
  3.12 for the gateway and 3.11 for RAG — either works locally)
- **~2 GB disk** for dependencies, or **~5 GB** if you install the offline embedding
  fallback (`sentence-transformers` pulls in torch — skip it if you have an OpenAI key)
- **git**
- An **OpenAI API key** (RAG embeddings) and an **Anthropic or OpenAI key** (worker
  classification — it tries Anthropic first, falls back to OpenAI with `gpt-4o-mini`)

---

## Step 0 — Kill the stale webhook (do this first, it is the whole ballgame)

Railway is dead, but **Telegram does not know that**. `register_telegram_webhook.py`
registered a webhook on the pipeline bot's token, and that registration is still live on
Telegram's side, pointing at a host that no longer answers.

While a webhook is registered, **Telegram refuses `getUpdates` with 409 Conflict**. Your
polling bot will start, look healthy, log nothing unusual, and receive absolutely nothing.
If you skip this step, everything below appears to work and the bot stays silent.

```bash
# from any machine, with the pipeline bot's token
curl "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/deleteWebhook?drop_pending_updates=true"
```

`drop_pending_updates=true` matters too: the bot has been down since July. Without it,
Telegram delivers the entire backlog at once and your bot replies to every message
somebody sent it over two months.

Verify:

```bash
curl "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getWebhookInfo"
# want: {"ok":true,"result":{"url":"","pending_update_count":0}}
```

---

## Step 1 — Clone and install

```bash
git clone https://github.com/laceto/AIstudioAccademiaMilano.git
cd AIstudioAccademiaMilano

python -m venv .venv
source .venv/bin/activate          # Windows Git Bash: source .venv/Scripts/activate

pip install -r gateway/requirements.txt

# RAG side: kitai has a stale langchain<1.0 pin, so install it without deps first
pip install --no-deps git+https://github.com/laceto/kitai.git
pip install -r requirements-rag.txt
```

> **Optional:** to skip the ~3 GB torch download, comment out `sentence-transformers`
> in `requirements-rag.txt` before installing. It is only the offline embedding fallback;
> with `OPENAI_API_KEY` set you never touch it.

---

## Step 2 — Two bots, two tokens

The pipeline bot and the RAG bot **must be different bots**. One Telegram bot can only be
consumed by one process — whichever starts last wins and the other silently goes deaf.
This is exactly the failure that took the pipeline bot down in the first place.

1. Telegram → **@BotFather** → `/newbot` → this is your **RAG bot** → copy the token
2. Your existing "AI Studio Milano" bot stays the **pipeline bot**

---

## Step 3 — `.env` at the repo root

Every process loads `.env` from the repo root automatically (`bot_telegram.py`,
`rag_bot_telegram.py`, `worker.py`, `api_server.py` all do this). Copy `.env.example`
and fill in:

```ini
TELEGRAM_BOT_TOKEN=<pipeline bot — the existing AI Studio Milano bot>
TELEGRAM_RAG_BOT_TOKEN=<the new RAG bot from Step 2>

OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...        # optional; worker falls back to OpenAI

RAG_API_URL=http://localhost:8000   # local only — never a public URL
```

Leave `TELEGRAM_CHANNEL_ID` alone unless you're also publishing to a channel.

> `.env` is gitignored and the pre-commit hook (`scripts/git-hooks/pre-commit`) blocks it
> from being staged. Don't fight the hook.

---

## Step 4 — Verify before you start anything

```bash
python scripts/check_telegram.py
```

Expected on a correct setup:

```
── pipeline bot  (TELEGRAM_BOT_TOKEN)
   bot:         @<your bot>
   mode:        polling (no webhook)      ← Step 0 worked
   pending:     0 update(s)

── rag bot  (TELEGRAM_RAG_BOT_TOKEN)
   bot:         @<your rag bot>
   mode:        polling (no webhook)
```

The script errors if the two tokens are identical, if a webhook is still registered on the
polling bot, or if Telegram recorded a delivery failure. Fix anything it reports before
moving on — every one of those conditions produces a bot that looks fine and does nothing.

---

## Step 5 — Start the stack

```bash
python scripts/run_local_stack.py
```

That starts all four processes, waits for the RAG API to answer `/health` before starting
the bots that depend on it, prefixes every log line with its source, and shuts everything
down cleanly on Ctrl+C.

To run them by hand instead — four terminals, venv activated in each:

```bash
uvicorn scripts.rag.api_server:app --host 127.0.0.1 --port 8000   # 1. RAG API
python -m gateway.rag_bot_telegram                                 # 2. RAG bot
python -m gateway.bot_telegram                                     # 3. pipeline bot
python -m gateway.worker                                           # 4. queue worker
```

Start the RAG API first — the RAG bot returns `RAG error: ...` to users if it isn't up yet.

---

## Step 6 — Verify end to end

1. Message the **RAG bot**: `Come funziona la pipeline a 6 agenti?`
   → an answer drawn from the repo. Confirms RAG API + vectorstore + polling.
2. Message the **pipeline bot**: `Ho bisogno di una landing page per il mio ristorante`
   → immediate ack with a Job ID, then a second message from the worker with the
   classified product and price (€9.90).
3. Check `gateway/queue/` — one JSON file per job, `status: classified`.

If step 2 gives you the ack but never the second message, the **worker** isn't running.
That's the half that was broken in your screenshot.

---

## Keeping it alive

The obvious catch: **the bot is up only while the laptop is awake and online.**

- **Disable sleep** on the laptop (or at least sleep-on-lid-close), otherwise the bots die
  every time you shut it.
- **Autostart:** on Windows, put a shortcut to `run_local_stack.py` in
  `shell:startup`; on macOS use a LaunchAgent; on Linux a systemd user service.
- **Restart after a crash:** nothing supervises these processes. If you want real
  resilience, wrap them in the OS service manager rather than the launcher script.
- Telegram queues updates for **24 hours** while a polling bot is offline, so short
  outages self-heal — messages arrive when you come back up. Longer than that and they
  are lost.

---

## What you give up versus Railway

| | Railway | Local laptop |
|---|---|---|
| Uptime | ~always | only while the laptop is on |
| Public URL | yes | none (polling only) |
| Cost | $5–10/mo | €0 |
| Webhook mode | available | not usable |
| `gateway/api.py` (FastAPI intake) | deployable | runnable but unreachable from outside |
| Streamlit gateway form | public | `localhost` only |

The Streamlit intake form and the WhatsApp webhook **cannot work locally** — both need a
public URL. Telegram is the one channel that survives this move intact, because it polls.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Bot silent, no errors in logs | Webhook still registered → `getUpdates` 409 | Step 0 |
| Bot replies to months-old messages on startup | Backlog delivered | `deleteWebhook?drop_pending_updates=true` |
| Only one of the two bots works | Same token in both env vars | Step 2 — two separate bots |
| `RAG error: Connection refused` | RAG API not up yet | Start it first, wait for `/health` |
| Ack arrives, result never does | Worker not running | `python -m gateway.worker` |
| `RAG_API_URL not configured` | Missing from `.env` | Step 3 |
| `ModuleNotFoundError: telegram` | Wrong venv, or deps not installed | Step 1 |
| Import error from `kitai` | Installed with deps | `pip install --no-deps git+...kitai.git` |

---

## If you go back to Railway later

Both services still exist with their domains, GitHub source connections and 28 env vars
intact — upgrading the plan and redeploying is a short job. **Before** you do, fix the
build config: root `railway.toml` sets `dockerfilePath = "scripts/rag/Dockerfile"` and
both services build from the same repo root, so the gateway service would come back up
running a second copy of the RAG API. Each service needs its own root directory or config
path (`gateway/Dockerfile` vs `scripts/rag/Dockerfile`).
