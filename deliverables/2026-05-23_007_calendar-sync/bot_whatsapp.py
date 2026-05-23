"""
bot_whatsapp.py — WhatsApp webhook via Twilio: receive a message, create calendar event.

Setup (Twilio Sandbox):
    1. Create a Twilio account at twilio.com
    2. Enable WhatsApp Sandbox in Twilio Console
    3. Set env vars: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM
    4. Run: python bot_whatsapp.py
    5. Expose with ngrok: ngrok http 8080
    6. Set Twilio Sandbox webhook URL to https://YOUR_NGROK_URL/whatsapp

Alternative (Meta Cloud API):
    Use META_PHONE_NUMBER_ID and META_ACCESS_TOKEN instead.
    Webhook path: /meta-whatsapp

Message in WhatsApp:
    "Pranzo con Marco domani alle 13 in Via Torino 5, Milano"
"""

import hashlib
import hmac
import os

from flask import Flask, request, Response
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

from event_parser import extract_event
from calendar_sync import sync_to_all_calendars

app = Flask(__name__)


def _verify_twilio_signature(req) -> bool:
    token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    sig   = req.headers.get("X-Twilio-Signature", "")
    url   = req.url
    params = req.form.to_dict()
    # Build canonical string
    canonical = url + "".join(f"{k}{v}" for k, v in sorted(params.items()))
    expected  = hmac.new(token.encode(), canonical.encode(), hashlib.sha1).digest()
    import base64
    return hmac.compare_digest(base64.b64encode(expected).decode(), sig)


@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    if os.environ.get("TWILIO_AUTH_TOKEN") and not _verify_twilio_signature(request):
        return Response("Forbidden", status=403)

    incoming = request.form.get("Body", "").strip()
    from_number = request.form.get("From", "")

    try:
        event = extract_event(incoming)
        results = sync_to_all_calendars(event)
    except Exception as e:
        resp = MessagingResponse()
        resp.message(f"❌ Error: {e}")
        return str(resp)

    ok_providers = [r.provider for r in results if r.status == "ok"]
    err_providers = [(r.provider, r.error) for r in results if r.status == "error"]
    skipped = [r.provider for r in results if r.status == "skipped"]

    lines = [f"📅 {event.title}", f"{event.date} {event.start_time}–{event.end_time}"]
    if event.location:
        lines.append(f"📍 {event.location}")
    lines.append("")
    for p in ok_providers:
        lines.append(f"✅ {p}")
    for p, err in err_providers:
        lines.append(f"❌ {p}: {err}")

    resp = MessagingResponse()
    resp.message("\n".join(lines))
    return str(resp)


@app.route("/meta-whatsapp", methods=["GET", "POST"])
def meta_whatsapp_webhook():
    """Meta Cloud API webhook (for production WhatsApp Business accounts)."""
    if request.method == "GET":
        # Verification challenge
        verify_token = os.environ.get("META_VERIFY_TOKEN", "aistudio_verify")
        if request.args.get("hub.verify_token") == verify_token:
            return request.args.get("hub.challenge", "")
        return Response("Forbidden", status=403)

    data = request.get_json(force=True, silent=True) or {}
    try:
        entry = data["entry"][0]["changes"][0]["value"]
        message = entry["messages"][0]
        text = message["text"]["body"]
        phone_number_id = entry["metadata"]["phone_number_id"]
        to = message["from"]
    except (KeyError, IndexError):
        return Response("ok", status=200)

    try:
        event = extract_event(text)
        results = sync_to_all_calendars(event)
        ok = [r.provider for r in results if r.status == "ok"]
        reply = f"📅 {event.title} | {event.date} {event.start_time}\n" + ", ".join(ok) + " ✅"
    except Exception as e:
        reply = f"❌ {e}"

    # Send reply via Meta Graph API
    import requests as req_lib
    token = os.environ.get("META_ACCESS_TOKEN", "")
    req_lib.post(
        f"https://graph.facebook.com/v19.0/{phone_number_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json={"messaging_product": "whatsapp", "to": to,
              "type": "text", "text": {"body": reply}},
    )
    return Response("ok", status=200)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"[bot_whatsapp] Listening on :{port}/whatsapp")
    print("Expose with: ngrok http", port)
    app.run(host="0.0.0.0", port=port)
