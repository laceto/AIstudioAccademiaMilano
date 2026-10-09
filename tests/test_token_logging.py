"""No process that talks to Telegram may log request URLs.

The Bot API puts the bot token in the URL path (https://api.telegram.org/bot<TOKEN>/sendMessage),
and httpx logs every request URL at INFO. The gateway was fixed on 2026-10-09 morning; the
pipeline worker and the RAG API, which send Telegram messages too, were found logging the token
the same afternoon. Each module is imported in a fresh interpreter, with httpx pre-set to INFO
the way a library default or a basicConfig could leave it.
"""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

MODULES = [
    "gateway.api",
    "gateway.pipeline_worker",
    "scripts.rag.api_server",
    "gateway.bot_telegram",
    "gateway.rag_bot_telegram",
]


@pytest.mark.parametrize("module", MODULES)
def test_importing_the_module_silences_http_request_logs(module):
    code = (
        "import logging, importlib\n"
        "logging.getLogger('httpx').setLevel(logging.INFO)\n"
        "logging.getLogger('httpcore').setLevel(logging.INFO)\n"
        f"importlib.import_module({module!r})\n"
        "print(logging.getLogger('httpx').getEffectiveLevel(), logging.getLogger('httpcore').getEffectiveLevel())\n"
    )
    res = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert res.returncode == 0, res.stderr[-400:]
    httpx_level, httpcore_level = map(int, res.stdout.split()[-2:])
    assert httpx_level >= 30 and httpcore_level >= 30, f"{module} leaves httpx at INFO"
