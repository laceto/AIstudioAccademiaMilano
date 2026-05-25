"""
gateway/worker.py — Queue processor

Polls gateway/queue/ for pending jobs, runs each through Stacy (Claude Haiku)
for intent classification, writes result back to the job file, and notifies
Telegram users async.

Run standalone:
  python -m gateway.worker

Started automatically by api.py lifespan when embedded in the FastAPI container.

Environment variables:
  ANTHROPIC_API_KEY    Required for pipeline processing (Claude Haiku)
  GATEWAY_QUEUE_DIR    Queue directory (default: gateway/queue)
  TELEGRAM_BOT_TOKEN   Required to reply to Telegram users
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_STACY_SYSTEM = """You are Stacy, intake agent for AI Studio Accademia Milano.
Classify the request and return ONLY a valid JSON object — no prose, no markdown:
{
  "intent": "<brief snake_case intent name>",
  "product_type": "<one of: static_landing_page|premium_landing_page|commercial_landing_page|pdf_document|invoice_pdf|strategic_report|chatbot_app|email_delivery|rag_knowledge_base|calendar_integration|weather_dashboard|agent_deploy_streamlit|unknown_product>",
  "confidence": <float 0.0-1.0>,
  "summary": "<one sentence: what the user needs>",
  "needs_review": <true if confidence < 0.8 or product_type is unknown_product, else false>
}"""

_PRICES: dict[str, float | None] = {
    "static_landing_page": 9.90,
    "premium_landing_page": 29.90,
    "commercial_landing_page": 45.90,
    "pdf_document": 1.90,
    "invoice_pdf": 3.90,
    "strategic_report": 4.90,
    "chatbot_app": 19.90,
    "email_delivery": 0.50,
    "rag_knowledge_base": 29.90,
    "calendar_integration": 14.90,
    "weather_dashboard": 9.90,
    "agent_deploy_streamlit": 19.90,
    "unknown_product": None,
}


class QueueWorker:
    def __init__(self, queue_dir: str | None = None, poll_interval: float = 5.0):
        from gateway.pipeline_adapter import PipelineAdapter

        queue_dir = queue_dir or os.environ.get("GATEWAY_QUEUE_DIR", "gateway/queue")
        self.queue_dir = Path(queue_dir)
        self.adapter = PipelineAdapter(queue_dir=str(self.queue_dir))
        self.poll_interval = poll_interval

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            import anthropic
            self.claude: object = anthropic.AsyncAnthropic(api_key=api_key)
        else:
            self.claude = None
            logger.warning("[worker] ANTHROPIC_API_KEY not set — jobs will be queued but not processed")

    async def classify(self, text: str) -> dict:
        """Run Stacy classification via Claude Haiku. Returns classification dict."""
        if not self.claude:
            return {
                "intent": "unknown",
                "product_type": "unknown_product",
                "confidence": 0.0,
                "summary": text[:80],
                "needs_review": True,
            }

        message = await self.claude.messages.create(  # type: ignore[union-attr]
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            system=_STACY_SYSTEM,
            messages=[{"role": "user", "content": text}],
        )
        raw = message.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())

    def _build_reply(self, job: dict, cls: dict) -> tuple[str, str]:
        """Return (new_status, reply_text) from classification result."""
        product = cls.get("product_type", "unknown_product")
        price = _PRICES.get(product)
        summary = cls.get("summary", job["text"][:60])

        if cls.get("needs_review") or price is None:
            return "needs_review", (
                f"Richiesta ricevuta: {summary}\n\n"
                "Questo tipo di richiesta richiede l'approvazione di Luigi prima di procedere.\n"
                f"Job ID: `{job['job_id']}`"
            )

        return "classified", (
            f"Richiesta ricevuta: {summary}\n\n"
            f"Prodotto: {product.replace('_', ' ').title()}\n"
            f"Prezzo: EUR {price:.2f}\n\n"
            f"Il tuo deliverable è in lavorazione.\nJob ID: `{job['job_id']}`"
        )

    async def _notify_telegram(self, chat_id: str | int, text: str) -> None:
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        if not token or not chat_id:
            return
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as http:
                await http.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
                )
        except Exception as exc:
            logger.warning("[worker] Telegram notify failed for chat_id=%s: %s", chat_id, exc)

    async def _process(self, job: dict) -> None:
        job_file = self.queue_dir / f"{job['job_id']}.json"

        job["status"] = "processing"
        job_file.write_text(json.dumps(job, indent=2, ensure_ascii=False), encoding="utf-8")

        try:
            cls = await self.classify(job["text"])
        except Exception as exc:
            logger.error("[worker] classify failed for job %s: %s", job["job_id"], exc)
            job.update(
                status="error",
                result=f"Classification failed: {exc}",
                processed_at=datetime.now(timezone.utc).isoformat(),
            )
            job_file.write_text(json.dumps(job, indent=2, ensure_ascii=False), encoding="utf-8")
            return

        status, reply = self._build_reply(job, cls)
        job.update(
            status=status,
            result=reply,
            classification=cls,
            processed_at=datetime.now(timezone.utc).isoformat(),
        )
        job_file.write_text(json.dumps(job, indent=2, ensure_ascii=False), encoding="utf-8")

        logger.info("[worker] job %s -> %s (product=%s)", job["job_id"], status, cls.get("product_type"))

        if job.get("channel") == "telegram":
            chat_id = job.get("metadata", {}).get("chat_id")
            await self._notify_telegram(chat_id, reply)

    async def run(self) -> None:
        logger.info("[worker] started — poll=%.0fs queue=%s", self.poll_interval, self.queue_dir)
        while True:
            try:
                pending = self.adapter.list_pending()
                if pending:
                    await asyncio.gather(*[self._process(j) for j in pending])
            except Exception as exc:
                logger.error("[worker] loop error: %s", exc)
            await asyncio.sleep(self.poll_interval)


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        level=logging.INFO,
    )
    asyncio.run(QueueWorker().run())
