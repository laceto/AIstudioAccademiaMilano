"""mailagent tidy: header heuristics + protect list -> Gmail label/archive in batches, and the Cloud Run endpoint.

Offline: the Gmail service and the mail provider are fakes.
"""

import json
import logging
from datetime import datetime, timezone

import pytest

from mailagent.classifier import classify
from mailagent.config import AccountConfig
from mailagent.pipeline import tidy_account

NOW = datetime(2026, 10, 16, 9, 0, tzinfo=timezone.utc)
OLD = int(datetime(2026, 10, 16, 6, 0, tzinfo=timezone.utc).timestamp() * 1000)  # 3 h before NOW


def _msg(i="m1", sender="News <news@shop.it>", subject="Saldi", labels=("INBOX",), when=OLD, **headers):
    h = {"from": sender, "subject": subject}
    h.update({k.replace("_", "-").lower(): v for k, v in headers.items()})
    return {"id": i, "headers": h, "labels": list(labels), "internal_date": when}


def _cfg(**kw):
    tidy = {"enabled": True, **kw.pop("tidy", {})}
    return AccountConfig(id="g", provider="gmail", tidy=tidy, **kw)


# ── classifier ─────────────────────────────────────────────────────────────

def test_list_unsubscribe_or_bulk_precedence_is_newsletter():
    d = classify(_msg(list_unsubscribe="<mailto:u@shop.it>"), _cfg(), NOW)
    assert d.label == "Newsletter" and d.archive and "list-unsubscribe" in d.reason
    assert classify(_msg(precedence="bulk"), _cfg(), NOW).label == "Newsletter"
    assert classify(_msg(list_id="<weekly.shop.it>"), _cfg(), NOW).label == "Newsletter"


def test_noreply_sender_is_notification():
    for s in ("no-reply@github.com", "Acme <noreply@acme.it>", "notifications@linkedin.com", "donotreply@x.it"):
        assert classify(_msg(sender=s), _cfg(), NOW).label == "Notifiche", s


def test_bounces_and_out_of_office_replies_stay_in_the_inbox():
    assert classify(_msg(sender="Mail Delivery Subsystem <mailer-daemon@googlemail.com>"), _cfg(), NOW) is None
    assert classify(_msg(sender="anna@studio.it", auto_submitted="auto-replied"), _cfg(), NOW) is None
    assert classify(_msg(sender="cron@server.it", auto_submitted="auto-generated"), _cfg(), NOW).label == "Notifiche"


def test_gmail_promotions_category_is_promotion():
    d = classify(_msg(labels=("INBOX", "CATEGORY_PROMOTIONS")), _cfg(), NOW)
    assert d.label == "Promozioni"


def test_plain_personal_mail_is_left_alone():
    assert classify(_msg(sender="Mamma <mamma@gmail.com>", subject="Domenica?"), _cfg(), NOW) is None


def test_protect_list_beats_every_heuristic():
    cfg = _cfg(protect=["@banca.it", "Commercialista@"])
    assert classify(_msg(sender="Avvisi <no-reply@banca.it>", list_unsubscribe="<x>"), cfg, NOW) is None
    assert classify(_msg(sender="commercialista@studio.it", precedence="bulk"), cfg, NOW) is None


def test_starred_and_recent_mail_are_protected():
    assert classify(_msg(list_unsubscribe="<x>", labels=("INBOX", "STARRED")), _cfg(), NOW) is None
    # a 2FA code or a reset link from no-reply@ must stay in the inbox while you wait for it
    fresh = int(datetime(2026, 10, 16, 8, 45, tzinfo=timezone.utc).timestamp() * 1000)
    assert classify(_msg(sender="no-reply@bank.com", when=fresh), _cfg(), NOW) is None
    assert classify(_msg(sender="no-reply@bank.com", when=fresh), _cfg(tidy={"min_age_minutes": 0}), NOW) is not None


def test_explicit_rule_wins_over_heuristic_label():
    cfg = _cfg(rules=[{"subject_contains": "[AI Studio]", "label": "AI Studio", "archive": True}])
    d = classify(_msg(sender="no-reply@aistudio.it", subject="[AI Studio] nuova richiesta"), cfg, NOW)
    assert d.label == "AI Studio" and d.reason.startswith("rule")


