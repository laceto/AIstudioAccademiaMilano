"""
gateway/bot_whatsapp.py — Carlos (Bot/Integration Engineer)

Twilio WhatsApp webhook handler. Mounts onto Pablo's FastAPI app as a router.
Users send a WhatsApp message → pipeline submission → reply.

The webhook endpoint /webhook/whatsapp is pre-registered in api.py with HMAC
validation. This module adds the full Twilio TwiML response logic.

Mount in api.py:
  from gateway.bot_whatsapp import router as whatsapp_router
  app.include_router(whatsapp_router)

Environment variables:
  TWILIO_ACCOUNT_SID
  TWILIO_AUTH_TOKEN
"""

import base64
import hashlib
import hmac
import logging
import os

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import PlainTextResponse

from config.brand import b, fmt
from gateway.pipeline_adapter import PipelineAdapter

logger = logging.getLogger(__name__)
router = APIRouter()
_adapter = PipelineAdapter()


def _verify_twilio_signature(request: Request, body: bytes) -> bool:
    """Twilio HMAC-SHA1 signature validation (Twilio's own scheme, not generic HMAC-SHA256)."""
    token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    if not token:
        logger.warning("TWILIO_AUTH_TOKEN not set — skipping signature validation")
        return True  # allow in dev; block in prod via env guard

    sig = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url)
    # Twilio canonical string: URL + sorted POST params concatenated
    form_str = ""  # populated after form parsing; validated in endpoint
    canonical = url + form_str
    expected = base64.b64encode(
        hmac.new(token.encode(), canonical.encode(), hashlib.sha1).digest()
    ).decode()
    return hmac.compare_digest(expected, sig)


@router.post("/webhook/whatsapp", response_class=PlainTextResponse)
async def whatsapp_reply(
    request: Request,
    Body: str = Form(default=""),
    From: str = Form(default=""),
    To: str = Form(default=""),
):
    """Full TwiML reply endpoint for Twilio WhatsApp sandbox."""
    token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    if token:
        sig = request.headers.get("X-Twilio-Signature", "")
        raw_form = await request.body()
        # Re-derive canonical with sorted form fields
        form_data = await request.form()
        sorted_params = "".join(f"{k}{v}" for k, v in sorted(form_data.items()))
        canonical = str(request.url) + sorted_params
        expected = base64.b64encode(
            hmac.new(token.encode(), canonical.encode(), hashlib.sha1).digest()
        ).decode()
        if not hmac.compare_digest(expected, sig):
            raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    incoming = Body.strip()
    user_phone = From.replace("whatsapp:", "")

    logger.info(
        "WhatsApp request | from=%s text_length=%d",
        user_phone[-4:] + "****",   # log only last 4 digits
        len(incoming),
    )

    if not incoming:
        return _twiml_reply("Please send a text message describing what you need.")

    result = _adapter.submit(
        text=incoming,
        channel="whatsapp",
        metadata={"user_id": user_phone},
    )

    if result["status"] == "error":
        reply = fmt(b("ui_strings.whatsapp_unknown_product")) + " Please try a different request."
    else:
        reply = (
            f"Got it! Your request is being processed.\n"
            f"Job ID: {result['job_id']}\n\n"
            "You'll receive the result here when it's ready."
        )

    return _twiml_reply(reply)


def _twiml_reply(message: str) -> str:
    safe = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{safe}</Message></Response>'
