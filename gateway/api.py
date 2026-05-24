"""
gateway/api.py — Pablo (Platform Engineer)

FastAPI application exposing the Input Gateway to the public internet.

Endpoints:
  POST /submit         Accept a pipeline request (JSON)
  GET  /status/{id}   Poll job status
  POST /webhook/whatsapp  Twilio WhatsApp webhook (Carlos)
  GET  /health        Liveness probe

Run locally:
  uvicorn gateway.api:app --reload --port 8080

Environment variables:
  GATEWAY_HMAC_SECRET   Shared HMAC secret for webhook authentication
"""

import os

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, field_validator

from gateway.middleware import check_rate_limit, verify_hmac
from gateway.pipeline_adapter import PipelineAdapter

app = FastAPI(title="AI Studio Input Gateway", version="1.0.0")
_adapter = PipelineAdapter()


# ── Request / response models ────────────────────────────────────────────────

class SubmitRequest(BaseModel):
    text: str
    channel: str = "api"
    metadata: dict = {}

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("text must not be empty")
        if len(v) > 4000:
            raise ValueError("text exceeds 4000 characters")
        return v

    @field_validator("channel")
    @classmethod
    def channel_valid(cls, v: str) -> str:
        allowed = {"api", "streamlit", "telegram", "whatsapp"}
        if v not in allowed:
            raise ValueError(f"channel must be one of {allowed}")
        return v


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/submit", status_code=status.HTTP_202_ACCEPTED)
async def submit(request: Request, body: SubmitRequest):
    ip = request.client.host if request.client else "unknown"

    if not check_rate_limit(ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded — try again in 60 seconds")

    result = _adapter.submit(
        text=body.text,
        channel=body.channel,
        metadata={**body.metadata, "ip": ip},
    )

    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["result"])

    return result


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    job = _adapter.get_status(job_id)
    if job["status"] == "not_found":
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")
    return job


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    """Twilio WhatsApp webhook — registered here so it runs behind Pablo's rate limiter."""
    body_bytes = await request.body()
    sig = request.headers.get("X-Twilio-Signature", "")

    if not verify_hmac(body_bytes, sig, secret_env="TWILIO_AUTH_TOKEN"):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    # Actual message handling is in gateway/bot_whatsapp.py; this endpoint
    # exists so the URL is registered and HMAC-validated before Carlos's code runs.
    return PlainTextResponse("ok")
