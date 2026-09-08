"""
Local Telegram stack launcher — AI Studio Accademia Milano

Starts the four processes that make the Telegram channels work on a laptop,
in dependency order, and shuts them all down together on Ctrl+C:

  1. scripts.rag.api_server   RAG API on 127.0.0.1:8000 (localhost only)
  2. gateway.rag_bot_telegram RAG bot   — polls Telegram, queries (1)
  3. gateway.bot_telegram     pipeline bot — polls Telegram, writes to the queue
  4. gateway.worker           queue worker — classifies jobs, replies via Telegram

No public URL is needed: every bot polls, so all traffic is outbound.

Usage:
    python scripts/run_local_stack.py
    python scripts/run_local_stack.py --no-rag      # pipeline bot + worker only
    python scripts/run_local_stack.py --port 8100   # if 8000 is taken

Run `python scripts/check_telegram.py` first — a webhook left registered on a
polling bot makes it silently deaf, and this launcher cannot detect that for you.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Same .env convention as the bots — so pre-flight sees what they will see
_ENV_FILE = REPO_ROOT / ".env"
if _ENV_FILE.exists():
    for _line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

_procs: list[tuple[str, subprocess.Popen]] = []
_stopping = threading.Event()


def _pump(label: str, proc: subprocess.Popen) -> None:
    """Stream a child's output with a prefix so four logs stay readable in one terminal."""
    assert proc.stdout is not None
    for line in proc.stdout:
        if _stopping.is_set():
            return
        print(f"[{label}] {line.rstrip()}", flush=True)


def _spawn(label: str, args: list[str]) -> subprocess.Popen:
    kwargs = {}
    if sys.platform == "win32":
        # so Ctrl+C reaches the group, not just this script
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True

    proc = subprocess.Popen(
        args,
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        **kwargs,
    )
    _procs.append((label, proc))
    threading.Thread(target=_pump, args=(label, proc), daemon=True).start()
    print(f"  started {label} (pid {proc.pid})")
    return proc


def _wait_for_health(port: int, timeout: float = 180.0) -> bool:
    """The RAG API pre-warms FAISS on startup, so first boot is slow. Poll /health."""
    url = f"http://127.0.0.1:{port}/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _stopping.is_set():
            return False
        for _, proc in _procs:
            if proc.poll() is not None:
                return False  # it died while we waited
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(2)
    return False


def _shutdown(*_args) -> None:
    if _stopping.is_set():
        return
    _stopping.set()
    print("\nStopping...")
    for label, proc in reversed(_procs):
        if proc.poll() is None:
            proc.terminate()
    deadline = time.time() + 10
    for label, proc in reversed(_procs):
        try:
            proc.wait(timeout=max(0.1, deadline - time.time()))
        except subprocess.TimeoutExpired:
            print(f"  {label} did not stop — killing")
            proc.kill()
    print("All stopped.")


def _preflight(want_rag: bool) -> list[str]:
    problems = []
    required = {"TELEGRAM_BOT_TOKEN": "pipeline bot"}
    if want_rag:
        required["TELEGRAM_RAG_BOT_TOKEN"] = "RAG bot"
    for var, who in required.items():
        val = os.environ.get(var, "").strip()
        if not val or val.startswith("your-"):
            problems.append(f"{var} is not set ({who}) — see .env.example")

    pipeline = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    rag = os.environ.get("TELEGRAM_RAG_BOT_TOKEN", "").strip()
    if want_rag and pipeline and pipeline == rag:
        problems.append(
            "TELEGRAM_BOT_TOKEN and TELEGRAM_RAG_BOT_TOKEN are the same token — "
            "one bot cannot be polled by two processes. Create a second bot via @BotFather."
        )

    if not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"):
        problems.append("Neither ANTHROPIC_API_KEY nor OPENAI_API_KEY is set — the worker cannot classify jobs.")

    if want_rag and not (REPO_ROOT / "data" / "vectorstore" / "repo" / "index.faiss").exists():
        problems.append("data/vectorstore/repo/index.faiss missing — run `python -m scripts.embed_index`.")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8000, help="RAG API port (default 8000)")
    parser.add_argument("--no-rag", action="store_true", help="Skip the RAG API and RAG bot")
    args = parser.parse_args()
    want_rag = not args.no_rag

    problems = _preflight(want_rag)
    if problems:
        print("Pre-flight failed:\n")
        for p in problems:
            print(f"  - {p}")
        return 1

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    py = sys.executable
    print("Starting local Telegram stack (Ctrl+C to stop)\n")

    try:
        if want_rag:
            _spawn("rag-api", [py, "-m", "uvicorn", "scripts.rag.api_server:app",
                               "--host", "127.0.0.1", "--port", str(args.port)])
            print("  waiting for RAG API to pre-warm the vectorstore...")
            if not _wait_for_health(args.port):
                print("\nRAG API never became healthy — see the [rag-api] lines above.")
                _shutdown()
                return 1
            print("  RAG API healthy")

            # the RAG bot reads this; make sure it matches the port we actually used
            os.environ["RAG_API_URL"] = f"http://127.0.0.1:{args.port}"
            _spawn("rag-bot", [py, "-m", "gateway.rag_bot_telegram"])

        _spawn("pipeline-bot", [py, "-m", "gateway.bot_telegram"])
        _spawn("worker", [py, "-m", "gateway.worker"])

        print("\nAll processes up. Message your bots to test.\n")

        while not _stopping.is_set():
            for label, proc in _procs:
                if proc.poll() is not None:
                    print(f"\n[{label}] exited with code {proc.returncode} — stopping the stack.")
                    _shutdown()
                    return 1
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        _shutdown()

    return 0


if __name__ == "__main__":
    sys.exit(main())
