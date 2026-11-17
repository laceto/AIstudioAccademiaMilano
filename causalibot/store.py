"""Causali storage: a named Firestore database `causali`, kept apart from the job store `(default)`.

A document: data, banca, importo (string, to keep the cents), causale, categoria, creata_il, expire_at,
allegati. `allegati` is empty today; a receipt photo can be added later as {"tipo", "ref"} without
migrating anything. expire_at = movement date + 24 months (Firestore TTL deletes it after that).
"""
import calendar
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

DATABASE = "causali"
COLLECTION = "causali"
DRAFTS = "bozze"
RETENTION_MONTHS = 24
UNDO_MINUTES = 10
DRAFT_DAYS = 1


def expire_at_for(day: date, months: int = RETENTION_MONTHS) -> datetime:
    total = day.month - 1 + months
    year, month = day.year + total // 12, total % 12 + 1
    d = min(day.day, calendar.monthrange(year, month)[1])
    return datetime(year, month, d, tzinfo=timezone.utc)


@dataclass
class Causale:
    day: date
    bank: str
    amount: Decimal
    causale: str
    category: str = ""
    allegati: list = field(default_factory=list)
    id: str = ""

    def to_doc(self, created: datetime) -> dict:
        return {"data": self.day.isoformat(), "banca": self.bank, "importo": f"{self.amount:.2f}",
                "causale": self.causale, "categoria": self.category, "creata_il": created,
                "expire_at": expire_at_for(self.day), "allegati": list(self.allegati)}

    @classmethod
    def from_doc(cls, doc: dict, id: str = "") -> "Causale":
        return cls(day=date.fromisoformat(str(doc["data"])), bank=str(doc["banca"]).lower(),
                   amount=Decimal(str(doc["importo"])), causale=str(doc["causale"]),
                   category=doc.get("categoria") or "", allegati=list(doc.get("allegati") or []), id=id)


class MemoryStore:
    """Same interface as FirestoreStore, in memory: tests and local runs."""

    def __init__(self):
        self._docs: dict[str, dict] = {}
        self._drafts: dict[str, dict] = {}

    def add(self, c: Causale, created: datetime | None = None) -> str:
        key = uuid.uuid4().hex
        self._docs[key] = c.to_doc(created or datetime.now(timezone.utc))
        return key

    def _sorted(self):
        return sorted(self._docs.items(), key=lambda kv: kv[1]["creata_il"], reverse=True)

    def recent(self, n: int = 10) -> list[Causale]:
        return [Causale.from_doc(d, k) for k, d in self._sorted()[:n]]

    def all(self) -> list[Causale]:
        return [Causale.from_doc(d, k) for k, d in self._sorted()]

    def delete_last(self, now: datetime | None = None) -> Causale | None:
        now = now or datetime.now(timezone.utc)
        for key, doc in self._sorted()[:1]:
            if now - doc["creata_il"] <= timedelta(minutes=UNDO_MINUTES):
                del self._docs[key]
                return Causale.from_doc(doc, key)
        return None

    def put_draft(self, c: Causale, created: datetime | None = None) -> str:
        key = uuid.uuid4().hex[:12]
        self._drafts[key] = c.to_doc(created or datetime.now(timezone.utc))
        return key

    def peek_draft(self, key: str) -> Causale | None:
        doc = self._drafts.get(key)
        return Causale.from_doc(doc, key) if doc else None

    def pop_draft(self, key: str) -> Causale | None:
        doc = self._drafts.pop(key, None)
        return Causale.from_doc(doc, key) if doc else None

    def update_draft(self, key: str, c: Causale) -> None:
        if key in self._drafts:
            self._drafts[key] = c.to_doc(self._drafts[key]["creata_il"])


class FirestoreStore:
    """Firestore database `causali`. The client is built lazily so importing this module needs no cloud package."""

    def __init__(self, project: str | None = None, client=None):
        self.project = project
        self._client = client

    @property
    def db(self):
        if self._client is None:
            from google.cloud import firestore
            self._client = firestore.Client(project=self.project, database=DATABASE)
        return self._client

    def add(self, c: Causale, created: datetime | None = None) -> str:
        ref = self.db.collection(COLLECTION).document()
        ref.set(c.to_doc(created or datetime.now(timezone.utc)))
        return ref.id

    def _recent_docs(self, n: int):
        return list(self.db.collection(COLLECTION).order_by("creata_il", direction="DESCENDING").limit(n).stream())

    def recent(self, n: int = 10) -> list[Causale]:
        return [Causale.from_doc(d.to_dict(), d.id) for d in self._recent_docs(n)]

    def all(self) -> list[Causale]:
        return [Causale.from_doc(d.to_dict(), d.id) for d in self.db.collection(COLLECTION).stream()]

    def delete_last(self, now: datetime | None = None) -> Causale | None:
        now = now or datetime.now(timezone.utc)
        for d in self._recent_docs(1):
            data = d.to_dict()
            if now - data["creata_il"] <= timedelta(minutes=UNDO_MINUTES):
                d.reference.delete()
                return Causale.from_doc(data, d.id)
        return None

    def put_draft(self, c: Causale, created: datetime | None = None) -> str:
        ref = self.db.collection(DRAFTS).document()
        created = created or datetime.now(timezone.utc)
        doc = c.to_doc(created)
        doc["expire_at"] = created + timedelta(days=DRAFT_DAYS)  # drafts die after a day, not after 24 months
        ref.set(doc)
        return ref.id

    def peek_draft(self, key: str) -> Causale | None:
        snap = self.db.collection(DRAFTS).document(key).get()
        return Causale.from_doc(snap.to_dict(), key) if snap.exists else None

    def pop_draft(self, key: str) -> Causale | None:
        ref = self.db.collection(DRAFTS).document(key)
        snap = ref.get()
        if not snap.exists:
            return None
        ref.delete()
        return Causale.from_doc(snap.to_dict(), key)

    def update_draft(self, key: str, c: Causale) -> None:
        ref = self.db.collection(DRAFTS).document(key)
        snap = ref.get()
        if snap.exists:
            old = snap.to_dict()
            doc = c.to_doc(old["creata_il"])
            doc["expire_at"] = old["expire_at"]
            ref.set(doc)
