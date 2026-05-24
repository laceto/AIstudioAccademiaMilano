"""
Webhook-based announcer — no bot process needed.

Call this from any script to post to Discord when something ships:

    from announcer import announce, announce_deliverable
    announce("🚀 New deliverable: Milan Weather Dashboard is live!")
    announce_deliverable("011", "Milan Weather Dashboard", "€9.90", "2026-05-24")

Set env var:
    DISCORD_WEBHOOK_URL   (Server Settings → Integrations → Webhooks → New Webhook → Copy URL)
"""

import os
import requests
from datetime import datetime

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")


def announce(text: str, webhook_url: str | None = None) -> bool:
    url = webhook_url or WEBHOOK_URL
    if not url:
        print("⚠️  DISCORD_WEBHOOK_URL not set — announcement skipped.")
        return False
    r = requests.post(url, json={"content": text}, timeout=8)
    r.raise_for_status()
    return True


def announce_deliverable(
    id: str,
    name: str,
    price: str,
    date: str | None = None,
    webhook_url: str | None = None,
) -> bool:
    date = date or datetime.now().strftime("%Y-%m-%d")
    embed = {
        "embeds": [{
            "title": f"🚀 Shipped: #{id} — {name}",
            "description": f"**Price:** {price}  ·  **Date:** {date}",
            "color": 0x5865F2,
            "footer": {
                "text": "AI Studio Accademia Milano · github.com/laceto/AIstudioAccademiaMilano"
            },
        }]
    }
    url = webhook_url or WEBHOOK_URL
    if not url:
        print("⚠️  DISCORD_WEBHOOK_URL not set — announcement skipped.")
        return False
    r = requests.post(url, json=embed, timeout=8)
    r.raise_for_status()
    return True


def announce_post(title: str, body: str, webhook_url: str | None = None) -> bool:
    """Post a rich embed — used by Valentina for content publishing."""
    embed = {
        "embeds": [{
            "title": title,
            "description": body[:4096],
            "color": 0x5865F2,
            "footer": {"text": "AI Studio Accademia Milano"},
        }]
    }
    url = webhook_url or WEBHOOK_URL
    if not url:
        print("⚠️  DISCORD_WEBHOOK_URL not set — post skipped.")
        return False
    r = requests.post(url, json=embed, timeout=8)
    r.raise_for_status()
    return True


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        announce(" ".join(sys.argv[1:]))
    else:
        print("Usage: python announcer.py <message>")
