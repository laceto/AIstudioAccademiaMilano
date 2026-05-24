"""
ISS-011 / Request 011: Order webhook for bakery v2.

Tests the reusable handler in templates/web/order_webhook.py.
Side-effect functions are injected, so no network is touched.
"""

from __future__ import annotations

import datetime as dt

import pytest

from templates.web.order_webhook import (
    MAX_NOTES_LEN,
    Order,
    OrderResult,
    OrderValidationError,
    calendar_event,
    customer_email,
    generate_order_id,
    handle_order,
    owner_email,
    validate,
)


# ── fixtures ─────────────────────────────────────────────────────────────────────

NOW = dt.datetime(2026, 5, 24, 12, 0, tzinfo=dt.timezone.utc)
PICKUP = (NOW + dt.timedelta(hours=48)).isoformat()


@pytest.fixture
def base_payload() -> dict:
    return {
        "product":   "Torta della nonna",
        "quantity":  1,
        "pickup_at": PICKUP,
        "name":      "Anna Bianchi",
        "email":     "anna@example.com",
        "phone":     "+39 333 1234567",
        "notes":     "Senza zucchero raffinato",
    }


@pytest.fixture
def fake_email_log() -> list[tuple[str, str, str]]:
    return []


@pytest.fixture
def fake_calendar_log() -> list[tuple]:
    return []


@pytest.fixture
def send_email_fn(fake_email_log):
    def _send(to, subject, body):
        fake_email_log.append((to, subject, body))
    return _send


@pytest.fixture
def create_calendar_event_fn(fake_calendar_log):
    def _create(title, starts_at, duration_min, notes):
        fake_calendar_log.append((title, starts_at, duration_min, notes))
        return "https://calendar.google.com/event/fake-123"
    return _create


# ── validation: happy path ───────────────────────────────────────────────────────

def test_validate_returns_typed_order(base_payload):
    order = validate(base_payload, now=NOW)
    assert isinstance(order, Order)
    assert order.product == "Torta della nonna"
    assert order.quantity == 1
    assert order.email == "anna@example.com"
    assert order.pickup_at.tzinfo is not None  # always tz-aware


def test_validate_strips_whitespace_from_strings():
    payload = {
        "product":   "  Pane  ",
        "quantity":  2,
        "pickup_at": PICKUP,
        "name":      "  Anna  ",
        "email":     "  anna@example.com  ",
    }
    order = validate(payload, now=NOW)
    assert order.product == "Pane"
    assert order.name == "Anna"
    assert order.email == "anna@example.com"


# ── validation: error paths (each maps to a documented wire-stable code) ─────────

@pytest.mark.parametrize("field", ["product", "quantity", "pickup_at", "name", "email"])
def test_validate_rejects_missing_required_field(base_payload, field):
    del base_payload[field]
    with pytest.raises(OrderValidationError) as exc:
        validate(base_payload, now=NOW)
    assert exc.value.code == f"missing_field:{field}"


@pytest.mark.parametrize("email", ["", "not-an-email", "foo@", "@bar", "spaces in@here.com"])
def test_validate_rejects_bad_email(base_payload, email):
    base_payload["email"] = email
    with pytest.raises(OrderValidationError) as exc:
        validate(base_payload, now=NOW)
    # Empty string is caught as missing_field first; both are valid rejections.
    assert exc.value.code in {"invalid_email", "missing_field:email"}


@pytest.mark.parametrize("q", [0, -1, 51, 9999, "abc"])
def test_validate_rejects_bad_quantity(base_payload, q):
    base_payload["quantity"] = q
    with pytest.raises(OrderValidationError) as exc:
        validate(base_payload, now=NOW)
    assert exc.value.code == "quantity_out_of_range"


def test_validate_rejects_pickup_in_past(base_payload):
    base_payload["pickup_at"] = (NOW - dt.timedelta(hours=1)).isoformat()
    with pytest.raises(OrderValidationError) as exc:
        validate(base_payload, now=NOW)
    assert exc.value.code == "pickup_in_past"


def test_validate_rejects_pickup_too_soon(base_payload):
    # 12h ahead — inside the 24h minimum lead time
    base_payload["pickup_at"] = (NOW + dt.timedelta(hours=12)).isoformat()
    with pytest.raises(OrderValidationError) as exc:
        validate(base_payload, now=NOW)
    assert exc.value.code == "pickup_too_soon"


