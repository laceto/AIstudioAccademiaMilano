from .base import DeliveryChannel
from .telegram import TelegramDelivery
from .whatsapp import WhatsAppDelivery

CHANNELS: dict[str, type[DeliveryChannel]] = {
    "whatsapp": WhatsAppDelivery,
    "telegram": TelegramDelivery,
}


def get_channel(name: str) -> DeliveryChannel:
    if name not in CHANNELS:
        raise ValueError(f"Unknown delivery channel: {name}. Known: {sorted(CHANNELS)}")
    return CHANNELS[name]()


__all__ = ["DeliveryChannel", "WhatsAppDelivery", "TelegramDelivery", "get_channel", "CHANNELS"]
