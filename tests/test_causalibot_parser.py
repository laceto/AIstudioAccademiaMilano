"""Offline tests for causalibot.parser: a free-text message becomes a causale, by rules only."""
from datetime import date
from decimal import Decimal

import pytest

from causalibot.parser import ParseError, parse_message

TODAY = date(2026, 11, 17)


def ok(text):
    return parse_message(text, today=TODAY)


def test_basic_outflow_today():
    p = ok("250 credem pulizie Valeria")
    assert (p.day, p.bank, p.amount, p.causale) == (TODAY, "credem", Decimal("-250.00"), "Pulizie Valeria")


def test_bank_is_never_defaulted():
    with pytest.raises(ParseError, match="banca"):
        ok("pulizie 250")


def test_bank_must_be_a_whole_word():
    with pytest.raises(ParseError, match="banca"):
        ok("250 booking viaggio")  # "ing" inside "booking" is not a bank


def test_yesterday_and_ing():
    p = ok("ieri 40 ing parrucchiere")
    assert p.day == date(2026, 11, 16) and p.bank == "ing" and p.amount == Decimal("-40.00")


def test_explicit_income_with_plus_and_date():
    p = ok("15/11 +120 credem rimborso Marco")
    assert p.day == date(2026, 11, 15) and p.amount == Decimal("120.00") and p.causale == "Rimborso Marco"


def test_income_by_word():
    assert ok("80 ing ricevuto da Anna").amount == Decimal("80.00")
    assert ok("80 ing entrata affitto").amount == Decimal("80.00")


@pytest.mark.parametrize("raw,expected", [
    ("250", "250.00"), ("250,50", "250.50"), ("1.250", "1250.00"), ("1.250,50", "1250.50"), ("250.5", "250.50"),
])
def test_italian_amounts(raw, expected):
    assert ok(f"{raw} credem spesa").amount == -Decimal(expected)


def test_date_without_year_never_in_the_future():
    assert ok("20/12 30 credem regalo").day == date(2025, 12, 20)


def test_date_with_year():
    assert ok("03/02/2026 30 credem regalo").day == date(2026, 2, 3)


def test_date_is_not_read_as_amount():
    p = ok("15/11 credem 99 libri")
    assert p.amount == Decimal("-99.00") and p.day == date(2026, 11, 15)


def test_amount_missing_or_zero():
    with pytest.raises(ParseError, match="importo"):
        ok("credem pulizie")
    with pytest.raises(ParseError, match="importo"):
        ok("0 credem pulizie")


def test_causale_missing():
    with pytest.raises(ParseError, match="causale"):
        ok("250 credem")


def test_impossible_date():
    with pytest.raises(ParseError, match="data"):
        ok("31/02 250 credem pulizie")


def test_later_numbers_stay_in_the_causale():
    assert ok("250 credem pulizie 2 volte").causale == "Pulizie 2 volte"
