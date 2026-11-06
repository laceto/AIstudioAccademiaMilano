"""Per-bank layout hints. Column words are matched on the header line of the movements table."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    key: str
    markers: tuple[str, ...]  # looked for in the text of the first page (letterhead, legal footer)
    debit: tuple[str, ...]
    credit: tuple[str, ...]
    balance: tuple[str, ...] = ("saldo",)
    opening: tuple[str, ...] = ("saldo iniziale", "saldo contabile iniziale", "saldo precedente")
    closing: tuple[str, ...] = ("saldo finale", "saldo contabile finale", "saldo fine periodo")


# Real Credem statements (2024-2025): "IMPORTO A DEBITO / IMPORTO A CREDITO"; legal footer names Credito Emiliano.
CREDEM = Profile("credem", ("credito emiliano",),
                 debit=("debito", "dare", "addebiti"), credit=("credito", "avere", "accrediti"))
ING = Profile("ing", ("ing bank", "conto arancio", "ing italia", "ing direct"),
              debit=("uscite", "addebiti", "dare"), credit=("entrate", "accrediti", "avere"))
GENERIC = Profile("generic", (), debit=("dare", "uscite", "addebiti"), credit=("avere", "entrate", "accrediti"))

PROFILES = (CREDEM, ING)


def detect(first_page: str) -> Profile:
    text = first_page.lower()
    for p in PROFILES:
        if any(m in text for m in p.markers):
            return p
    return GENERIC
