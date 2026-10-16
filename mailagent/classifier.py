"""Tidy classifier: is this inbox mail a newsletter, a service notification or a promotion?

No model, only signals a sender sets on purpose, so every decision has a readable reason:
  1. protected: starred, younger than min_age_minutes (a 2FA code you are waiting for), or the
     sender matches the account's `protect` list -> never touched
  2. the account's explicit filing `rules` (same as scan/sweep)
  3. Gmail's own Promotions category
  4. List-Unsubscribe / List-Id / Precedence: bulk|list|junk -> newsletter
  5. no-reply / notifications sender, or Auto-Submitted: auto-generated -> notification
     (bounces from mailer-daemon and out-of-office replies stay: they are about your own mail)

Per-account `tidy` options (all optional): enabled, categories, labels, archive, mark_read, min_age_minutes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from .config import AccountConfig

CATEGORIES = ("promotions", "newsletter", "notifications")
LABELS = {"newsletter": "Newsletter", "notifications": "Notifiche", "promotions": "Promozioni"}
NOREPLY = re.compile(r"(^|[._+-])(no-?reply|do-?not-?reply|notifications?|notify|alerts?)([._+-]|$)", re.I)
ADDRESS = re.compile(r"<([^>]+)>")


@dataclass(frozen=True)
class Decision:
    label: str
    archive: bool
    mark_read: bool
    reason: str


def _address(sender: str) -> str:
    m = ADDRESS.search(sender)
    return (m.group(1) if m else sender).strip().lower()


def rule_matches(rule: dict, subject: str, sender: str) -> bool:
    s, f = rule.get("subject_contains"), rule.get("sender_contains")
    return bool((s and s.lower() in subject.lower()) or (f and f.lower() in sender.lower()))


def _protected(msg: dict, cfg: AccountConfig, now: datetime) -> bool:
    if "STARRED" in msg.get("labels", []):
        return True
    min_age_ms = int(cfg.tidy.get("min_age_minutes", 60)) * 60_000
    if now.timestamp() * 1000 - int(msg.get("internal_date") or 0) < min_age_ms:
        return True
    sender = msg["headers"].get("from", "").lower()
    return any(p.lower() in sender for p in cfg.protect)


def _signals(msg: dict) -> list[tuple[str, str]]:
    """(category, reason) for every signal present, strongest first."""
    h, labels = msg["headers"], msg.get("labels", [])
    found = []
    if "CATEGORY_PROMOTIONS" in labels:
        found.append(("promotions", "gmail category promotions"))
    for key in ("list-unsubscribe", "list-id"):
        if h.get(key):
            found.append(("newsletter", f"header {key}"))
    if h.get("precedence", "").strip().lower() in ("bulk", "list", "junk"):
        found.append(("newsletter", f"precedence {h['precedence'].strip().lower()}"))
    local = _address(h.get("from", "")).split("@", 1)[0]
    if NOREPLY.search(local):
        found.append(("notifications", f"sender {local}@"))
    if h.get("auto-submitted", "").strip().lower().startswith("auto-generated"):  # not auto-replied: a person's out-of-office
        found.append(("notifications", "header auto-submitted"))
    return found


def classify(msg: dict, cfg: AccountConfig, now: datetime) -> Decision | None:
    """msg = {id, headers: {lowercase name: value}, labels: [...], internal_date: epoch ms}."""
    if _protected(msg, cfg, now):
        return None
    t = cfg.tidy
    mark_read = bool(t.get("mark_read", False))
    subject, sender = msg["headers"].get("subject", ""), msg["headers"].get("from", "")
    for r in cfg.rules:
        if rule_matches(r, subject, sender):
            return Decision(r["label"], r.get("archive", True), mark_read, f"rule {r.get('subject_contains') or r.get('sender_contains')}")
    wanted = t.get("categories", CATEGORIES)
    for category, reason in _signals(msg):
        if category in wanted:
            label = {**LABELS, **t.get("labels", {})}[category]
            return Decision(label, bool(t.get("archive", True)), mark_read, reason)
    return None
