"""Gmail mail provider (read + label/archive; no send, no delete). The API service is injectable for tests."""

from __future__ import annotations

import base64
import html
import re
from datetime import datetime, timezone
from typing import Any

from ..config import AccountConfig
from ..models import Email
from . import register_calendar, register_mail

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
            labels = self.service.users().labels().list(userId="me").execute().get("labels", [])
            self._labels = {l["name"]: l["id"] for l in labels}
        if name not in self._labels:
            made = self.service.users().labels().create(userId="me", body={"name": name}).execute()
            self._labels[name] = made["id"]
        return self._labels[name]

    def file_message(self, email_id: str, label: str, archive: bool = True) -> None:
        """Add `label` and (by default) take the mail out of the inbox. Never deletes or sends."""
        body = {"addLabelIds": [self._label_id(label)], "removeLabelIds": ["INBOX"] if archive else []}
        self.service.users().messages().modify(userId="me", id=email_id, body=body).execute()

    def list_new(self, since: datetime, max_results: int) -> list[Email]:
        msgs = self.service.users().messages()
        listing = msgs.list(userId="me", q=QUERY.format(ts=int(since.timestamp())), maxResults=max_results).execute()
        out = []
        for ref in listing.get("messages", []):
            m = msgs.get(userId="me", id=ref["id"], format="full").execute()
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
