"""Rule-based classification: ordered regex rules from YAML, first match wins, overrides beat everything."""
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

import yaml

from bankanalyst.models import Transaction

DEFAULT_RULES = Path(__file__).with_name("rules.yaml")
UNCLASSIFIED = "Da classificare"


@dataclass
class Rule:
    name: str
    patterns: list[re.Pattern]
    direction: str = "any"
    transfer: bool = False
    amount: Decimal | None = None  # exact signed amount (e.g. -5.50): same merchant, different meaning by price
    bank: str | None = None  # only movements of this bank (credem / ing / fineco)
    flag: bool = False  # flagged: shown apart, left out of income/expense totals and the budget

    def matches(self, tx: Transaction) -> bool:
        if self.direction == "in" and tx.amount < 0 or self.direction == "out" and tx.amount > 0:
            return False
        if self.bank is not None and tx.bank.lower() != self.bank:
            return False
        if self.amount is not None and tx.amount != self.amount:
            return False
        return any(p.search(tx.description) for p in self.patterns)


@dataclass
class Note:
    """A causale for one movement: same bank, same signed amount, booked within `NOTE_DAYS` of `day`.

    For what the statement cannot say (cash withdrawn to pay someone). `category`, when given, replaces the
    rule's category for that movement only.
    """
    day: date
    bank: str
    amount: Decimal
    causale: str
    category: str | None = None


NOTE_DAYS = 5  # the bank may book a withdrawal a few days later (weekends, holidays)


@dataclass
class Rules:
    categories: list[Rule]
    overrides: dict[str, str]
    notes: list[Note] = field(default_factory=list)

    @property
    def transfers(self) -> set[str]:
        return {r.name for r in self.categories if r.transfer}

    @property
    def flags(self) -> set[str]:
        return {r.name for r in self.categories if r.flag}


def _read(path: Path) -> Rules:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cats = [Rule(name=c["name"], patterns=[re.compile(p, re.I) for p in c.get("patterns", [])],
                 direction=c.get("direction", "any"), transfer=bool(c.get("transfer", False)),
                 amount=Decimal(str(c["amount"])) if c.get("amount") is not None else None,
                 bank=str(c["bank"]).lower() if c.get("bank") else None, flag=bool(c.get("flag", False)))
            for c in data.get("categories") or []]
    notes = [Note(day=n["data"] if isinstance(n["data"], date) else date.fromisoformat(str(n["data"])),
                  bank=str(n["banca"]).lower(), amount=Decimal(str(n["importo"])), causale=str(n["causale"]),
                  category=n.get("categoria"))
             for n in data.get("causali") or []]
    return Rules(categories=cats, overrides=dict(data.get("overrides") or {}), notes=notes)


def load_rules(path: str | Path | None = None) -> Rules:
    """Default rules, with a personal file layered on top: its categories are tried first, its overrides added.

    A category in the personal file with the same name as a default one inherits its `transfer` flag, so
    personal patterns for "Giroconti tra conti" still keep those movements out of the totals.
    """
    base = _read(DEFAULT_RULES)
    if path is None:
        return base
    own = _read(Path(path))
    flags = {r.name: r.transfer for r in base.categories}
    for r in own.categories:
        r.transfer = r.transfer or flags.get(r.name, False)
    return Rules(categories=own.categories + base.categories, overrides={**base.overrides, **own.overrides},
                 notes=base.notes + own.notes)


def apply_notes(notes: list[Note], txs: list[Transaction]) -> list[Note]:
    """Attach each causale to the nearest-dated movement with the same bank and amount; return the unmatched.

    One note, one movement: two withdrawals of the same amount need two notes. Notes are matched in date order.
    """
    pending = []
    for n in sorted(notes, key=lambda n: n.day):
        candidates = [t for t in txs if not t.note and t.bank.lower() == n.bank and t.amount == n.amount
                      and abs((t.booking_date - n.day).days) <= NOTE_DAYS]
        if not candidates:
            pending.append(n)
            continue
        t = min(candidates, key=lambda t: (abs((t.booking_date - n.day).days), t.booking_date))
        t.note = n.causale
        if n.category:
            t.category = n.category
    return pending


class Classifier:
    def __init__(self, rules: Rules):
        self.rules = rules

    def classify(self, tx: Transaction) -> str:
        desc = tx.description.lower()
        for fragment, category in self.rules.overrides.items():
            if fragment.lower() in desc:
                return category
        for rule in self.rules.categories:
            if rule.matches(tx):
                return rule.name
        return UNCLASSIFIED
