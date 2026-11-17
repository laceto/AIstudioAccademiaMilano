"""Categories for the card, from bankanalyst's base rules (bankanalyst/rules.yaml, shipped in the image).

Personal rules stay on the laptop; here only the base ones guess a category from the causale text.
"""
from datetime import date
from decimal import Decimal

from bankanalyst.classify import UNCLASSIFIED, Classifier, load_rules
from bankanalyst.models import Transaction


def _rules():
    return load_rules()


def category_names() -> list[str]:
    """Spending/income categories to offer as buttons: no transfers, no flagged ones, no duplicates, rule order."""
    rules = _rules()
    skip = rules.transfers | rules.flags
    seen: list[str] = []
    for r in rules.categories:
        if r.name not in skip and r.name not in seen:
            seen.append(r.name)
    return seen


def guess_category(causale: str, bank: str, amount: Decimal, day: date) -> str:
    """The base rules' category for this text, or "" when they find nothing."""
    tx = Transaction(bank=bank, booking_date=day, value_date=None, description=causale, amount=amount,
                     source="telegram", page=0)
    name = Classifier(_rules()).classify(tx)
    return "" if name == UNCLASSIFIED else name