def test_validate_rejects_malformed_pickup(base_payload):
    base_payload["pickup_at"] = "not a date"
    with pytest.raises(OrderValidationError):
        validate(base_payload, now=NOW)


def test_validate_rejects_oversized_notes(base_payload):
    base_payload["notes"] = "x" * (MAX_NOTES_LEN + 1)
    with pytest.raises(OrderValidationError) as exc:
        validate(base_payload, now=NOW)
    assert exc.value.code == "notes_too_long"


# ── order_id format ──────────────────────────────────────────────────────────────

def test_generate_order_id_format():
    oid = generate_order_id(now=NOW)
    # ORD-YYYY-XXXX (4 hex chars uppercase)
    assert oid.startswith("ORD-2026-")
    suffix = oid.split("-")[-1]
    assert len(suffix) == 4
    assert all(c in "0123456789ABCDEF" for c in suffix)


def test_generate_order_id_is_random():
    ids = {generate_order_id(now=NOW) for _ in range(100)}
    # 4 hex chars = 65536 possibilities; collisions in 100 draws are vanishingly rare.
    assert len(ids) > 95


# ── composition ──────────────────────────────────────────────────────────────────

def test_customer_email_includes_key_fields(base_payload):
    order = validate(base_payload, now=NOW)
    subject, body = customer_email(order, "ORD-2026-AAAA", bakery_name="Forno di Marta")
    assert "Forno di Marta" in subject
    assert "ORD-2026-AAAA" in subject
    assert "Anna Bianchi" in body
    assert "Torta della nonna" in body
    assert "ORD-2026-AAAA" in body


def test_owner_email_includes_contact_details(base_payload):
    order = validate(base_payload, now=NOW)
    subject, body = owner_email(order, "ORD-2026-AAAA", bakery_name="Forno di Marta")
    assert "Torta della nonna" in subject
    assert "anna@example.com" in body
    assert "+39 333 1234567" in body
    assert "Senza zucchero raffinato" in body


def test_calendar_event_uses_pickup_time(base_payload):
    order = validate(base_payload, now=NOW)
    title, starts_at, duration_min, notes = calendar_event(order, "ORD-2026-AAAA", bakery_name="Forno di Marta")
    assert "Torta della nonna" in title
    assert "Anna Bianchi" in title
    assert "ORD-2026-AAAA" in title
    assert starts_at == order.pickup_at
    assert duration_min == 15
    assert "anna@example.com" in notes


# ── full dispatch ────────────────────────────────────────────────────────────────

def test_handle_order_full_happy_path(base_payload, send_email_fn, create_calendar_event_fn,
                                     fake_email_log, fake_calendar_log):
    result = handle_order(
        base_payload,
        send_email_fn=send_email_fn,
        create_calendar_event_fn=create_calendar_event_fn,
        owner_email_addr="marta@example.com",
        bakery_name="Forno di Marta",
        now=NOW,
    )

    # Returns a proper OrderResult.
    assert isinstance(result, OrderResult)
    assert result.order_id.startswith("ORD-2026-")
    assert result.calendar_event_url == "https://calendar.google.com/event/fake-123"

    # Calendar event was created.
    assert len(fake_calendar_log) == 1

    # Two emails: customer + owner, in that order.
    assert len(fake_email_log) == 2
    assert fake_email_log[0][0] == "anna@example.com"
    assert fake_email_log[1][0] == "marta@example.com"


def test_handle_order_does_not_send_emails_on_validation_failure(send_email_fn, create_calendar_event_fn,
                                                                  fake_email_log, fake_calendar_log):
    bad_payload = {"product": "x", "quantity": 1, "pickup_at": "nonsense",
                   "name": "x", "email": "x@x.com"}
    with pytest.raises(OrderValidationError):
        handle_order(
            bad_payload,
            send_email_fn=send_email_fn,
            create_calendar_event_fn=create_calendar_event_fn,
            owner_email_addr="marta@example.com",
            bakery_name="Forno di Marta",
            now=NOW,
        )
    assert fake_email_log == []
    assert fake_calendar_log == []
