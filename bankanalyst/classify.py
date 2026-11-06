"""Rule-based classification: ordered regex rules from YAML, first match wins, overrides beat everything."""
import re
from dataclasses import dataclass
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

    def matches(self, tx: Transaction) -> bool:
        if self.direction == "in" and tx.amount < 0 or self.direction == "out" and tx.amount > 0:
            return False
        if self.amount is not None and tx.amount != self.amount:
            return False
        return any(p.search(tx.description) for p in self.patterns)


@dataclass
class Rules:
    categories: list[Rule]
    overrides: dict[str, str]

    @property
    def transfers(self) -> set[str]:
        return {r.name for r in self.categories if r.transfer}


def _read(path: Path) -> Rules:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cats = [Rule(name=c["name"], patterns=[re.compile(p, re.I) for p in c.get("patterns", [])],
                 direction=c.get("direction", "any"), transfer=bool(c.get("transfer", False)),
                 amount=Decimal(str(c["amount"])) if c.get("amount") is not None else None)
            for c in data.get("categories") or []]
    return Rules(categories=cats, overrides=dict(data.get("overrides") or {}))


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
    return Rules(categories=own.categories + base.categories, overrides={**base.overrides, **own.overrides})


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