def test_tidy_options_rename_labels_and_mark_read():
    cfg = _cfg(tidy={"labels": {"newsletter": "Letture"}, "mark_read": True, "archive": False})
    d = classify(_msg(list_unsubscribe="<x>"), cfg, NOW)
    assert (d.label, d.archive, d.mark_read) == ("Letture", False, True)


def test_categories_can_be_switched_off():
    cfg = _cfg(tidy={"categories": ["newsletter"]})
    assert classify(_msg(sender="no-reply@x.it"), cfg, NOW) is None
    assert classify(_msg(list_unsubscribe="<x>"), cfg, NOW).label == "Newsletter"


# ── tidy_account: batching ─────────────────────────────────────────────────

class TidyMail:
    def __init__(self, msgs, fail_label=None):
        self.msgs, self.batches, self.fail_label, self.query = msgs, [], fail_label, None

    def tidy_candidates(self, query, max_messages):
        self.query = query
        return self.msgs[:max_messages]

    def modify_many(self, ids, label, archive, mark_read):
        if label == self.fail_label:
            raise RuntimeError("HttpError 500")
        self.batches.append((sorted(ids), label, archive, mark_read))


def test_tidy_groups_by_label_in_one_call_each():
    msgs = [_msg("a", list_unsubscribe="<x>"), _msg("b", precedence="bulk"),
            _msg("c", sender="noreply@x.it"), _msg("d", sender="amico@gmail.com")]
    mail = TidyMail(msgs)
    rep = tidy_account(_cfg(), mail, now=NOW)
    assert sorted(mail.batches) == [(["a", "b"], "Newsletter", True, False), (["c"], "Notifiche", True, False)]
    assert rep.filed == {"Newsletter": 2, "Notifiche": 1} and rep.examined == 4 and rep.kept == 1
    assert "in:inbox" in mail.query and rep.errors == []


def test_tidy_dry_run_reports_and_touches_nothing():
    mail = TidyMail([_msg("a", list_unsubscribe="<x>")])
    rep = tidy_account(_cfg(), mail, now=NOW, dry_run=True)
    assert mail.batches == [] and rep.filed == {"Newsletter": 1}
    assert rep.decisions[0]["id"] == "a" and rep.decisions[0]["label"] == "Newsletter"


def test_tidy_one_failing_batch_does_not_stop_the_others():
    mail = TidyMail([_msg("a", list_unsubscribe="<x>"), _msg("c", sender="noreply@x.it")], fail_label="Newsletter")
    rep = tidy_account(_cfg(), mail, now=NOW)
    assert mail.batches == [(["c"], "Notifiche", True, False)]
    assert rep.filed == {"Notifiche": 1} and len(rep.errors) == 1 and "Newsletter" in rep.errors[0]


def test_tidy_disabled_account_does_nothing():
    mail = TidyMail([_msg("a", list_unsubscribe="<x>")])
    rep = tidy_account(AccountConfig(id="g", provider="gmail"), mail, now=NOW)
    assert rep.examined == 0 and mail.query is None


# ── Gmail provider: candidates + modify_many + retries ─────────────────────

class _Call:
    def __init__(self, v, log=None):
        self.v, self.log = v, log

    def execute(self, **kw):
        if self.log is not None:
            self.log.append(kw)
        return self.v


class Svc:
    def __init__(self):
        self.queries, self.modified, self.executes = [], [], []

    def users(self):
        return self

    def messages(self):
        return self

    def labels(self):
        return self

    def list(self, userId, q=None, maxResults=None, pageToken=None):
        if q is None:
            return _Call({"labels": [{"id": "L1", "name": "Newsletter"}]}, self.executes)
        self.queries.append((q, maxResults, pageToken))
        if pageToken is None:
            return _Call({"messages": [{"id": "a"}, {"id": "b"}], "nextPageToken": "p2"}, self.executes)
        return _Call({"messages": [{"id": "c"}]}, self.executes)

    def get(self, userId, id, format, metadataHeaders):
        assert format == "metadata" and "List-Unsubscribe" in metadataHeaders
        return _Call({"id": id, "labelIds": ["INBOX"], "internalDate": str(OLD),
                      "payload": {"headers": [{"name": "From", "value": "n@x.it"},
                                              {"name": "List-Unsubscribe", "value": "<x>"}]}}, self.executes)

    def batchModify(self, userId, body):
        self.modified.append(body)
        return _Call({}, self.executes)


