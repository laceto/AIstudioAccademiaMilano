import os

import stripe

from .base import CheckoutSession, PaymentProvider, PaymentVerification

# Marker the caller must see come back in metadata. Sessions paid against an
# earlier marker (or no marker) are rejected — kills cross-app session_id replay.
APP_MARKER = "dispenser_v1"


class StripeProvider(PaymentProvider):
    name = "stripe"

    def __init__(self) -> None:
        key = os.environ.get("STRIPE_SECRET_KEY")
        if not key:
            raise RuntimeError("STRIPE_SECRET_KEY not set")
        stripe.api_key = key

    def create_checkout_session(
        self,
        amount_eur: float,
        product_label: str,
        success_url: str,
        cancel_url: str,
        metadata: dict,
    ) -> CheckoutSession:
        amount_cents = int(round(amount_eur * 100))
        # Server-side fields the caller must not be able to forge from the success URL.
        safe_metadata = {
            **metadata,
            "app_marker": APP_MARKER,
            "expected_amount_cents": str(amount_cents),
        }
        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "eur",
                    "unit_amount": amount_cents,
                    "product_data": {"name": product_label},
                },
                "quantity": 1,
            }],
            success_url=success_url + ("&" if "?" in success_url else "?") + "session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            metadata=safe_metadata,
        )
        return CheckoutSession(url=session.url, session_id=session.id)

    def verify_payment(self, session_id: str) -> PaymentVerification:
        session = stripe.checkout.Session.retrieve(session_id)
        return PaymentVerification(
            paid=(session.payment_status == "paid"),
            amount_cents=int(session.amount_total or 0),
            metadata=dict(session.metadata or {}),
        )
