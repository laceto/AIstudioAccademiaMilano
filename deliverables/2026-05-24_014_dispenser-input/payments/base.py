from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class CheckoutSession:
    url: str
    session_id: str


@dataclass
class PaymentVerification:
    paid: bool
    amount_cents: int
    metadata: dict = field(default_factory=dict)


class PaymentProvider(ABC):
    name: str = ""

    @abstractmethod
    def create_checkout_session(
        self,
        amount_eur: float,
        product_label: str,
        success_url: str,
        cancel_url: str,
        metadata: dict,
    ) -> CheckoutSession: ...

    @abstractmethod
    def verify_payment(self, session_id: str) -> PaymentVerification: ...
