"""Parse WhatsApp exported chat .txt files into Feeds.

WhatsApp exports come in two main formats:
  [DD/MM/YYYY, HH:MM:SS] Sender: message         (iOS, brackets)
  DD/MM/YYYY, HH:MM - Sender: message             (Android, no brackets)
"""
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import IO

from .models import Feed, FeedItem


# Matches both iOS and Android export styles:
#   iOS:     [DD/MM/YYYY, HH:MM:SS] Sender: message  (bracket, NO dash)
#   Android: DD/MM/YYYY, HH:MM - Sender: message     (no bracket, dash)
_LINE_RE = re.compile(
    r"^\[?(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}),?\s+"
    r"(\d{1,2}:\d{2}(?::\d{2})?(?:\s?[AP]M)?)\]?"
    r"(?:\s*[-–]\s*|\s+)"          # iOS has space; Android has " - "
    r"([^:]+):\s*(.*)"
)

# System/meta messages (no sender:) — skip these
_SYSTEM_RE = re.compile(
    r"^\[?(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}),?\s+"
    r"(\d{1,2}:\d{2}(?::\d{2})?)\]?\s*[-–]\s*"
    r"(?!.*:)"
)


def _parse_date(date_str: str, time_str: str) -> datetime:
    date_str = date_str.strip()
    time_str = time_str.strip()
    for fmt in (
        "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M",
        "%d/%m/%y %H:%M:%S", "%d/%m/%y %H:%M",
        "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M",
        "%m/%d/%y %H:%M:%S", "%m/%d/%y %H:%M",
        "%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M",
        "%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M",
        "%d/%m/%Y %I:%M:%S %p", "%d/%m/%Y %I:%M %p",
    ):
        try:
            return datetime.strptime(f"{date_str} {time_str}", fmt)
        except ValueError:
            pass
    return datetime.now()


def parse_whatsapp_text(text: str, source_name: str = "whatsapp_chat") -> Feed:
    """Parse raw WhatsApp export text into a Feed."""
    feed_id = re.sub(r"\W+", "_", source_name.lower())[:40]
    items: list[FeedItem] = []
    current: dict | None = None

    for line in text.splitlines():
        m = _LINE_RE.match(line)
        if m:
            if current:
                items.append(_make_item(current, feed_id, len(items)))
            current = {
                "date": m.group(1),
                "time": m.group(2),
                "author": m.group(3).strip(),
                "content": m.group(4),
            }
        elif current and line.strip():
            # Continuation of a multi-line message
            current["content"] += "\n" + line

    if current:
        items.append(_make_item(current, feed_id, len(items)))

    return Feed(
        id=feed_id,
        title=source_name,
        source_type="whatsapp",
        source_path=source_name,
        items=items,
        description=f"WhatsApp chat — {len(items)} messages",
    )


def _make_item(raw: dict, feed_id: str, idx: int) -> FeedItem:
    ts = _parse_date(raw["date"], raw["time"])
    return FeedItem(
        id=f"{feed_id}_{idx}",
        feed_id=feed_id,
        timestamp=ts,
        author=raw["author"],
        content=raw["content"].strip(),
    )


def load_whatsapp_file(path: Path) -> Feed:
    text = path.read_text(encoding="utf-8", errors="replace")
    return parse_whatsapp_text(text, source_name=path.stem)
