"""
gateway/pipeline_adapter.py — Pablo (Platform Engineer)

Canonical bridge between any input channel and the 6-agent pipeline.
Accepts (text, channel, metadata), sanitizes, queues the job, returns
{job_id, status, result}.

Stacy picks up jobs from gateway/queue/ and processes them through the pipeline.
"""

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path


_CONTROL_CHAR_RE = re.compile(r"[^\x09\x0A\x0D\x20-\x7E\x80-\xFF]")
_MAX_TEXT_LEN = 4000
_ALLOWED_CHANNELS = {"api", "streamlit", "telegram", "whatsapp"}


class PipelineAdapter:
    def __init__(self, queue_dir: str = "gateway/queue"):
        self.queue_dir = Path(queue_dir)
        self.queue_dir.mkdir(parents=True, exist_ok=True)

    def submit(self, text: str, channel: str, metadata: dict) -> dict:
        """Normalize input and queue for pipeline processing.

        Returns:
            {"job_id": str, "status": "queued"|"error", "result": None|str}
        """
        if channel not in _ALLOWED_CHANNELS:
            return {"job_id": None, "status": "error", "result": f"Unknown channel: {channel}"}

        clean = self._sanitize(text)
        if not clean:
            return {"job_id": None, "status": "error", "result": "Empty request after sanitization"}

        job_id = uuid.uuid4().hex[:10]
        now = datetime.now(timezone.utc).isoformat()

        job = {
            "job_id": job_id,
            "channel": channel,
            "text": clean,
            "metadata": {
                "user_id": str(metadata.get("user_id", "anonymous")),
                "chat_id": str(metadata.get("chat_id", "")),
                "ip": str(metadata.get("ip", "")),
                "text_length": len(clean),
                "timestamp": now,
            },
            "status": "queued",
            "result": None,
            "created_at": now,
        }

        job_file = self.queue_dir / f"{job_id}.json"
        job_file.write_text(json.dumps(job, indent=2, ensure_ascii=False), encoding="utf-8")

        return {"job_id": job_id, "status": "queued", "result": None}

    def get_status(self, job_id: str) -> dict:
        job_file = self.queue_dir / f"{job_id}.json"
        if not job_file.exists():
            return {"job_id": job_id, "status": "not_found", "result": None}
        return json.loads(job_file.read_text(encoding="utf-8"))

    def list_pending(self) -> list[dict]:
        """Return all queued jobs, oldest first."""
        jobs = []
        for f in sorted(self.queue_dir.glob("*.json")):
            try:
                job = json.loads(f.read_text(encoding="utf-8"))
                if job.get("status") == "queued":
                    jobs.append(job)
            except (json.JSONDecodeError, OSError):
                continue
        return jobs

    def _sanitize(self, text: str) -> str:
        clean = _CONTROL_CHAR_RE.sub("", text)
        clean = clean.replace("\r\n", "\n").replace("\r", "\n")
        return clean[:_MAX_TEXT_LEN].strip()
