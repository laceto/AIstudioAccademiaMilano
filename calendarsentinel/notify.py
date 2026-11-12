"""Turn a Calendar event into a message and push it to Telegram (same env vars as the gateway)."""

from __future__ import annotations

import os

import httpx


def _when(ev: dict) -> str:
    s = ev.get("start") or {}
    if "dateTime" in s:
        return s["dateTime"].replace("T", " ")[:16]
    if "date" in s:
        return f"{s['date']} (all day)"
    return "time not set"


def format_event(ev: dict) -> str:
    lines = ["New calendar event", ev.get("summary") or "(no title)", _when(ev)]
    if ev.get("location"):
        lines.append(f"Where: {ev['location']}")
    if ev.get("creator", {}).get("email"):
        lines.append(f"Added by: {ev['creator']['email']}")
    if ev.get("htmlLink"):
        lines.append(ev["htmlLink"])
    return "\n".join(lines)


def send_telegram(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chats = [c.strip() for c in os.environ.get("NOTIFY_TELEGRAM_CHAT_IDS", "").split(",") if c.strip()]
    if not token or not chats:
        raise RuntimeError("set TELEGRAM_BOT_TOKEN and NOTIFY_TELEGRAM_CHAT_IDS")
    failed = 0
    for chat in chats:
        r = httpx.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat, "text": text}, timeout=10.0)
        failed += r.status_code != 200
    if failed:
        raise RuntimeError(f"telegram: {failed}/{len(chats)} sends failed")  # never include the URL: it holds the token
