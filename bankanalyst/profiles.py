"""Per-bank layout hints. Column words are matched on the header line of the movements table."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    key: str
    markers: tuple[str, ...]  # looked for in the letterhead, before the movements table
    debit: tuple[str, ...]
    credit: tuple[str, ...]
    balance: tuple[str, ...] = ("saldo",)
    opening: tuple[str, ...] = ("saldo iniziale", "saldo contabile iniziale", "saldo precedente")
    closing: tuple[str, ...] = ("saldo finale", "saldo contabile finale")


CREDEM = Profile("credem", ("credem", "credito emiliano"),
                 debit=("dare", "addebiti", "uscite"), credit=("avere", "accrediti", "entrate"))
ING = Profile("ing", ("ing bank", "conto arancio", "ing italia", "ing direct"),
              debit=("uscite", "addebiti", "dare"), credit=("entrate", "accrediti", "avere"))
GENERIC = Profile("generic", (), debit=("dare", "uscite", "addebiti"), credit=("avere", "entrate", "accrediti"))

PROFILES = (CREDEM, ING)


def detect(letterhead: str) -> Profile:
    text = letterhead.lower()
    for p in PROFILES:
        if any(m in text for m in p.markers):
            return p
    return GENERIC
