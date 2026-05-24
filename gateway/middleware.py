"""
gateway/middleware.py — Pablo (Platform Engineer)

Shared security helpers used by api.py and Carlos's bot handlers:
  - verify_hmac()   HMAC-SHA256 signature validation
  - check_rate_limit()  per-IP sliding-window rate limiter
"""

import hashlib
import hmac
import os
import time
from collections import defaultdict
from threading import Lock

_RATE_LIMIT = 10       # max requests per window
_WINDOW_SEC = 60.0     # rolling window in seconds

_buckets: dict[str, list[float]] = defaultdict(list)
_lock = Lock()


def verify_hmac(payload: bytes, signature: str, secret_env: str = "GATEWAY_HMAC_SECRET") -> bool:
    """Return True if HMAC-SHA256(payload, secret) matches signature.

    Secret is read from the env var named by secret_env.
    Returns False (not an exception) if the secret is unset — caller decides
    whether to block or allow unsigned traffic.
    """
    secret = os.environ.get(secret_env, "").encode()
    if not secret:
        return False
    expected = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.lower())


def check_rate_limit(ip: str, limit: int = _RATE_LIMIT, window: float = _WINDOW_SEC) -> bool:
    """Sliding-window rate limiter. Returns True if request is allowed."""
    now = time.monotonic()
    with _lock:
        _buckets[ip] = [t for t in _buckets[ip] if now - t < window]
        if len(_buckets[ip]) >= limit:
            return False
        _buckets[ip].append(now)
        return True
