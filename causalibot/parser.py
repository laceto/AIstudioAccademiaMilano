"""Free-text message -> causale, by rules only (no model, nothing leaves the service).

    250 credem pulizie Valeria       today, credem, -250.00
    ieri 40 ing parrucchiere         yesterday, ing, -40.00
    15/11 +120 credem rimborso Marco 15 Nov, credem, +120.00 (income)

The bank is always required: there is no default, a missing bank is an error.
"""
import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

BANKS = ("credem", "ing", "fineco")
_INCOME_WORDS = {"entrata", "ricevuto", "ricevuta", "accredito"}
_DATE = re.compile(r"^(\d{1,2})/(\d{1,2})(?:/(\d{2}|\d{4}))?$")
_AMOUNT = re.compile(r"^([+-]?)(\d[\d.,]*)€?$")
_THOUSANDS = re.compile(r"^\d{1,3}(\.\d{3})+$")
_DECIMAL_DOT = re.compile(r"^\d+\.\d{1,2}$")
_CENT = Decimal("0.01")


class ParseError(ValueError):
    """The message cannot be read; the text is what the bot answers."""


@dataclass(frozen=True)
class ParsedCausale:
    day: date
    bank: str
    amount: Decimal  # signed: negative = uscita
    causale: str


def _amount(raw: str) -> Decimal:
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif "." in raw:
        if _THOUSANDS.match(raw):
            raw = raw.replace(".", "")
        elif not _DECIMAL_DOT.match(raw):
            raise ParseError(f"importo non valido: {raw}")
    try:
        return Decimal(raw).quantize(_CENT)
    except InvalidOperation:
        raise ParseError(f"importo non valido: {raw}") from None


def _date(token: str, today: date) -> date:
    if token == "oggi":
        return today
    if token == "ieri":
        return today - timedelta(days=1)
    d, m, y = _DATE.match(token).groups()
    try:
        if y:
            return date(int(y) + 2000 if len(y) == 2 else int(y), int(m), int(d))
        found = date(today.year, int(m), int(d))
    except ValueError:
        raise ParseError(f"data non valida: {token}") from None
    return found if found <= today else date(today.year - 1, int(m), int(d))


def parse_message(text: str, today: date) -> ParsedCausale:
    tokens = text.split()

    bank = next((t.lower() for t in tokens if t.lower() in BANKS), None)
    if bank is None:
        raise ParseError(f"manca la banca: scrivi {' / '.join(BANKS)}")
    tokens.remove(next(t for t in tokens if t.lower() == bank))

    when = next((t for t in tokens if t.lower() in ("oggi", "ieri") or _DATE.match(t)), None)
    day = today
    if when is not None:
        day = _date(when.lower(), today)
        tokens.remove(when)

    income = any(t.lower() in _INCOME_WORDS for t in tokens)
    tokens = [t for t in tokens if t.lower() not in _INCOME_WORDS]

    amount = None
    for i, t in enumerate(tokens):
        if t in ("+", "-") and i + 1 < len(tokens) and _AMOUNT.match(tokens[i + 1]):
            sign, number = t, _AMOUNT.match(tokens[i + 1]).group(2)
            del tokens[i:i + 2]
        elif (m := _AMOUNT.match(t)):
            sign, number = m.groups()
            del tokens[i]
        else:
            continue
        amount = _amount(number)
        income = income or sign == "+"
        break
    if amount is None or amount == 0:
        raise ParseError("manca l'importo (un numero diverso da zero)")

    causale = " ".join(tokens).strip()
    if not causale:
        raise ParseError("manca la causale: scrivi anche a cosa si riferisce")
    return ParsedCausale(day=day, bank=bank, amount=amount if income else -amount,
                         causale=causale[0].upper() + causale[1:])
