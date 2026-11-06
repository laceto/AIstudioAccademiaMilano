"""PDF statement → Statement.

Words are read with their positions (pdfplumber) and grouped into lines. When the movements table has a
header line (IMPORTO A DEBITO / IMPORTO A CREDITO for Credem, Uscite/Entrate for ING…), the x position of
each amount says which column it sits in, so the sign comes from the layout rather than from the wording.

Inside the table, every line that starts with a date is a movement ("anchor"). Description lines can sit
above and below it: Credem centres a multi-line description on the row with dates and amount. Rows are
told apart by the shaded stripes behind every other row when the page has them (Credem does), otherwise
by the wider gaps between movements; each description line goes to the nearest anchor of its row block
(a tie goes to the earlier one). The table ends at the closing balance, so whatever
follows (conto scalare, notices) is never read as movements.

Without a header (unknown layout) lines are read in order and the sign is guessed from the wording,
flagged `sign_uncertain`.
"""
import bisect
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

import pdfplumber

from bankanalyst.amounts import parse_amount, parse_date
from bankanalyst.models import Statement, Transaction
from bankanalyst.profiles import Profile, detect

_LINE_TOLERANCE = 2.5  # points: words whose tops differ less than this are on the same line
_BLOCK_GAP = 1.6  # a gap this many times the usual line spacing separates two movements
_MAX_HEADER_WORDS = 16  # longer lines naming debit and credit are prose (the legend), not a header
_TIE = 1.0  # points: a description line this close to equidistant goes to the earlier movement
_IN_COLUMN = 60  # points: an amount farther than this from both amount columns is outside the table
_PAGE_CODE = re.compile(r"^\d{9,}[A-Z]{3}\d+[A-Z]+$")  # Credem print code in the margin: 310010002290EUX01960OMERC
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
class _Line:
    top: float
    words: list[_Word]

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)


@dataclass
class _Page:
    lines: list[_Line]
    rects: list[tuple[float, float, float, float]]  # x0, x1, top, bottom


@dataclass
class _Columns:
    debit: float
    credit: float
    balance: float | None
    desc_x: float | None
    first_x: float  # x of the first header word: the date column


@dataclass
class _Anchor:
    top: float
    page: int
    booking: date
    value_date: date | None
    amount: Decimal
    inline: str
    uncertain: bool = False
    parts: list[tuple[float, str]] = field(default_factory=list)


def _read(page) -> _Page:
    rects = [(r["x0"], r["x1"], r["top"], r["bottom"]) for r in page.rects]
    return _Page(_lines(page), rects)


def _lines(page) -> list[_Line]:
    words = [w for w in page.extract_words(x_tolerance=1.5, y_tolerance=2) if not _PAGE_CODE.match(w["text"])]
    words.sort(key=lambda w: (w["top"], w["x0"]))
    lines: list[_Line] = []
    for w in words:
        if not lines or abs(w["top"] - lines[-1].top) > _LINE_TOLERANCE:
            lines.append(_Line(w["top"], []))
        lines[-1].words.append(_Word(w["text"], w["x0"], w["x1"]))
    for line in lines:
        line.words.sort(key=lambda w: w.x0)
    return lines


def _norm(text: str) -> str:
    return re.sub(r"[^\wàèéìòù]", "", text.lower())


def _amounts(line: _Line) -> list[tuple[_Word, Decimal]]:
    found = [(w, parse_amount(w.text)) for w in line.words]
    return [(w, a) for w, a in found if a is not None]


def _header(line: _Line, profile: Profile) -> _Columns | None:
    if len(line.words) > _MAX_HEADER_WORDS or _amounts(line):
        return None
    debit = next((w for w in line.words if _norm(w.text) in profile.debit), None)
    credit = next((w for w in line.words if _norm(w.text) in profile.credit), None)
    if not debit or not credit:
        return None
    balance = next((w for w in line.words if _norm(w.text) in profile.balance), None)
    desc = [w.x0 for w in line.words if _norm(w.text) in _DESC_HEADER]
    return _Columns(debit.center, credit.center, balance.center if balance else None, min(desc) if desc else None,
                    line.words[0].x0)


