"""
Telegram reader via Telethon (MTProto ufficiale, gratuito).
Legge gruppi medici di Fabrizia, raccoglie messaggi, li struttura per l'avatar.

Setup:
  1. Vai su https://my.telegram.org → App API → ottieni API_ID e API_HASH
  2. Prima run: inserisci numero di telefono + codice OTP
  3. La sessione viene salvata in fabrizia.session (locale, mai committare)
"""
import os
import asyncio
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient
from telethon.tl.types import Channel, Chat, User

API_ID   = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
SESSION  = "fabrizia"   # nome file .session locale


async def list_groups(client: TelegramClient) -> list[dict]:
    """Restituisce tutti i gruppi/canali di Fabrizia."""
    dialogs = await client.get_dialogs()
    groups = []
    for d in dialogs:
        if d.is_group or d.is_channel:
            groups.append({
                "id":    d.id,
                "name":  d.name,
                "type":  "channel" if d.is_channel else "group",
                "unread": d.unread_count,
            })
    return groups


async def fetch_messages(
    client: TelegramClient,
    group_id: int,
    limit: int = 200,
    since_hours: int = 24,
) -> list[dict]:
    """
    Scarica ultimi `limit` messaggi di un gruppo,
    filtrando per gli ultimi `since_hours` ore.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    messages = []

    async for msg in client.iter_messages(group_id, limit=limit):
        if msg.date < cutoff:
            break
        if not msg.text:
            continue

        sender_name = "Sconosciuto"
        if msg.sender:
            s = msg.sender
            if isinstance(s, User):
                parts = [s.first_name or "", s.last_name or ""]
                sender_name = " ".join(p for p in parts if p).strip() or s.username or "Sconosciuto"
            elif hasattr(s, "title"):
                sender_name = s.title

        messages.append({
            "msg_id":  msg.id,
            "sender":  sender_name,
            "text":    msg.text,
            "date":    msg.date.isoformat(),
            "replies": msg.replies.replies if msg.replies else 0,
        })

    return list(reversed(messages))  # ordine cronologico


async def fetch_all_groups(
    since_hours: int = 24,
    max_msg_per_group: int = 200,
) -> dict[str, list[dict]]:
    """Entry point: scarica messaggi recenti da tutti i gruppi."""
    async with TelegramClient(SESSION, API_ID, API_HASH) as client:
        groups = await list_groups(client)
        result = {}
        for g in groups:
            msgs = await fetch_messages(
                client, g["id"],
                limit=max_msg_per_group,
                since_hours=since_hours,
            )
            if msgs:
                result[g["name"]] = msgs
        return result


def run_fetch(since_hours: int = 24) -> dict[str, list[dict]]:
    """Wrapper sincrono per chiamata da Streamlit."""
    return asyncio.run(fetch_all_groups(since_hours=since_hours))
