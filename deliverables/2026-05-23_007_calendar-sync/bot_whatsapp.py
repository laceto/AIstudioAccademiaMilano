"""
bot_whatsapp.py — WhatsApp webhook via Twilio + Meta Cloud API.

Twilio Sandbox setup:
    export TWILIO_ACCOUNT_SID=...
    export TWILIO_AUTH_TOKEN=...
    python bot_whatsapp.py
    ngrok http 8080  # set webhook URL in Twilio Console → /whatsapp

Meta Cloud API (production):
    export META_PHONE_NUMBER_ID=...
    export META_ACCESS_TOKEN=...
    export META_VERIFY_TOKEN=aistudio_verify
    Webhook endpoint: /meta-whatsapp
"""

import base64, hashlib, hmac, os
from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
from event_parser import extract_event
from calendar_sync import sync_to_all_calendars

app = Flask(__name__)


@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    if token:
        sig = request.headers.get("X-Twilio-Signature", "")
        canonical = request.url + "".join(f"{k}{v}" for k, v in sorted(request.form.items()))
        expected = base64.b64encode(hmac.new(token.encode(), canonical.encode(), hashlib.sha1).digest()).decode()
        if not hmac.compare_digest(expected, sig):
            return Response("Forbidden", status=403)
    incoming = request.form.get("Body", "").strip()
    try:
        event = extract_event(incoming)
        results = sync_to_all_calendars(event)
        ok = [r.provider for r in results if r.status == "ok"]
        reply = f"📅 {event.title}\n{event.date} {event.start_time}\n" + "\n".join(f"✅ {p}" for p in ok)
    except Exception as e:
        reply = f"❌ {e}"
    resp = MessagingResponse(); resp.message(reply)
    return str(resp)


@app.route("/meta-whatsapp", methods=["GET", "POST"])
def meta_whatsapp():
    if request.method == "GET":
        if request.args.get("hub.verify_token") == os.environ.get("META_VERIFY_TOKEN", "aistudio_verify"):
            return request.args.get("hub.challenge", "")
        return Response("Forbidden", status=403)
    try:
        entry = request.get_json(force=True)["entry"][0]["changes"][0]["value"]
        msg = entry["messages"][0]; text = msg["text"]["body"]; to = msg["from"]
        phone_id = entry["metadata"]["phone_number_id"]
    except (KeyError, IndexError):
        return Response("ok", status=200)
    try:
        ev = extract_event(text)
        results = sync_to_all_calendars(ev)
        ok = [r.provider for r in results if r.status == "ok"]
        reply = f"📅 {ev.title} | {ev.date} {ev.start_time}\n" + ", ".join(ok) + " ✅"
    except Exception as e:
        reply = f"❌ {e}"
    import requests as req
    req.post(f"https://graph.facebook.com/v19.0/{phone_id}/messages",
             headers={"Authorization": f"Bearer {os.environ.get('META_ACCESS_TOKEN', '')}"},
             json={"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": reply}})
    return Response("ok", status=200)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"[bot_whatsapp] Listening :{port}/whatsapp")
    app.run(host="0.0.0.0", port=port)
