import os

import requests

from .base import DeliveryChannel


class TelegramDelivery(DeliveryChannel):
    """Send Telegram messages via the Bot API.

    Required env var:
      - TELEGRAM_BOT_TOKEN     from @BotFather

    `recipient` is a chat_id (numeric) or @username. The user must have started a
    conversation with the bot (or be in a group/channel the bot can post to) — the
    Bot API will refuse otherwise.
    """

    name = "telegram"
    BASE_URL = "https://api.telegram.org"

    def __init__(self) -> None:
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not self.token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN not set")

    def send(self, recipient: str, message: str, attachments: list[dict] | None = None) -> bool:
        url = f"{self.BASE_URL}/bot{self.token}/sendMessage"
        payload = {"chat_id": recipient, "text": message, "parse_mode": "Markdown"}
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        if attachments:
            for att in attachments:
                if not att.get("url"):
                    continue
                doc_url = f"{self.BASE_URL}/bot{self.token}/sendDocument"
                requests.post(
                    doc_url,
                    json={"chat_id": recipient, "document": att["url"], "caption": att.get("caption", "")},
                    timeout=15,
                ).raise_for_status()
        return r.json().get("ok", False)
