"""Reusable order webhook for landing-page deliverables.

Pure-Python, framework-agnostic. The caller (Flask/Vercel Function/Cloud Run) supplies:
  - send_email_fn(to: str, subject: str, body: str) -> None
  - create_calendar_event_fn(title: str, starts_at: datetime, duration_min: int, notes: str) -> str
    (returns the calendar event URL)

This module owns:
  - Input validation
  - Order ID generation
  - Composing customer + owner emails
  - Composing the calendar event title + notes
  - The dispatch sequence

It does NOT own:
  - HTTP routing (caller's job)
  - Gmail / Calendar credential management (caller injects send/create callables)
  - Persistence (caller writes the audit row; this returns the OrderResult)

Tests: tests/test_iss011_order_webhook.py
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import re
import secrets
from typing import Callable, Optional


# ── Public contract ──────────────────────────────────────────────────────────────

MIN_LEAD_TIME_HOURS = 24
MAX_QUANTITY = 50
MAX_NOTES_LEN = 1000

# Per APD's contract in deliverables/2026-05-24_011_bakery-v2/site/README.md
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class OrderValidationError(ValueError):
    """Raised when the inbound order payload is malformed.

    The `code` attribute is the wire-stable error string returned to the client
    per the published webhook contract (e.g. ``"invalid_email"``).
    """

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


@dataclasses.dataclass(frozen=True)
class Order:
    product: str
    quantity: int
    pickup_at: dt.datetime
    name: str
    email: str
    phone: Optional[str] = None
    notes: Optional[str] = None


@dataclasses.dataclass(frozen=True)
class OrderResult:
    order_id: str
    pickup_at: dt.datetime
    calendar_event_url: str


# ── Validation ───────────────────────────────────────────────────────────────────

def validate(payload: dict, *, now: Optional[dt.datetime] = None) -> Order:
    """Validate a raw payload and return a typed Order. Raises OrderValidationError."""
    now = now or dt.datetime.now(dt.timezone.utc)

    for required in ("product", "quantity", "pickup_at", "name", "email"):
        if required not in payload or payload[required] in (None, ""):
            raise OrderValidationError(f"missing_field:{required}")

    product = str(payload["product"]).strip()
    name = str(payload["name"]).strip()
    email = str(payload["email"]).strip()
    phone = (str(payload["phone"]).strip() if payload.get("phone") else None)
    notes = (str(payload["notes"]) if payload.get("notes") else None)

    if not _EMAIL_RE.match(email):
        raise OrderValidationError("invalid_email")

    try:
        quantity = int(payload["quantity"])
    except (TypeError, ValueError):
        raise OrderValidationError("quantity_out_of_range")
    if not 1 <= quantity <= MAX_QUANTITY:
        raise OrderValidationError("quantity_out_of_range")

    pickup_raw = payload["pickup_at"]
    try:
        # Accept both "Z" suffix and naive ISO; assume UTC if naive.
        pickup_at = dt.datetime.fromisoformat(str(pickup_raw).replace("Z", "+00:00"))
    except ValueError:
        raise OrderValidationError("pickup_in_past")  # malformed -> treat as invalid time
    if pickup_at.tzinfo is None:
        pickup_at = pickup_at.replace(tzinfo=dt.timezone.utc)

    if pickup_at < now:
        raise OrderValidationError("pickup_in_past")
    if pickup_at < now + dt.timedelta(hours=MIN_LEAD_TIME_HOURS):
        raise OrderValidationError("pickup_too_soon")

    if notes is not None and len(notes) > MAX_NOTES_LEN:
        raise OrderValidationError("notes_too_long")

    return Order(
        product=product,
        quantity=quantity,
        pickup_at=pickup_at,
        name=name,
        email=email,
        phone=phone,
        notes=notes,
    )


# ── Composition ──────────────────────────────────────────────────────────────────

def generate_order_id(*, now: Optional[dt.datetime] = None) -> str:
    """ORD-YYYY-XXXX where XXXX is 4 hex digits from a CSPRNG."""
    now = now or dt.datetime.now(dt.timezone.utc)
    return f"ORD-{now.year}-{secrets.token_hex(2).upper()}"


def customer_email(order: Order, order_id: str, *, bakery_name: str) -> tuple[str, str]:
    subject = f"Conferma ordine {order_id} — {bakery_name}"
    body = (
        f"Ciao {order.name},\n\n"
        f"abbiamo ricevuto il tuo ordine.\n\n"
        f"  Prodotto:  {order.product}\n"
        f"  Quantita': {order.quantity}\n"
        f"  Ritiro:    {order.pickup_at.isoformat()}\n"
        f"  ID ordine: {order_id}\n\n"
        f"Ti aspettiamo!\n— {bakery_name}\n"
    )
    return subject, body


def owner_email(order: Order, order_id: str, *, bakery_name: str) -> tuple[str, str]:
    subject = f"[{bakery_name}] Nuovo ordine {order_id}: {order.product} x{order.quantity}"
    body = (
        f"Nuovo ordine ricevuto:\n\n"
        f"  ID:        {order_id}\n"
        f"  Cliente:   {order.name} <{order.email}>"
        + (f" (tel: {order.phone})" if order.phone else "")
        + "\n"
        f"  Prodotto:  {order.product}\n"
        f"  Quantita': {order.quantity}\n"
        f"  Ritiro:    {order.pickup_at.isoformat()}\n"
        f"  Note:      {order.notes or '(nessuna)'}\n"
    )
    return subject, body


def calendar_event(order: Order, order_id: str, *, bakery_name: str) -> tuple[str, dt.datetime, int, str]:
    title = f"{bakery_name}: {order.product} x{order.quantity} — {order.name} ({order_id})"
    notes = (
        f"Cliente: {order.name} <{order.email}>"
        + (f" tel {order.phone}" if order.phone else "")
        + f"\nOrdine: {order_id}\n"
        + (f"\nNote: {order.notes}" if order.notes else "")
    )
    # Default slot: 15 minutes for pickup window.
    return title, order.pickup_at, 15, notes


# ── Dispatch ─────────────────────────────────────────────────────────────────────

def handle_order(
    payload: dict,
    *,
    send_email_fn: Callable[[str, str, str], None],
    create_calendar_event_fn: Callable[[str, dt.datetime, int, str], str],
    owner_email_addr: str,
    bakery_name: str,
    now: Optional[dt.datetime] = None,
) -> OrderResult:
    """Validate payload, send confirmations, create calendar event, return OrderResult.

    Side-effect functions are injected so this is unit-testable without network I/O.
    """
    order = validate(payload, now=now)
    order_id = generate_order_id(now=now)

    title, starts_at, duration_min, cal_notes = calendar_event(order, order_id, bakery_name=bakery_name)
    calendar_event_url = create_calendar_event_fn(title, starts_at, duration_min, cal_notes)

    cust_subject, cust_body = customer_email(order, order_id, bakery_name=bakery_name)
    own_subject, own_body = owner_email(order, order_id, bakery_name=bakery_name)
    send_email_fn(order.email, cust_subject, cust_body)
    send_email_fn(owner_email_addr, own_subject, own_body)

    return OrderResult(order_id=order_id, pickup_at=order.pickup_at, calendar_event_url=calendar_event_url)
