from .base import CheckoutSession, PaymentProvider
from .stripe_provider import StripeProvider
from .satispay_provider import SatispayProvider
from .paypal_provider import PayPalProvider

PROVIDERS: dict[str, type[PaymentProvider]] = {
    "stripe": StripeProvider,
    "satispay": SatispayProvider,
    "paypal": PayPalProvider,
}


def get_provider(name: str) -> PaymentProvider:
    if name not in PROVIDERS:
        raise ValueError(f"Unknown payment provider: {name}. Known: {sorted(PROVIDERS)}")
    return PROVIDERS[name]()


__all__ = ["CheckoutSession", "PaymentProvider", "get_provider", "PROVIDERS"]
