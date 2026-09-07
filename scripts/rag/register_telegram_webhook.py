#!/usr/bin/env python3
"""Register the RAG bot's Telegram webhook after a Railway deploy.

This points a bot at `scripts/rag/api_server.py:/webhook/telegram`, which replies
using TELEGRAM_RAG_BOT_TOKEN — so the webhook must be registered on that same
bot. Registering it on TELEGRAM_BOT_TOKEN instead hands the pipeline bot's
updates to the RAG API while the replies go out as a different bot, and kills
`gateway.bot_telegram` polling with a 409 into the bargain.

Usage:
    TELEGRAM_RAG_BOT_TOKEN=xxx RAILWAY_URL=https://your-app.up.railway.app \
    python scripts/rag/register_telegram_webhook.py
"""
import os
import sys

import httpx

token = os.environ.get("TELEGRAM_RAG_BOT_TOKEN", "")
base  = os.environ.get("RAILWAY_URL", "").rstrip("/")
if not token or not base:
    print("ERROR: TELEGRAM_RAG_BOT_TOKEN and RAILWAY_URL must be set.", file=sys.stderr)
    sys.exit(1)

if token == os.environ.get("TELEGRAM_BOT_TOKEN", ""):
    print(
        "ERROR: TELEGRAM_RAG_BOT_TOKEN is the same token as TELEGRAM_BOT_TOKEN.\n"
        "       Registering this webhook would take the pipeline bot offline "
        "(Telegram refuses getUpdates while a webhook is set).\n"
        "       Create a second bot via @BotFather → /newbot and use its token.",
        file=sys.stderr,
    )
    sys.exit(1)

url = f"https://api.telegram.org/bot{token}/setWebhook"
r   = httpx.post(url, json={"url": f"{base}/webhook/telegram"})
print(r.status_code, r.text)
sys.exit(0 if r.status_code == 200 else 1)
