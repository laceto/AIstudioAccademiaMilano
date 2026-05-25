"""
Shared settings I/O — AI Studio Accademia Milano.

Atomic write via temp-file + os.replace eliminates torn writes.
Advisory lock via .lock file prevents concurrent read-modify-write races.
"""

import contextlib
import json
import os
import tempfile
import time
from pathlib import Path


_MOJIBAKE_BYTES = [
    (b"\xc3\xa2\xe2\x82\xac\"", b" \xe2\x80\x94 "),
    (b"\xc3\xa2\xe2\x82\xac\xe2\x80\x9c", b" \xe2\x80\x94 "),
    (b"\xc3\xa2\xe2\x82\xac\xe2\x80\x9d", b" \xe2\x80\x94 "),
    (b"\xc3\xa2\xe2\x82\xac\x94", b" \xe2\x80\x94 "),
    (b"\xe2\x80\x9c", b"\""),
    (b"\xe2\x80\x9d", b"\""),
]

_LOCK_MAX_AGE_SEC = 60.0


def _sanitize_json_bytes(raw: bytes) -> bytes:
    for bad, good in _MOJIBAKE_BYTES:
        raw = raw.replace(bad, good)
    return raw


def load_settings(settings_path: str) -> dict:
    raw = Path(settings_path).read_bytes()
    try:
        return json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        fixed = _sanitize_json_bytes(raw)
        return json.loads(fixed.decode("utf-8", errors="replace"))


def save_settings(settings: dict, settings_path: str) -> None:
    """Atomically write settings via unique temp file + os.replace (no torn writes)."""
    path = Path(settings_path)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    print(f"[settings_io] Settings saved to {path.name}")


@contextlib.contextmanager
def settings_lock(settings_path: str, timeout: float = 10.0):
    """Advisory lock to prevent concurrent read-modify-write on the same file.

    Uses a .lock sentinel file. Stale locks older than _LOCK_MAX_AGE_SEC are
    auto-removed so a crashed process cannot block the studio indefinitely.
    """
    lock_path = Path(settings_path).with_suffix(".lock")

    if lock_path.exists():
        try:
            age = time.time() - lock_path.stat().st_mtime
            if age > _LOCK_MAX_AGE_SEC:
                print(f"[settings_io] Removing stale lock (age={age:.0f}s)")
                lock_path.unlink(missing_ok=True)
        except OSError:
            pass

    deadline = time.monotonic() + timeout
    acquired = False
    while time.monotonic() < deadline:
        try:
            lock_path.touch(exist_ok=False)
            acquired = True
            break
        except FileExistsError:
            time.sleep(0.1)

    if not acquired:
        print(f"[settings_io] WARNING: could not acquire lock within {timeout}s — proceeding without lock")
    try:
        yield
    finally:
        if acquired:
            lock_path.unlink(missing_ok=True)
