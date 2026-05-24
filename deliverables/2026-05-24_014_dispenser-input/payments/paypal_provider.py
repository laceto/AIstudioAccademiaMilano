from .base import CheckoutSession, PaymentProvider


class PayPalProvider(PaymentProvider):
    """PayPal Checkout payment provider — v2 stub.

    Implementation refs:
      - API: https://developer.paypal.com/docs/api/orders/v2/
      - Auth: OAuth2 client_id + secret → bearer token (POST /v1/oauth2/token)
      - Flow: POST /v2/checkout/orders → links[].rel=='approve' is the redirect URL
    """

    name = "paypal"

    def create_checkout_session(
        self,
        amount_eur: float,
        product_label: str,
        success_url: str,
        cancel_url: str,
        metadata: dict,
    ) -> CheckoutSession:
        raise NotImplementedError("PayPalProvider planned for v2.")

    def verify_payment(self, session_id: str) -> bool:
        raise NotImplementedError("PayPalProvider planned for v2.")
