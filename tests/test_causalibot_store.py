"""Offline tests for causalibot.store: retention, the future-proof attachments field, undo window."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from causalibot.store import Causale, MemoryStore, expire_at_for

NOW = datetime(2026, 11, 17, 10, 0, tzinfo=timezone.utc)


def make(day=date(2026, 11, 17), amount="-250.00", **kw):
    return Causale(day=day, bank="credem", amount=Decimal(amount), causale="Pulizie Valeria",
                   category="Casa e utenze", **kw)


def test_expire_is_movement_date_plus_24_months():
    assert expire_at_for(date(2026, 11, 17)) == datetime(2028, 11, 17, tzinfo=timezone.utc)


def test_expire_clamps_leap_day():
    assert expire_at_for(date(2024, 2, 29)) == datetime(2026, 2, 28, tzinfo=timezone.utc)


def test_document_keeps_cents_as_string_and_has_empty_attachments():
    doc = make().to_doc(created=NOW)
    assert doc["importo"] == "-250.00" and doc["allegati"] == []
    assert doc["expire_at"] == expire_at_for(date(2026, 11, 17)) and doc["creata_il"] == NOW


def test_roundtrip_with_future_attachment():
    c = make(allegati=[{"tipo": "foto", "ref": "gs://x/y.jpg"}])
    back = Causale.from_doc(c.to_doc(created=NOW))
    assert back.amount == Decimal("-250.00") and back.allegati == [{"tipo": "foto", "ref": "gs://x/y.jpg"}]


def test_recent_newest_first_and_limited():
    s = MemoryStore()
    for i in range(12):
        s.add(make(amount=f"-{i + 1}.00"), created=NOW + timedelta(minutes=i))
    got = s.recent(10)
    assert len(got) == 10 and got[0].amount == Decimal("-12.00")


def test_undo_last_only_within_ten_minutes():
    s = MemoryStore()
    s.add(make(), created=NOW)
    assert s.delete_last(now=NOW + timedelta(minutes=11)) is None and len(s.recent(10)) == 1
    gone = s.delete_last(now=NOW + timedelta(minutes=9))
    assert gone is not None and s.recent(10) == []


def test_drafts_are_taken_once():
    s = MemoryStore()
    key = s.put_draft(make(), created=NOW)
    assert s.pop_draft(key) is not None
    assert s.pop_draft(key) is None  # a second tap on Salva finds nothing


def test_all_for_bankanalyst():
    s = MemoryStore()
    s.add(make(), created=NOW)
    assert [c.causale for c in s.all()] == ["Pulizie Valeria"]
