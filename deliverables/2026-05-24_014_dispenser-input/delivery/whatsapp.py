import os

from twilio.rest import Client

from .base import DeliveryChannel


class WhatsAppDelivery(DeliveryChannel):
    """Send WhatsApp messages via Twilio.

    Required env vars:
      - TWILIO_ACCOUNT_SID
      - TWILIO_AUTH_TOKEN
      - TWILIO_WHATSAPP_FROM    e.g. "whatsapp:+14155238886" (Twilio sandbox)
    """

    name = "whatsapp"

    def __init__(self) -> None:
        sid = os.environ.get("TWILIO_ACCOUNT_SID")
        token = os.environ.get("TWILIO_AUTH_TOKEN")
        self.from_number = os.environ.get("TWILIO_WHATSAPP_FROM")
        if not (sid and token and self.from_number):
            raise RuntimeError(
                "Missing Twilio env vars: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM"
            )
        self.client = Client(sid, token)

    def send(self, recipient: str, message: str, attachments: list[dict] | None = None) -> bool:
        to = recipient if recipient.startswith("whatsapp:") else f"whatsapp:{recipient}"
        kwargs: dict = {"from_": self.from_number, "to": to, "body": message}
        if attachments:
            kwargs["media_url"] = [a["url"] for a in attachments if a.get("url")]
        msg = self.client.messages.create(**kwargs)
        return bool(msg.sid)
