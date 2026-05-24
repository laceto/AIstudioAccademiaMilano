import os

import stripe

from .base import CheckoutSession, PaymentProvider


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
        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "eur",
                    "unit_amount": int(round(amount_eur * 100)),
                    "product_data": {"name": product_label},
                },
                "quantity": 1,
            }],
            success_url=success_url + ("&" if "?" in success_url else "?") + "session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            metadata=metadata,
        )
        return CheckoutSession(url=session.url, session_id=session.id)

    def verify_payment(self, session_id: str) -> bool:
        session = stripe.checkout.Session.retrieve(session_id)
        return session.payment_status == "paid"
