"""Provider registry: how a new mail/calendar system plugs in.

Adding an account of a known type is a YAML block. Adding a new *type* is one module that
decorates a factory with @register_mail("type") and/or @register_calendar("type"); the
pipeline never imports a concrete provider.
"""

from __future__ import annotations

from typing import Callable, Protocol

from ..config import AccountConfig
from ..models import Email


class MailProvider(Protocol):
    def list_new(self, since, max_results: int) -> list[Email]: ...


class CalendarProvider(Protocol):
    def find_conflicts(self, start: str, end: str) -> list[dict]: ...
    def create_event(self, item: dict) -> str: ...


class UnknownProvider(KeyError):
    pass


_MAIL: dict[str, Callable[[AccountConfig], MailProvider]] = {}
_CAL: dict[str, Callable[[AccountConfig], CalendarProvider]] = {}


def register_mail(kind: str):
    def deco(factory):
        _MAIL[kind] = factory
        return factory
    return deco


def register_calendar(kind: str):
    def deco(factory):
        _CAL[kind] = factory
        return factory
    return deco


def _lookup(table: dict, kind: str, what: str):
    _load_builtin()
    if kind not in table:
        raise UnknownProvider(f"no {what} provider {kind!r}; known: {sorted(table)}")
    return table[kind]


def build_mail(cfg: AccountConfig) -> MailProvider:
    return _lookup(_MAIL, cfg.provider, "mail")(cfg)


def build_calendar(cfg: AccountConfig) -> CalendarProvider:
    return _lookup(_CAL, cfg.calendar or cfg.provider, "calendar")(cfg)


def _load_builtin() -> None:
    from . import gmail  # noqa: F401  (registers itself)
    # new provider types: import their module here
