"""Dispenser input form — Streamlit.

Flow:
    1. User scans a QR on the physical dispenser → lands here with ?d=<dispenser-id>
    2. Guided wizard: product → details → delivery channel(s) → recipient
    3. Pay via Stripe Checkout (configurable provider — Satispay/PayPal coming v2)
    4. Stripe redirects back with ?session_id=… → we verify payment + enqueue
    5. User sees "in the queue" confirmation; deliverable lands on their channel later
"""
import os
import sys
from pathlib import Path
from urllib.parse import urlencode

import streamlit as st

# Make sibling modules importable when Streamlit invokes this file directly
sys.path.insert(0, str(Path(__file__).resolve().parent))

import request_queue  # noqa: E402
from classifiers import CatalogClassifier  # noqa: E402
from payments import get_provider  # noqa: E402

PAYMENT_PROVIDER_NAME = os.environ.get("PAYMENT_PROVIDER", "stripe")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8501")


def get_secret(name: str, default: str | None = None) -> str | None:
    try:
        return st.secrets[name]
    except Exception:
        return os.environ.get(name, default)


def hydrate_env() -> None:
    """Mirror st.secrets into os.environ so provider/channel classes see them."""
    for k in (
        "STRIPE_SECRET_KEY",
        "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_FROM",
        "TELEGRAM_BOT_TOKEN", "ADMIN_TELEGRAM_CHAT_ID",
        "PUBLIC_BASE_URL", "PAYMENT_PROVIDER",
    ):
        v = get_secret(k)
        if v and k not in os.environ:
            os.environ[k] = v


# ---------------------------------------------------------------- page setup
st.set_page_config(page_title="AI Studio Dispenser", page_icon="🤖", layout="centered")
hydrate_env()

dispenser_id = st.query_params.get("d", "default")
payment_session_id = st.query_params.get("session_id")

classifier = CatalogClassifier()


def make_provider():
    try:
        return get_provider(PAYMENT_PROVIDER_NAME)
    except (RuntimeError, ValueError) as e:
        st.warning(f"Payment provider not configured ({e}).")
        return None


# ----------------------------------------------- post-payment redirect path
if payment_session_id:
    provider = make_provider()
    pending = st.session_state.get("pending_request")
    if provider and pending and provider.verify_payment(payment_session_id):
        request_id = request_queue.enqueue({
            **pending,
            "payment_session_id": payment_session_id,
            "payment_provider": provider.name,
        })
        del st.session_state["pending_request"]
        st.success(f"Payment received. Your request is in the queue (id `{request_id[:8]}`).")
        st.info(
            "You'll get the deliverable on your chosen channel(s) shortly. "
            "Median turnaround: 5–10 minutes during operator hours."
        )
        st.balloons()
        st.stop()
    else:
        st.error("Could not verify payment. If you were charged, contact support with the session id.")
        st.code(payment_session_id, language="text")
        st.stop()


# ---------------------------------------------------------------- the wizard
st.title("🤖 AI Studio Dispenser")
st.caption(f"Dispenser `{dispenser_id}` · Powered by AI Studio Accademia Milano")

products = classifier.list_products()
labels = [f"{p['label']} — €{p['price_eur']:.2f}" for p in products]

with st.form("dispenser_form"):
    st.subheader("1. Pick a product")
    idx = st.selectbox("Product", range(len(products)), format_func=lambda i: labels[i])
    chosen = products[idx]

    st.subheader("2. Describe what you need")
    free_text = st.text_area(
        "Details",
        placeholder="One or two sentences. E.g. 'Invoice INV-042 for Acme SRL, €1,200, single line item Consulting May 2026.'",
        height=140,
    )

    st.subheader("3. Where should we send it?")
    col1, col2 = st.columns(2)
    via_whatsapp = col1.checkbox("WhatsApp", value=True)
    via_telegram = col2.checkbox("Telegram")
    recipient = st.text_input(
        "Number or Telegram chat_id",
        placeholder="+39…  or  123456789",
        help=(
            "WhatsApp: full international number (e.g. +393331234567). "
            "Telegram: numeric chat_id (start the bot with /start first to get yours)."
        ),
    )

    submitted = st.form_submit_button("Continue to payment →", type="primary", use_container_width=True)

if not submitted:
    st.stop()


# --------------------------------------------------------------- validation
channels: list[str] = []
if via_whatsapp:
    channels.append("whatsapp")
if via_telegram:
    channels.append("telegram")

errors = []
if not channels:
    errors.append("Pick at least one delivery channel.")
if not recipient.strip():
    errors.append("Recipient is required.")
if not free_text.strip():
    errors.append("Describe what you need (at least a sentence).")

if errors:
    for e in errors:
        st.error(e)
    st.stop()


# --------------------------------------------- classify + queue + checkout
classification = classifier.classify(chosen["id"], free_text=free_text.strip())

st.session_state["pending_request"] = {
    "dispenser_id": dispenser_id,
    "classification": classification.__dict__,
    "delivery_channels": channels,
    "recipient": recipient.strip(),
}

provider = make_provider()
if provider is None:
    st.info("Payment provider not configured. Showing the request payload that would be queued:")
    st.json(st.session_state["pending_request"])
    st.stop()

return_url = f"{PUBLIC_BASE_URL}/?{urlencode({'d': dispenser_id})}"
checkout = provider.create_checkout_session(
    amount_eur=classification.price_eur,
    product_label=classification.product_label,
    success_url=return_url,
    cancel_url=return_url,
    metadata={
        "dispenser_id": dispenser_id,
        "product_id": classification.product_id,
        "channels": ",".join(channels),
    },
)

st.markdown(f"### Total: **€{classification.price_eur:.2f}**")
st.link_button(
    f"Pay with {provider.name.title()} →",
    checkout.url,
    type="primary",
    use_container_width=True,
)
st.caption("You'll be redirected to the payment provider. After payment we queue your request automatically.")
