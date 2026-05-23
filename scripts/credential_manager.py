import time
from pathlib import Path
from typing import Optional


SUPPORTED_PROVIDERS = {
    "gmail_oauth",
    "openai_api_key",
    "streamlit_github_oauth",
    "anthropic_api_key",
    "groq_api_key",
    "google_calendar_oauth",
    "microsoft_graph_oauth",
    "apple_app_password",
    "twilio_auth_token",
    "telegram_bot_token",
    "github_token",
}


class CredentialManager:
    """Session-scoped credential store. Secrets never appear in repr or on disk."""

    def __init__(self, ttl_seconds: int = 3600, storage_dir: Optional[Path] = None):
        self._ttl = ttl_seconds
        self._store: dict = {}  # key -> (secret, expires_at)
        # storage_dir accepted for interface compatibility; plaintext is never written
        self._storage_dir = storage_dir

    def supports(self, provider: str) -> bool:
        return provider in SUPPORTED_PROVIDERS

    def store(self, key: str, secret: str) -> None:
        expires_at = time.monotonic() + self._ttl  # ttl=0 means already expired
        self._store[key] = (secret, expires_at)

    def get(self, key: str) -> Optional[str]:
        entry = self._store.get(key)
        if entry is None:
            return None
        secret, expires_at = entry
        if time.monotonic() >= expires_at:
            del self._store[key]
            return None
        return secret

    def is_available(self, key: str) -> bool:
        return self.get(key) is not None

    def revoke(self, key: str) -> None:
        self._store.pop(key, None)

    def close(self) -> None:
        self._store.clear()

    def __repr__(self) -> str:
        return f"CredentialManager(keys={list(self._store.keys())}, ttl={self._ttl}s)"

    def __str__(self) -> str:
        return repr(self)
