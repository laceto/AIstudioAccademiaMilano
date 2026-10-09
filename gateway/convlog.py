"""Per-session message log for the gateway.

Every message a user sends and every reply the bot returns is written as one
line to stdout (Cloud Run ships stdout to Cloud Logging), keyed by chat_id:

    [conv] dir=in chat=123 text="Ho bisogno di una landing page"
    [conv] dir=out chat=123 text="Richiesta ricevuta: ..."

It uses its own logger and handler because the root logger is configured late
(bot_telegram.basicConfig runs on the first webhook import), so plain
logger.info calls made before that would be dropped.

Privacy: these lines hold user text. Cloud Logging keeps them for the bucket's
retention period (30 days by default) — keep that in mind for GDPR.
"""

from __future__ import annotations

import json
import logging
import sys

MAX_CHARS = 1000

_conv = logging.getLogger("gateway.conversation")
_conv.setLevel(logging.INFO)
_conv.propagate = False
if not _conv.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(asctime)s [conv] %(message)s"))
    _conv.addHandler(_handler)


def log_message(direction: str, chat_id: str | int, text: str) -> None:
    """Log one message. direction is "in" (user -> bot) or "out" (bot -> user)."""
    text = text or ""
    suffix = ""
    if len(text) > MAX_CHARS:
        suffix = f" ...(truncated, {len(text)} chars)"
        text = text[:MAX_CHARS]
    # json.dumps keeps the entry on one line (escapes newlines) and quotes safely.
    _conv.info("dir=%s chat=%s text=%s%s", direction, chat_id, json.dumps(text, ensure_ascii=False), suffix)


def silence_http_loggers() -> None:
    """Stop httpx/httpcore logging request URLs.

    The Telegram Bot API puts the bot token in the URL path
    (https://api.telegram.org/bot<TOKEN>/sendMessage), so INFO-level request
    logs leak it into Cloud Logging.
    """
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)
