#!/usr/bin/env python3
"""Register the Telegram webhook after Railway deploy.

Usage:
    TELEGRAM_BOT_TOKEN=xxx RAILWAY_URL=https://your-app.up.railway.app \
    python scripts/rag/register_telegram_webhook.py
"""
import os
import sys

import httpx

token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
base  = os.environ.get("RAILWAY_URL", "").rstrip("/")
if not token or not base:
    print("ERROR: TELEGRAM_BOT_TOKEN and RAILWAY_URL must be set.", file=sys.stderr)
    sys.exit(1)

url = f"https://api.telegram.org/bot{token}/setWebhook"
r   = httpx.post(url, json={"url": f"{base}/webhook/telegram"})
print(r.status_code, r.text)
sys.exit(0 if r.status_code == 200 else 1)
