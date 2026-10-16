"""PDF statement → Statement.

Words are read with their positions (pdfplumber), grouped into lines, and the movements table is
recognised by its header line (Dare/Avere, Uscite/Entrate…). The x position of each amount says
which column it sits in, so the sign comes from the layout rather than from the wording. Without
such a header (unknown layout) the sign is guessed from the wording and flagged `sign_uncertain`.
"""
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pdfplumber

from bankanalyst.amounts import parse_amount, parse_date
from bankanalyst.models import Statement, Transaction
from bankanalyst.profiles import GENERIC, Profile, detect

_LINE_TOLERANCE = 2.5  # points: words whose tops differ less than this are on the same line
_STOP = re.compile(r"\b(pagina|pag\.|segue|continua)\b", re.I)
_DESC_HEADER = ("descrizione", "causale", "operazioni", "operazione", "dettaglio")
_CREDIT_WORDS = ("accredito", "bonifico a vostro favore", "bonifico da", "a vostro favore", "stipendio",
                 "versamento", "interessi creditori", "giroconto da", "emolumenti", "pensione")


@dataclass
class _Word:
    text: str
    x0: float
    x1: float

    @property
    def center(self) -> float:
        return (self.x0 + self.x1) / 2


@dataclass
class _Columns:
    debit: float
    credit: float
    balance: float | None
    desc_x: float | None


def _lines(page) -> list[list[_Word]]:
    words = sorted(page.extract_words(x_tolerance=1.5, y_tolerance=2), key=lambda w: (w["top"], w["x0"]))
    lines: list[list[_Word]] = []
    top = None
    for w in words:
        if top is None or abs(w["top"] - top) > _LINE_TOLERANCE:
            lines.append([])
            top = w["top"]
        lines[-1].append(_Word(w["text"], w["x0"], w["x1"]))
    return [sorted(line, key=lambda w: w.x0) for line in lines]


def _norm(text: str) -> str:
    return re.sub(r"[^\wàèéìòù]", "", text.lower())


def _header(line: list[_Word], profile: Profile) -> _Columns | None:
    if any(parse_amount(w.text) is not None for w in line):
        return None
    debit = next((w for w in line if _norm(w.text) in profile.debit), None)
    credit = next((w for w in line if _norm(w.text) in profile.credit), None)
    if not debit or not credit:
        return None
    balance = next((w for w in line if _norm(w.text) in profile.balance), None)
    desc = [w.x0 for w in line if _norm(w.text) in _DESC_HEADER]
    return _Columns(debit.center, credit.center, balance.center if balance else None, min(desc) if desc else None)


def _guess_sign(description: str) -> int:
    text = description.lower()
    return 1 if any(k in text for k in _CREDIT_WORDS) else -1


def parse_statement(path: str | Path, profile: Profile | None = None) -> Statement:
    path = Path(path)
    with pdfplumber.open(path) as pdf:
        pages = [_lines(p) for p in pdf.pages]

    if profile is None:
        letterhead = []
        for line in (pages[0] if pages else []):
            if _header(line, GENERIC):
                break
            letterhead.append(" ".join(w.text for w in line))
        profile = detect("\n".join(letterhead))

    st = Statement(path=str(path), bank=profile.key)
    if not any(pages):
        st.warnings.append("nessun testo nel PDF: probabilmente scansionato, serve l'OCR")
        return st

    cols: _Columns | None = None
    for page_no, lines in enumerate(pages, start=1):
        current: Transaction | None = None
        for line in lines:
            text = " ".join(w.text for w in line)
            low = text.lower()
            header = _header(line, profile)
            if header:
                cols, current = header, None
                continue

            amounts = [(w, parse_amount(w.text)) for w in line]
            amounts = [(w, a) for w, a in amounts if a is not None]

            if any(k in low for k in profile.opening + profile.closing):
                if amounts:
                    value = amounts[-1][1]
                    if any(k in low for k in profile.opening):
                        st.opening = value if st.opening is None else st.opening
                    else:
                        st.closing = value
                current = None
                continue

            booking = parse_date(line[0].text)
            if booking is None:
                is_continuation = (current is not None and not amounts and not _STOP.search(text)
                                   and (cols is None or cols.desc_x is None or line[0].x0 >= cols.desc_x - 5))
                if is_continuation:
                    current.description = f"{current.description} {text}"
                else:
                    current = None
                continue

            skip = {id(line[0])}
            value_date = parse_date(line[1].text) if len(line) > 1 else None
            if value_date:
                skip.add(id(line[1]))

            if not amounts:
                st.warnings.append(f"p.{page_no}: riga con data ma senza importo, ignorata: {text}")
                current = None
                continue

            uncertain = False
            if cols:
                candidates = [(w, a) for w, a in amounts if cols.balance is None or
                              min(abs(w.center - cols.debit), abs(w.center - cols.credit)) < abs(w.center - cols.balance)]
                if not candidates:
                    st.warnings.append(f"p.{page_no}: importo non attribuibile a Dare/Avere: {text}")
                    current = None
                    continue
                word, value = min(candidates, key=lambda c: min(abs(c[0].center - cols.debit),
                                                                abs(c[0].center - cols.credit)))
                is_debit = abs(word.center - cols.debit) < abs(word.center - cols.credit)
                amount = -abs(value) if is_debit else abs(value)
                skip.update(id(w) for w, _ in amounts)
            else:
                word, value = amounts[-1]
                skip.add(id(word))
                desc_tmp = " ".join(w.text for w in line if id(w) not in skip)
                if value < 0:
                    amount = value
                else:
                    amount, uncertain = value * _guess_sign(desc_tmp), True

            description = " ".join(w.text for w in line if id(w) not in skip)
            current = Transaction(bank=profile.key, booking_date=booking, value_date=value_date,
                                  description=description, amount=Decimal(amount), source=path.name,
                                  page=page_no, sign_uncertain=uncertain)
            st.transactions.append(current)

    if not st.transactions:
        st.warnings.append("nessun movimento riconosciuto: layout da adattare in bankanalyst/profiles.py")
    return st
