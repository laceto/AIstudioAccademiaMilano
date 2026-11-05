"""
gateway/auth.py — 047: API key for the gateway's client endpoints.

POST /submit and GET /status/{job_id} need the header

    X-API-Key: <GATEWAY_API_KEY>

Fail closed: with no usable key configured both endpoints answer 503, so a deploy that
forgot the key is shut, not open. A key shorter than 32 characters or still the
.env.example placeholder counts as not configured.

For local development only, GATEWAY_ALLOW_OPEN_SUBMIT=1 lets requests through when no key
is set. It is ignored as soon as GATEWAY_API_KEY is set.

Public, unchanged: /, /api/showcase, /trading, /health. The Telegram and WhatsApp webhooks
keep their own checks (secret token, Twilio signature).
"""

import hmac
import os
import re

from fastapi import HTTPException, Request

HEADER = "X-API-Key"
MIN_KEY_LEN = 32
_PLACEHOLDER = re.compile(r"^your-|your_key_here|your-key-here|-here$", re.IGNORECASE)


def configured_key() -> str | None:
    key = os.environ.get("GATEWAY_API_KEY", "").strip()
    if len(key) < MIN_KEY_LEN or _PLACEHOLDER.search(key):
        return None
    return key


def _open_mode() -> bool:
    return os.environ.get("GATEWAY_ALLOW_OPEN_SUBMIT", "").strip().lower() in {"1", "true", "yes"}


def api_key_problem(supplied: str | None) -> tuple[int, str] | None:
    """None when the request may go on, else (http status, detail)."""
    key = configured_key()
    if key is None:
        if _open_mode():
            return None
        return 503, "Gateway API key not configured"
    if not supplied or not hmac.compare_digest(supplied.encode(), key.encode()):
        return 401, f"Missing or invalid {HEADER}"
    return None


def require_api_key(request: Request) -> None:
    """FastAPI dependency for the client endpoints."""
    problem = api_key_problem(request.headers.get(HEADER))
    if problem:
        code, detail = problem
        headers = {"WWW-Authenticate": "ApiKey"} if code == 401 else None
        raise HTTPException(status_code=code, detail=detail, headers=headers)
