"""scan -> extract -> store; calendar writes only on explicit approval."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable

from .config import AccountConfig
from .extractor import Extractor
from .store import JsonStore

OVERLAP = timedelta(hours=1)  # re-read a little: the processed ledger makes this harmless


@dataclass
class ScanReport:
    account_id: str
    seen: int = 0
    new_todos: int = 0
    new_proposals: int = 0
    skipped: int = 0
    filed: int = 0
    errors: list[str] = field(default_factory=list)


def _ignored(cfg: AccountConfig, em) -> bool:
    return any(s.lower() in em.sender.lower() for s in cfg.ignore_senders) or any(
        s.lower() in em.subject.lower() for s in cfg.ignore_subjects
    )


def _matching_rule(cfg: AccountConfig, em) -> dict | None:
    for rule in cfg.rules:
        s, f = rule.get("subject_contains"), rule.get("sender_contains")
        if (s and s.lower() in em.subject.lower()) or (f and f.lower() in em.sender.lower()):
            return rule
    return None


def scan_account(cfg: AccountConfig, mail, extractor: Extractor, store: JsonStore, now: datetime | None = None, dry_run: bool = False) -> ScanReport:
    now = now or datetime.now(timezone.utc)
    state = store.get_state(cfg.id)
    since = datetime.fromisoformat(state["cursor"]) if state.get("cursor") else now - timedelta(hours=cfg.lookback_hours)
    processed = list(state.get("processed", []))
    rep = ScanReport(cfg.id)
    for em in mail.list_new(since, cfg.max_emails):
        if em.id in processed:
            continue
        rule = _matching_rule(cfg, em)
        if rule and hasattr(mail, "file_message"):
            try:
                if not dry_run:  # a dry run reports what it would do and touches nothing
                    mail.file_message(em.id, rule["label"], rule.get("archive", True))
            except Exception as exc:  # stays unprocessed: filed again on the next scan
                rep.errors.append(f"{em.id}: could not file ({exc})")
                continue
            rep.filed += 1
            processed.append(em.id)
            continue
        if rule or _ignored(cfg, em):
            rep.skipped += 1
            processed.append(em.id)
            continue
        rep.seen += 1
        try:
            ext = extractor.extract(em, today=now.date().isoformat())
        except Exception as exc:  # one bad email must not block the rest; it is retried next scan
            rep.errors.append(f"{em.id}: {exc}")
            continue
        for n, t in enumerate(ext.todos):
            rec = {"id": f"{cfg.id}:{em.id}:t{n}", "account": cfg.id, "status": "open", "source_subject": em.subject,
                   "source_sender": em.sender, "source_link": em.link, "created_at": now.isoformat(), **t.model_dump()}
            rep.new_todos += store.add_todo(rec)
        if ext.event:
            rec = {"id": f"{cfg.id}:{em.id}:e", "account": cfg.id, "status": "pending", "source_subject": em.subject,
                   "source_link": em.link, "created_at": now.isoformat(), **ext.event.model_dump()}
            rep.new_proposals += store.add_proposal(rec)
        processed.append(em.id)
    # With any error keep the old cursor so the failed email stays inside the next window.
    cursor = state.get("cursor") if rep.errors else (now - OVERLAP).isoformat()
    store.set_state(cfg.id, {"cursor": cursor, "processed": processed})
    return rep


def scan_all(accounts: list[AccountConfig], build_mail: Callable, extractor: Extractor, store: JsonStore, now: datetime | None = None, dry_run: bool = False) -> list[ScanReport]:
    reports = []
    for cfg in accounts:
        try:
            reports.append(scan_account(cfg, build_mail(cfg), extractor, store, now, dry_run))
        except Exception as exc:  # account-level failure (revoked token, outage): report, go on
            reports.append(ScanReport(cfg.id, errors=[f"{type(exc).__name__}: {exc}"]))
    return reports


def approve_proposal(pid: str, store: JsonStore, calendar) -> str:
    prop = next((p for p in store.list_proposals() if p["id"] == pid), None)
    if prop is None:
        raise ValueError(f"unknown proposal {pid}")
    if prop["status"] != "pending":
        raise ValueError(f"proposal {pid} is not pending ({prop['status']})")
    event_id = calendar.create_event(prop)
    store.update_proposal(pid, {"status": "approved", "calendar_event_id": event_id})
    return event_id


def reject_proposal(pid: str, store: JsonStore) -> None:
    store.update_proposal(pid, {"status": "rejected"})
