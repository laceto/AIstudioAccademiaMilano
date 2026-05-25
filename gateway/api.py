"""
gateway/api.py — Pablo (Platform Engineer)

FastAPI application exposing the Input Gateway to the public internet.

Endpoints:
  POST /submit              Accept a pipeline request (JSON)
  GET  /status/{id}         Poll job status
  POST /webhook/whatsapp    Twilio WhatsApp webhook (Carlos, HMAC-validated)
  POST /webhook/telegram    Telegram webhook (registered after Cloud Run deploy)
  GET  /health              Liveness probe

Run locally:
  uvicorn gateway.api:app --reload --port 8080

Environment variables:
  GATEWAY_QUEUE_DIR     Queue directory path (default: gateway/queue)
  ANTHROPIC_API_KEY     Claude API key for the queue worker
  OPENAI_API_KEY        OpenAI API key (fallback for queue worker)
  TELEGRAM_BOT_TOKEN    Required for Telegram webhook mode
"""

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

# Load .env from repo root — setdefault so Cloud Run env vars always win
_env_file = Path(__file__).resolve().parent.parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel, field_validator

from gateway.bot_whatsapp import router as whatsapp_router
from gateway.middleware import check_rate_limit
from gateway.pipeline_adapter import PipelineAdapter

_queue_dir = os.environ.get("GATEWAY_QUEUE_DIR", "gateway/queue")
_adapter = PipelineAdapter(queue_dir=_queue_dir)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from gateway.worker import QueueWorker
    worker = QueueWorker(queue_dir=_queue_dir)
    task = asyncio.create_task(worker.run())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    pass


app = FastAPI(title="AI Studio Input Gateway", version="1.0.0", lifespan=lifespan)
app.include_router(whatsapp_router)


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


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    """Telegram update webhook — receives updates from Telegram servers."""
    from telegram import Bot
    from gateway.bot_telegram import _normalize

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise HTTPException(status_code=503, detail="TELEGRAM_BOT_TOKEN not configured")

    try:
        data = await request.json()
    except Exception:
        return {"ok": True}

    message = data.get("message") or data.get("edited_message")
    if not message:
        return {"ok": True}

    text = message.get("text", "").strip()
    chat_id = message.get("chat", {}).get("id")
    user_id = message.get("from", {}).get("id", "anonymous")

    if not text or not chat_id:
        return {"ok": True}

    bot = Bot(token=token)

    if text.startswith("/start"):
        await bot.send_message(
            chat_id=chat_id,
            text=(
                "Benvenuto in AI Studio Accademia Milano!\n\n"
                "Dimmi cosa ti serve e lo costruiamo per te.\n\n"
                "Esempi:\n"
                "• Ho bisogno di un sito per il mio ristorante\n"
                "• Crea una fattura PDF da 500€\n"
                "• Voglio un chatbot per il mio sito\n\n"
                "Scrivi la tua richiesta e penso io al resto."
            ),
        )
        return {"ok": True}

    normalized = _normalize(text)
    if not normalized:
        await bot.send_message(chat_id=chat_id, text="Invia un messaggio di testo con la tua richiesta.")
        return {"ok": True}

    result = _adapter.submit(
        text=normalized,
        channel="telegram",
        metadata={"user_id": user_id, "chat_id": chat_id},
    )

    if result["status"] == "error":
        await bot.send_message(
            chat_id=chat_id,
            text="Non riesco a elaborare questa richiesta. Prova con una diversa.",
        )
    else:
        await bot.send_message(
            chat_id=chat_id,
            text=f"Ricevuto! La tua richiesta è in elaborazione.\n\nJob ID: `{result['job_id']}`",
            parse_mode="Markdown",
        )

    return {"ok": True}
