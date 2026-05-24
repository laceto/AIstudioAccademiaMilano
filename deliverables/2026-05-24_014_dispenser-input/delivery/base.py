from abc import ABC, abstractmethod


class DeliveryChannel(ABC):
    name: str = ""

    @abstractmethod
    def send(self, recipient: str, message: str, attachments: list[dict] | None = None) -> bool: ...