def _row_bounds(page: _Page, cols: _Columns) -> list[float]:
    """Edges of the shaded row stripes in the date column: each stretch between two edges is one row."""
    stripes = [r for r in page.rects if r[0] <= cols.first_x + 2 <= r[1] and r[1] - r[0] < 200 and 4 < r[3] - r[2] < 300]
    return sorted({round(v, 1) for r in stripes for v in (r[2], r[3])})


def _is_debit(word: _Word, cols: _Columns) -> bool:
    return abs(word.center - cols.debit) < abs(word.center - cols.credit)


def _balance(line: _Line, profile: Profile, cols: _Columns | None, st: Statement) -> str | None:
    """Record an opening/closing balance line. Returns 'opening', 'closing' or None (not a balance line)."""
    low = line.text.lower()
    kind = ("opening" if any(k in low for k in profile.opening) else
            "closing" if any(k in low for k in profile.closing) else None)
    amounts = _amounts(line)
    if kind is None or not amounts:
        return None
    word, value = amounts[-1]
    in_column = cols is not None and min(abs(word.center - cols.debit), abs(word.center - cols.credit)) < _IN_COLUMN
    if in_column and value > 0 and _is_debit(word, cols):
        value = -value
    if kind == "opening":
        st.opening = value if st.opening is None else st.opening
    else:
        st.closing = value
    return kind


def _guess_sign(description: str) -> int:
    text = description.lower()
    return 1 if any(k in text for k in _CREDIT_WORDS) else -1


def parse_statement(path: str | Path, profile: Profile | None = None) -> Statement:
    path = Path(path)
    with pdfplumber.open(path) as pdf:
        pages = [_read(p) for p in pdf.pages]

    if profile is None:
        profile = detect("\n".join(line.text for line in (pages[0].lines if pages else [])))

    st = Statement(path=str(path), bank=profile.key)
    if not any(p.lines for p in pages):
        st.warnings.append("nessun testo nel PDF: probabilmente scansionato, serve l'OCR")
        return st

    if any(_header(line, profile) for page in pages for line in page.lines):
        _parse_table(pages, profile, st, path.name)
    else:
        _parse_lines([p.lines for p in pages], profile, st, path.name)

    if not st.transactions:
        st.warnings.append("nessun movimento riconosciuto: layout da adattare in bankanalyst/profiles.py")
    return st


def _parse_table(pages: list[_Page], profile: Profile, st: Statement, source: str) -> None:
    cols: _Columns | None = None
    for page_no, page in enumerate(pages, start=1):
        lines = page.lines
        start = next((i for i, line in enumerate(lines) if _header(line, profile)), None)
        if start is None and cols is None:
            for line in lines:  # summary pages before the table: balances only
                _balance(line, profile, None, st)
            continue
        if start is not None:
            for line in lines[:start]:
                _balance(line, profile, None, st)
            cols = _header(lines[start], profile)
            body = lines[start + 1:]
        else:
            body = lines  # the table continues from the previous page without a repeated header

        items: list[_Anchor | tuple[float, str]] = []
        closed = False
        for line in body:
            if _header(line, profile):
                cols = _header(line, profile)
                continue
            kind = _balance(line, profile, cols, st)
            if kind == "closing":
                closed = True
                break
            if kind:
                continue
            anchor = _anchor(line, cols, page_no, st)
            if anchor:
                items.append(anchor)
            elif not _amounts(line) and not _STOP.search(line.text) and parse_date(line.words[0].text) is None \
                    and (cols.desc_x is None or line.words[0].x0 >= cols.desc_x - 5):
                items.append((line.top, line.text))
        _assign(items, _row_bounds(page, cols))
        for a in (i for i in items if isinstance(i, _Anchor)):
            description = " ".join(text for _, text in sorted(a.parts + [(a.top, a.inline)]) if text)
            st.transactions.append(Transaction(bank=profile.key, booking_date=a.booking, value_date=a.value_date,
                                               description=description, amount=a.amount, source=source,
                                               page=a.page, sign_uncertain=a.uncertain))
        if closed:
            return


