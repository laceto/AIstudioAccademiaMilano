"""Rule-based classification: ordered regex rules from YAML, first match wins, overrides beat everything."""
import re
from dataclasses import dataclass
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

    def matches(self, tx: Transaction) -> bool:
        if self.direction == "in" and tx.amount < 0 or self.direction == "out" and tx.amount > 0:
            return False
        return any(p.search(tx.description) for p in self.patterns)


@dataclass
class Rules:
    categories: list[Rule]
    overrides: dict[str, str]

    @property
    def transfers(self) -> set[str]:
        return {r.name for r in self.categories if r.transfer}


def load_rules(path: str | Path | None = None) -> Rules:
    data = yaml.safe_load(Path(path or DEFAULT_RULES).read_text(encoding="utf-8")) or {}
    cats = [Rule(name=c["name"], patterns=[re.compile(p, re.I) for p in c.get("patterns", [])],
                 direction=c.get("direction", "any"), transfer=bool(c.get("transfer", False)))
            for c in data.get("categories") or []]
    return Rules(categories=cats, overrides=dict(data.get("overrides") or {}))


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
