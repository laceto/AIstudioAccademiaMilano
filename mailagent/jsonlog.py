"""One JSON object per line on stdout: Cloud Logging reads `severity` and `message` and keeps the rest as fields.

Pass structured fields with logger.info("...", extra={"fields": {...}}). Never put tokens or mail bodies in them.
"""

from __future__ import annotations

import json
import logging
import sys


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {"severity": record.levelname, "message": record.getMessage(), "logger": record.name}
        out.update(getattr(record, "fields", None) or {})
        if record.exc_info:
            out["exception"] = self.formatException(record.exc_info)
        return json.dumps(out, ensure_ascii=False, default=str)


def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.ERROR)
