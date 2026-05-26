"""WhatsApp chat export parser for The Niccolò Chronicles.

Handles the two formats a casual user will actually have:

1. The native WhatsApp text export (`.txt`), in either of WhatsApp's
   common line shapes:

       [12/05/26, 14:32:15] Luigi: Niccolò just asked...
       12/05/26, 14:32 - Luigi: Niccolò just asked...

2. A CSV with columns `date,time,author,message,attachment` (the shape
   most third-party WhatsApp-to-CSV converters emit, and the one our
   spec asks for).

The parser returns a flat list of `ChatEntry` records. It does NOT try
to classify entries — that is the LLM's job. It only:

* normalises dates to `datetime.date`,
* joins multi-line messages,
* detects attachments (image / voice / other) and pulls out the
  filename when present.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

LINE_BRACKETED = re.compile(
    r"^\[(?P<d>\d{1,2})/(?P<m>\d{1,2})/(?P<y>\d{2,4}),\s*"
    r"(?P<H>\d{1,2}):(?P<M>\d{2})(?::\d{2})?\s*(?:AM|PM|am|pm)?\]\s*"
    r"(?P<author>[^:]+?):\s?(?P<text>.*)$"
)
LINE_PLAIN = re.compile(
    r"^(?P<d>\d{1,2})/(?P<m>\d{1,2})/(?P<y>\d{2,4}),\s*"
    r"(?P<H>\d{1,2}):(?P<M>\d{2})(?::\d{2})?\s*(?:AM|PM|am|pm)?\s*-\s*"
    r"(?P<author>[^:]+?):\s?(?P<text>.*)$"
)

ATTACHMENT_INLINE = re.compile(
    r"(?P<name>[\w\-.]+\.(?:jpg|jpeg|png|heic|gif|webp|mp4|mov|opus|m4a|ogg|aac|pdf))"
    r"\s*\(file attached\)",
    re.IGNORECASE,
)
ATTACHMENT_IOS = re.compile(
    r"<attached:\s*(?P<name>[\w\-.]+)>", re.IGNORECASE
)
MEDIA_OMITTED = re.compile(r"<\s*Media omitted\s*>", re.IGNORECASE)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".gif", ".webp"}
VIDEO_EXTS = {".mp4", ".mov"}
VOICE_EXTS = {".opus", ".m4a", ".ogg", ".aac"}
VOICE_HINTS = ("voice note", "audio omitted", "PTT-", "ptt-")


@dataclass(frozen=True)
class ChatEntry:
    """A single, normalised message from the export."""
    date: date
    author: str
    text: str
    attachment: str | None  # filename, or None
    kind: str  # "text" | "image" | "video" | "voice" | "other_media"

    def to_dict(self) -> dict:
        return {
            "date": self.date.isoformat(),
            "author": self.author,
            "text": self.text,
            "attachment": self.attachment,
            "kind": self.kind,
        }


def _normalise_year(y: str) -> int:
    n = int(y)
    if n < 100:
        # WhatsApp two-digit years: 70-99 -> 1970s/80s/90s, 00-69 -> 2000s/60s.
        # In 2026 we want 26 -> 2026, 99 -> 1999.
        return 2000 + n if n < 70 else 1900 + n
    return n


def _classify_attachment(name: str | None, text: str) -> str:
    if name:
        ext = Path(name).suffix.lower()
        if ext in IMAGE_EXTS:
            return "image"
        if ext in VIDEO_EXTS:
            return "video"
        if ext in VOICE_EXTS:
            return "voice"
        return "other_media"
    lowered = text.lower()
    if any(h.lower() in lowered for h in VOICE_HINTS):
        return "voice"
    return "text"


def _extract_attachment(text: str) -> tuple[str | None, str]:
    """Return (filename_or_None, cleaned_text)."""
    m = ATTACHMENT_INLINE.search(text)
    if m:
        return m.group("name"), ATTACHMENT_INLINE.sub("", text).strip(" -·\n\r\t")
    m = ATTACHMENT_IOS.search(text)
    if m:
        return m.group("name"), ATTACHMENT_IOS.sub("", text).strip(" -·\n\r\t")
    if MEDIA_OMITTED.search(text):
        return None, MEDIA_OMITTED.sub("", text).strip(" -·\n\r\t")
    return None, text.strip()


def _match_header(line: str):
    return LINE_BRACKETED.match(line) or LINE_PLAIN.match(line)


def parse_whatsapp_txt(content: str) -> list[ChatEntry]:
    """Parse the native WhatsApp `.txt` export, joining multi-line messages."""
    entries: list[ChatEntry] = []
    pending_header: re.Match | None = None
    pending_lines: list[str] = []

    def flush():
        nonlocal pending_header, pending_lines
        if pending_header is None:
            return
        gd = pending_header.groupdict()
        d = date(_normalise_year(gd["y"]), int(gd["m"]), int(gd["d"]))
        author = gd["author"].strip()
        text = "\n".join(pending_lines).strip()
        attachment, cleaned = _extract_attachment(text)
        kind = _classify_attachment(attachment, cleaned)
        entries.append(ChatEntry(
            date=d, author=author, text=cleaned,
            attachment=attachment, kind=kind,
        ))
        pending_header = None
        pending_lines = []

    for raw_line in content.splitlines():
        line = raw_line.rstrip("\r")
        # WhatsApp's invisible LRM characters sometimes prefix lines.
        line = line.lstrip("‎‏").rstrip()
        if not line:
            if pending_header is not None:
                pending_lines.append("")
            continue
        m = _match_header(line)
        if m:
            flush()
            pending_header = m
            pending_lines = [m.group("text")]
        else:
            if pending_header is not None:
                pending_lines.append(line)
            # else: stray pre-header line (WhatsApp's first encryption notice). Skip.
    flush()
    return entries


def parse_csv(content: str) -> list[ChatEntry]:
    """Parse a CSV with columns date,time?,author,message,attachment?.

    `date` may be ISO (`2026-05-12`) or DD/MM/YY. `attachment` is optional.
    `time` is optional and ignored (we only group by day).
    """
    reader = csv.DictReader(content.splitlines())
    entries: list[ChatEntry] = []
    for row in reader:
        if not row:
            continue
        raw_date = (row.get("date") or "").strip()
        if not raw_date:
            continue
        d = _parse_date(raw_date)
        author = (row.get("author") or "").strip()
        text = (row.get("message") or "").strip()
        attachment = (row.get("attachment") or "").strip() or None
        if attachment is None:
            attachment, text = _extract_attachment(text)
        kind = _classify_attachment(attachment, text)
        entries.append(ChatEntry(
            date=d, author=author, text=text,
            attachment=attachment, kind=kind,
        ))
    return entries


def _parse_date(raw: str) -> date:
    if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
        y, m, d = raw.split("-")
        return date(int(y), int(m), int(d))
    m_ = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})$", raw)
    if not m_:
        raise ValueError(f"unrecognised date: {raw!r}")
    d, m, y = m_.groups()
    return date(_normalise_year(y), int(m), int(d))


def parse_chat(path: str | Path) -> list[ChatEntry]:
    """Parse either a WhatsApp `.txt` export or a CSV, by suffix."""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() == ".csv":
        return parse_csv(text)
    return parse_whatsapp_txt(text)


def filter_month(entries: Iterable[ChatEntry], year: int, month: int) -> list[ChatEntry]:
    return [e for e in entries if e.date.year == year and e.date.month == month]