def test_gmail_tidy_candidates_page_until_max_and_lowercase_headers():
    from mailagent.providers.gmail import GmailProvider

    svc = Svc()
    out = GmailProvider("g", service=svc).tidy_candidates("in:inbox", 2)
    assert [m["id"] for m in out] == ["a", "b"] and len(svc.queries) == 1
    assert out[0]["headers"]["list-unsubscribe"] == "<x>" and out[0]["labels"] == ["INBOX"]
    assert out[0]["internal_date"] == OLD
    assert len(GmailProvider("g", service=Svc()).tidy_candidates("in:inbox", 10)) == 3


def test_gmail_modify_many_archives_marks_read_and_retries():
    from mailagent.providers.gmail import NUM_RETRIES, GmailProvider

    svc = Svc()
    GmailProvider("g", service=svc).modify_many(["a", "b"], "Newsletter", archive=True, mark_read=True)
    assert svc.modified == [{"ids": ["a", "b"], "addLabelIds": ["L1"], "removeLabelIds": ["INBOX", "UNREAD"]}]
    # every API call goes through execute(num_retries=...): the client backs off on 429 / 5xx
    assert svc.executes and all(kw.get("num_retries") == NUM_RETRIES for kw in svc.executes)


# ── JSON logging ───────────────────────────────────────────────────────────

def test_json_formatter_emits_cloud_logging_fields():
    from mailagent.jsonlog import JsonFormatter

    rec = logging.LogRecord("mailagent", logging.WARNING, __file__, 1, "tidy %s", ("g",), None)
    rec.fields = {"account": "g", "filed": {"Newsletter": 2}}
    out = json.loads(JsonFormatter().format(rec))
    assert out["severity"] == "WARNING" and out["message"] == "tidy g"
    assert out["account"] == "g" and out["filed"] == {"Newsletter": 2}


# ── HTTP endpoint (Cloud Run) ──────────────────────────────────────────────

@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from mailagent import server

    acc = tmp_path / "a.yaml"
    acc.write_text("accounts:\n  - id: g\n    provider: gmail\n    tidy: {enabled: true}\n"
                   "  - id: off\n    provider: gmail\n", encoding="utf-8")
    monkeypatch.setenv("MAILAGENT_ACCOUNTS", str(acc))
    monkeypatch.delenv("MAILAGENT_DRY_RUN", raising=False)
    built = {}

    def fake_build(cfg):
        built[cfg.id] = TidyMail([_msg("a", list_unsubscribe="<x>", when=0)])
        return built[cfg.id]

    monkeypatch.setattr(server, "build_mail", fake_build)
    return TestClient(server.app), built


def test_process_defaults_to_dry_run_and_only_tidy_accounts(client):
    c, built = client
    r = c.post("/process")
    assert r.status_code == 200
    body = r.json()
    assert body["dry_run"] is True and [a["account"] for a in body["accounts"]] == ["g"]
    assert body["accounts"][0]["filed"] == {"Newsletter": 1} and built["g"].batches == []


def test_process_real_run_when_env_says_so(client, monkeypatch):
    c, built = client
    monkeypatch.setenv("MAILAGENT_DRY_RUN", "0")
    assert c.post("/process").json()["dry_run"] is False
    assert built["g"].batches == [(["a"], "Newsletter", True, False)]


def test_process_body_can_force_dry_run_but_not_unknown_account(client, monkeypatch):
    c, built = client
    monkeypatch.setenv("MAILAGENT_DRY_RUN", "0")
    assert c.post("/process", json={"dry_run": True}).json()["dry_run"] is True
    assert built["g"].batches == []
    assert c.post("/process", json={"account": "nope"}).status_code == 404


def test_process_account_failure_returns_500(client, monkeypatch):
    from mailagent import server

    c, _ = client

    def boom(cfg):
        raise RuntimeError("token revoked")

    monkeypatch.setattr(server, "build_mail", boom)
    r = c.post("/process")
    assert r.status_code == 500 and "token revoked" in r.json()["accounts"][0]["errors"][0]


def test_healthz(client):
    c, _ = client
    assert c.get("/healthz").json() == {"ok": True}
