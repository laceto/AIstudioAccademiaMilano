from .base import CheckoutSession, PaymentProvider


class SatispayProvider(PaymentProvider):
    """Satispay payment provider — v2 stub.

    Implementation refs:
      - API: https://developers.satispay.com/reference/payment-creation
      - Auth: RSA key pair, Authorization + Satispay-Signature headers
      - Flow: POST /g_business/v1/payments → returns redirect_url + payment_id
    """

    name = "satispay"

    def create_checkout_session(
        self,
        amount_eur: float,
        product_label: str,
        success_url: str,
        cancel_url: str,
        metadata: dict,
    ) -> CheckoutSession:
        raise NotImplementedError("SatispayProvider planned for v2.")

    def verify_payment(self, session_id: str) -> bool:
        raise NotImplementedError("SatispayProvider planned for v2.")
