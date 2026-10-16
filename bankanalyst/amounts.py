"""Italian number and date formats as they appear on bank statements."""
import re
from datetime import date
from decimal import Decimal

_AMOUNT = re.compile(r"^(?:€\s?)?([+-])?(\d{1,3}(?:\.\d{3})*|\d+),(\d{2})(-)?$")
_DATE = re.compile(r"^(\d{2})[/.](\d{2})[/.](\d{2}|\d{4})$")


def parse_amount(raw: str) -> Decimal | None:
    """'1.234,56' → 1234.56; a leading or trailing minus makes it negative. None if not an amount."""
    m = _AMOUNT.match(raw.strip())
    if not m:
        return None
    sign, units, cents, trailing = m.groups()
    value = Decimal(f"{units.replace('.', '')}.{cents}")
    return -value if sign == "-" or trailing else value


def parse_date(raw: str) -> date | None:
    m = _DATE.match(raw.strip())
    if not m:
        return None
    d, mth, y = (int(g) for g in m.groups())
    if y < 100:
        y += 2000
    try:
        return date(y, mth, d)
    except ValueError:
        return None


def fmt_eur(value: Decimal) -> str:
    s = f"{value:,.2f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")
