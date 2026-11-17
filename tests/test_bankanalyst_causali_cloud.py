"""Offline tests: bankanalyst reads the causali from the cloud database, and survives it being unreachable."""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from bankanalyst.causali_cloud import fetch_notes, merge_notes
from bankanalyst.classify import Note
from bankanalyst.models import Statement, Transaction
from bankanalyst.report import analyze
from causalibot.store import Causale, FirestoreStore

NOW = datetime(2026, 11, 17, 10, 0, tzinfo=timezone.utc)


class FakeSnap:
    def __init__(self, id, data):
        self.id, self._d = id, data

    def to_dict(self):
        return self._d


class FakeCollection:
    def __init__(self, docs, fail=False):
        self.docs, self.fail = docs, fail

    def stream(self):
        if self.fail:
            raise RuntimeError("DefaultCredentialsError")
        return iter(self.docs)


class FakeClient:
    def __init__(self, docs, fail=False):
        self.col = FakeCollection(docs, fail)
        self.asked = []

    def collection(self, name):
        self.asked.append(name)
        return self.col


def doc(c):
    return FakeSnap("d1", c.to_doc(NOW))


def test_fetch_turns_documents_into_notes():
    c = Causale(day=date(2026, 11, 17), bank="credem", amount=Decimal("-250.00"), causale="Pulizie Valeria",
                category="Casa e utenze")
    notes, warning = fetch_notes(store=FirestoreStore(client=FakeClient([doc(c)])))
    assert warning is None
    assert notes == [Note(day=date(2026, 11, 17), bank="credem", amount=Decimal("-250.00"),
                          causale="Pulizie Valeria", category="Casa e utenze")]


def test_empty_category_becomes_none():
    c = Causale(day=date(2026, 11, 17), bank="ing", amount=Decimal("-5.00"), causale="Caffè")
    notes, _ = fetch_notes(store=FirestoreStore(client=FakeClient([doc(c)])))
    assert notes[0].category is None


def test_unreachable_cloud_warns_and_returns_nothing():
    notes, warning = fetch_notes(store=FirestoreStore(client=FakeClient([], fail=True)))
    assert notes == [] and "causali" in warning and "DefaultCredentialsError" in warning


def test_merge_drops_identical_notes():
    n = Note(day=date(2026, 11, 17), bank="credem", amount=Decimal("-250.00"), causale="Pulizie Valeria")
    assert merge_notes([n], [Note(**n.__dict__)]) == [n]


def _statement():
    t = Transaction(bank="credem", booking_date=date(2026, 11, 18), value_date=None, description="PRELIEVO BANCOMAT",
                    amount=Decimal("-250.00"), source="x.pdf", page=1)
    return Statement(path="x.pdf", bank="credem", transactions=[t])


def test_analyze_attaches_cloud_notes_and_reports_the_warning():
    cloud = [Note(day=date(2026, 11, 17), bank="credem", amount=Decimal("-250.00"), causale="Pulizie Valeria")]
    r = analyze([_statement()], extra_notes=cloud)
    assert r.transactions[0].note == "Pulizie Valeria" and r.pending_notes == []


def test_analyze_adds_a_controlli_row_for_the_warning():
    r = analyze([_statement()], cloud_warning="causali cloud non raggiungibile")
    assert any("non raggiungibile" in c["avvisi"] for c in r.checks)
    assert r.checks[0]["file"] == "x.pdf"


def test_cli_without_cloud_flag_never_touches_it(monkeypatch):
    from bankanalyst import cli

    monkeypatch.setenv("CAUSALI_FIRESTORE_PROJECT", "p")
    monkeypatch.setattr(cli, "_cloud_notes", lambda *a, **k: pytest.fail("cloud must not be read"))
    assert cli._causali_for_run(no_cloud=True) == ([], None)


def test_project_is_read_from_dotenv_without_touching_the_environment(monkeypatch, tmp_path):
    """Regression: load_dotenv() in main() leaked the real OPENAI_API_KEY into later tests (gateway worker 401)."""
    import os

    from bankanalyst import cli

    env = tmp_path / ".env"
    env.write_text("CAUSALI_FIRESTORE_PROJECT=proj-x\nOPENAI_API_KEY=sk-should-not-leak\n", encoding="utf-8")
    monkeypatch.delenv("CAUSALI_FIRESTORE_PROJECT", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(cli, "_ENV_FILE", env)
    seen = []
    monkeypatch.setattr(cli, "_cloud_notes", lambda project: seen.append(project) or ([], None))
    assert cli._causali_for_run(no_cloud=False) == ([], None)
    assert seen == ["proj-x"]
    assert "OPENAI_API_KEY" not in os.environ and "CAUSALI_FIRESTORE_PROJECT" not in os.environ
