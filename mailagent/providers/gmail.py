"""Gmail mail provider (read + label/archive/mark read; no send, no delete). The API service is injectable for tests."""

from __future__ import annotations

import base64
import html
import re
from datetime import datetime, timezone
from typing import Any

from ..config import AccountConfig
from ..models import Email
from . import register_calendar, register_mail

# googleapiclient retries 429, 5xx and rate-limit 403s itself, with exponential backoff, when told how often.
NUM_RETRIES = 5
TIDY_HEADERS = ["From", "Subject", "List-Unsubscribe", "List-Id", "Precedence", "Auto-Submitted"]


def _exec(request: Any) -> dict:
    return request.execute(num_retries=NUM_RETRIES)


# Inbox only, no promotion/social tabs: those almost never hold something to act on.
QUERY = "after:{ts} in:inbox -category:promotions -category:social"


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "replace")


def _text_of(payload: dict) -> str:
    """Prefer text/plain anywhere in the MIME tree; fall back to tag-stripped HTML."""
    plain, html_ = [], []

    def walk(part: dict) -> None:
        mime, data = part.get("mimeType", ""), (part.get("body") or {}).get("data")
        if data and mime == "text/plain":
            plain.append(_decode(data))
        elif data and mime == "text/html":
            html_.append(_decode(data))
        for sub in part.get("parts") or []:
            walk(sub)

    walk(payload)
    if plain:
        return "\n".join(plain).strip()
    return html.unescape(re.sub(r"<[^>]+>", " ", " ".join(html_))).strip()


class GmailProvider:
    def __init__(self, account_id: str, service: Any | None = None, cfg: AccountConfig | None = None):
        self.account_id, self._service, self._cfg = account_id, service, cfg

    @property
    def service(self) -> Any:
        if self._service is None:
            from .google_auth import build_service

            self._service = build_service(self._cfg, "gmail", "v1")
        return self._service

    def _label_id(self, name: str) -> str:
        if not hasattr(self, "_labels"):
            labels = _exec(self.service.users().labels().list(userId="me")).get("labels", [])
            self._labels = {l["name"]: l["id"] for l in labels}
        if name not in self._labels:
            made = _exec(self.service.users().labels().create(userId="me", body={"name": name}))
            self._labels[name] = made["id"]
        return self._labels[name]

    def file_message(self, email_id: str, label: str, archive: bool = True) -> None:
        """Add `label` and (by default) take the mail out of the inbox. Never deletes or sends."""
        body = {"addLabelIds": [self._label_id(label)], "removeLabelIds": ["INBOX"] if archive else []}
        _exec(self.service.users().messages().modify(userId="me", id=email_id, body=body))

    def inbox_candidates(self, rule: dict) -> list[dict]:
        """Shortlist of inbox mail that may match a rule: [{id, subject, sender}], all pages."""
        term = (f'subject:"{rule["subject_contains"]}"' if rule.get("subject_contains") else f'from:"{rule["sender_contains"]}"')
        msgs, token, out = self.service.users().messages(), None, []
        while True:
            page = _exec(msgs.list(userId="me", q=f"in:inbox {term}", maxResults=500, pageToken=token))
            for ref in page.get("messages", []):
                m = _exec(msgs.get(userId="me", id=ref["id"], format="metadata", metadataHeaders=["Subject", "From"]))
                h = {x["name"].lower(): x["value"] for x in m["payload"].get("headers", [])}
                out.append({"id": m["id"], "subject": h.get("subject", ""), "sender": h.get("from", "")})
            token = page.get("nextPageToken")
            if not token:
                return out

    def file_many(self, ids: list[str], label: str, archive: bool = True) -> None:
        self.modify_many(ids, label, archive=archive)

    def modify_many(self, ids: list[str], label: str, archive: bool = True, mark_read: bool = False) -> None:
        """Label `ids`, optionally archive and mark read, in batchModify calls of at most 1000 ids."""
        label_id = self._label_id(label)
        remove = (["INBOX"] if archive else []) + (["UNREAD"] if mark_read else [])
        for i in range(0, len(ids), 1000):
            _exec(self.service.users().messages().batchModify(userId="me", body={
                "ids": ids[i:i + 1000], "addLabelIds": [label_id], "removeLabelIds": remove}))

    def tidy_candidates(self, query: str, max_messages: int) -> list[dict]:
        """Up to `max_messages` mail matching `query`, headers only: [{id, headers, labels, internal_date}]."""
        msgs, token, out = self.service.users().messages(), None, []
        while len(out) < max_messages:
            page = _exec(msgs.list(userId="me", q=query, maxResults=min(500, max_messages - len(out)), pageToken=token))
            for ref in page.get("messages", [])[: max_messages - len(out)]:
                m = _exec(msgs.get(userId="me", id=ref["id"], format="metadata", metadataHeaders=TIDY_HEADERS))
                out.append({"id": m["id"], "labels": m.get("labelIds", []), "internal_date": int(m.get("internalDate", 0)),
                            "headers": {h["name"].lower(): h["value"] for h in m["payload"].get("headers", [])}})
            token = page.get("nextPageToken")
            if not token:
                break
        return out

    def list_new(self, since: datetime, max_results: int) -> list[Email]:
        msgs = self.service.users().messages()
        listing = _exec(msgs.list(userId="me", q=QUERY.format(ts=int(since.timestamp())), maxResults=max_results))
        out = []
        for ref in listing.get("messages", []):
            m = _exec(msgs.get(userId="me", id=ref["id"], format="full"))
            headers = {h["name"].lower(): h["value"] for h in m["payload"].get("headers", [])}
            received = datetime.fromtimestamp(int(m["internalDate"]) / 1000, tz=timezone.utc).isoformat()
            out.append(Email(
                account_id=self.account_id, id=m["id"], thread_id=m.get("threadId", ""),
                sender=headers.get("from", ""), subject=headers.get("subject", ""), received_at=received,
                body=_text_of(m["payload"]), link=f"https://mail.google.com/mail/u/0/#inbox/{m['id']}",
            ))
        return out


@register_mail("gmail")
def _build_mail(cfg: AccountConfig) -> GmailProvider:
    return GmailProvider(cfg.id, cfg=cfg)


@register_calendar("gmail")
def _build_calendar(cfg: AccountConfig):
    from .google_calendar import GoogleCalendarProvider

    return GoogleCalendarProvider(cfg)
