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
# Real ING statements (2024-2025): "CONTO CORRENTE ARANCIO", USCITE/ENTRATE, legal footer "ING BANK N.V.".
ING = Profile("ing", ("ing bank", "conto arancio", "conto corrente arancio", "ing italia", "ing direct"),
              debit=("uscite", "addebiti", "dare"), credit=("entrate", "accrediti", "avere"))
# Real Fineco statements (2025-2026): "DATA OPERAZIONE / DATA VALUTA / USCITE / ENTRATE / DESCRIZIONE", dates as
# dd.mm.yy, balances as "+5.225,90 Saldo iniziale in euro"; letterhead "FinecoBank S.p.A.", BIC FEBIITM1/2.
FINECO = Profile("fineco", ("fineco", "febiitm"),
                 debit=("uscite", "addebiti", "dare"), credit=("entrate", "accrediti", "avere"))
GENERIC = Profile("generic", (), debit=("dare", "uscite", "addebiti"), credit=("avere", "entrate", "accrediti"))

PROFILES = (CREDEM, ING, FINECO)


def detect(first_page: str) -> Profile:
    text = first_page.lower()
    for p in PROFILES:
        if any(m in text for m in p.markers):
            return p
    return GENERIC