def _anchor(line: _Line, cols: _Columns, page_no: int, st: Statement) -> _Anchor | None:
    words = line.words
    booking = parse_date(words[0].text)
    if booking is None:
        return None
    skip = {id(words[0])}
    value_date = parse_date(words[1].text) if len(words) > 1 else None
    if value_date:
        skip.add(id(words[1]))
    amounts = [(w, a) for w, a in _amounts(line)
               if cols.balance is None or
               min(abs(w.center - cols.debit), abs(w.center - cols.credit)) < abs(w.center - cols.balance)]
    if not amounts:
        st.warnings.append(f"p.{page_no}: riga con data ma senza importo, ignorata: {line.text}")
        return None
    word, value = min(amounts, key=lambda c: min(abs(c[0].center - cols.debit), abs(c[0].center - cols.credit)))
    skip.update(id(w) for w, _ in _amounts(line))
    return _Anchor(top=line.top, page=page_no, booking=booking, value_date=value_date,
                   amount=-abs(value) if _is_debit(word, cols) else abs(value),
                   inline=" ".join(w.text for w in words if id(w) not in skip))


def _assign(items: list, bounds: list[float]) -> None:
    """Give each description line to the nearest anchor of its row block.

    Blocks are the stretches between row-stripe edges when the page has them, else they are split at the
    gaps clearly wider than the usual line spacing.
    """
    tops = [i.top if isinstance(i, _Anchor) else i[0] for i in items]
    if bounds:
        by_row: dict[int, list] = {}
        for item, top in zip(items, tops):
            by_row.setdefault(bisect.bisect(bounds, top + 1), []).append(item)
        blocks = list(by_row.values())
    else:
        gaps = sorted(b - a for a, b in zip(tops, tops[1:]) if b - a > 0)
        limit = gaps[len(gaps) // 4] * _BLOCK_GAP if gaps else 0
        blocks, current = [], []
        for item, top, prev in zip(items, tops, [None] + tops[:-1]):
            if prev is not None and top - prev > limit:
                blocks.append(current)
                current = []
            current.append(item)
        if current:
            blocks.append(current)
    for block in blocks:
        anchors = [i for i in block if isinstance(i, _Anchor)]
        if not anchors:
            continue
        for item in block:
            if isinstance(item, tuple):
                top, text = item
                best = min(abs(a.top - top) for a in anchors)
                nearest = next(a for a in anchors if abs(a.top - top) <= best + _TIE)
                nearest.parts.append((top, text))


def _parse_lines(pages: list[list[_Line]], profile: Profile, st: Statement, source: str) -> None:
    """Unknown layout: movements are lines starting with a date; the sign is guessed from the wording."""
    for page_no, lines in enumerate(pages, start=1):
        current: Transaction | None = None
        for line in lines:
            if _balance(line, profile, None, st):
                current = None
                continue
            amounts = _amounts(line)
            words = line.words
            booking = parse_date(words[0].text)
            if booking is None:
                if current is not None and not amounts and not _STOP.search(line.text):
                    current.description = f"{current.description} {line.text}"
                else:
                    current = None
                continue
            if not amounts:
                st.warnings.append(f"p.{page_no}: riga con data ma senza importo, ignorata: {line.text}")
                current = None
                continue
            skip = {id(words[0])}
            value_date = parse_date(words[1].text) if len(words) > 1 else None
            if value_date:
                skip.add(id(words[1]))
            word, value = amounts[-1]
            skip.add(id(word))
            description = " ".join(w.text for w in words if id(w) not in skip)
            uncertain = value >= 0
            amount = value if value < 0 else value * _guess_sign(description)
            current = Transaction(bank=profile.key, booking_date=booking, value_date=value_date,
                                  description=description, amount=amount, source=source, page=page_no,
                                  sign_uncertain=uncertain)
            st.transactions.append(current)
