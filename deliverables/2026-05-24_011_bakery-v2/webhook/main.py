"""Flask wrapper around templates.web.order_webhook.

Deployable to:
  - Vercel Functions (drop under /api/order.py with the Flask shim)
  - Google Cloud Run via `gcloud run deploy --source .` (uses requirements.txt + Procfile)

Real send/create implementations are imported from existing AI Studio skills:
  - Gmail send: deliverable 002's `gmail_api_send`
  - Calendar:   deliverable 007's google_calendar adapter

Credentials are read from environment variables — never hard-coded
(per CLAUDE.md security constraints).
"""

from __future__ import annotations

import hashlib
import hmac
import os
import json
from flask import Flask, request, jsonify

from templates.web.order_webhook import handle_order, OrderValidationError

app = Flask(__name__)

BAKERY_NAME   = os.environ.get("BAKERY_NAME", "Forno di Marta")
OWNER_EMAIL   = os.environ["MARTA_NOTIFY_EMAIL"]     # required; fail fast at boot
_WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")  # HMAC-SHA256 signing secret


def _verify_signature(raw_body: bytes, header: str | None) -> bool:
    """Return True when WEBHOOK_SECRET is unset (dev) or signature matches."""
    if not _WEBHOOK_SECRET:
        return True
    if not header:
        return False
    expected = "sha256=" + hmac.new(
        _WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, header)


def _gmail_send(to: str, subject: str, body: str) -> None:
    # Stub — real impl wires to deliverables/2026-05-23_002_pdf-email/gmail_send.py
    # Kept as an injectable boundary so unit tests don't touch the network.
    from importlib import import_module
    mod = import_module("deliverables_002_gmail.gmail_send")  # symlink or sys.path entry at deploy time
    mod.send(to=to, subject=subject, body=body)


def _create_calendar_event(title, starts_at, duration_min, notes) -> str:
    from importlib import import_module
    mod = import_module("deliverables_007_calendar.google_adapter")
    return mod.create_event(
        calendar_id=os.environ["GOOGLE_CALENDAR_ID"],
        title=title,
        starts_at=starts_at,
        duration_min=duration_min,
        description=notes,
    )


@app.post("/api/order")
def order_endpoint():
    raw = request.get_data()
    if not _verify_signature(raw, request.headers.get("X-Webhook-Signature")):
        return jsonify(error="invalid_signature"), 401

    try:
        payload = json.loads(raw) if raw else {}
    except Exception:
        return jsonify(error="invalid_json"), 400

    try:
        result = handle_order(
            payload,
            send_email_fn=_gmail_send,
            create_calendar_event_fn=_create_calendar_event,
            owner_email_addr=OWNER_EMAIL,
            bakery_name=BAKERY_NAME,
        )
    except OrderValidationError as e:
        return jsonify(error=e.code), 400
    except Exception:
        # Surface to Sentry if configured; respond opaquely to the client.
        import traceback; traceback.print_exc()
        return jsonify(error="internal_error"), 500

    return jsonify(
        order_id=result.order_id,
        pickup_at=result.pickup_at.isoformat(),
        calendar_event_url=result.calendar_event_url,
    ), 200


if __name__ == "__main__":  # local dev only
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
