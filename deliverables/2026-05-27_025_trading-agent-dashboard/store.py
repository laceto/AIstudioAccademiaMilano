"""
Shared JSON state store — thread-safe, process-safe via atomic rename.

Both the Streamlit dashboard and the FastAPI server read/write this file.
The write path uses a temp-file + rename pattern, which is atomic on Linux/macOS.
"""
import json
import threading
from datetime import datetime
from pathlib import Path

STATE_FILE = Path(__file__).parent / "state.json"
_lock = threading.Lock()

_DEFAULT: dict = {"last_run": None, "agents": {}, "portfolio": {}, "analyses": {}}


def load() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return dict(_DEFAULT)


def _atomic_write(state: dict) -> None:
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
    tmp.replace(STATE_FILE)


def save(state: dict) -> None:
    with _lock:
        _atomic_write(state)


def update_agent(name: str, data: dict) -> None:
    with _lock:
        state = load()
        state.setdefault("agents", {})[name] = data
        _atomic_write(state)


def update_portfolio(portfolio: dict) -> None:
    with _lock:
        state = load()
        state["portfolio"] = portfolio
        state["last_run"] = datetime.now().isoformat()
        _atomic_write(state)


def update_analysis(symbol: str, data: dict) -> None:
    """Cache a techa Orchestrator report keyed by symbol."""
    with _lock:
        state = load()
        state.setdefault("analyses", {})[symbol.upper()] = {
            **data,
            "cached_at": datetime.now().isoformat(),
        }
        _atomic_write(state)


def get_analysis(symbol: str) -> dict | None:
    state = load()
    return state.get("analyses", {}).get(symbol.upper())
