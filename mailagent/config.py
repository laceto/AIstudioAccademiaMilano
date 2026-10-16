"""accounts.yaml -> AccountConfig list. One block per mailbox; ids must be unique."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class AccountConfig:
    id: str
    provider: str  # key in the provider registry: gmail, outlook, ...
    calendar: str | None = None  # calendar provider key; defaults to `provider`
    enabled: bool = True
    scans_per_day: int = 4
    lookback_hours: int = 24  # first scan only; later scans resume from the stored cursor
    max_emails: int = 50
    timezone: str = "Europe/Rome"
    ignore_senders: list = field(default_factory=list)  # case-insensitive substrings; skipped before the model
    ignore_subjects: list = field(default_factory=list)
    # filing rules: {subject_contains|sender_contains: str, label: str, archive: bool=True}; a match files the
    # mail (label, leave inbox) and keeps it away from the model. Needs a provider with file_message().
    rules: list = field(default_factory=list)
    options: dict = field(default_factory=dict)  # provider-specific: token_env, token_file, ...


def load_accounts(path: str | Path, include_disabled: bool = False) -> list[AccountConfig]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    out: list[AccountConfig] = []
    seen: set[str] = set()
    for item in raw.get("accounts", []):
        cfg = AccountConfig(**item)
        if cfg.id in seen:
            raise ValueError(f"duplicate account id: {cfg.id}")
        seen.add(cfg.id)
        if cfg.enabled or include_disabled:
            out.append(cfg)
    return out
