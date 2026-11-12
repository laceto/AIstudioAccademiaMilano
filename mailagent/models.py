"""Plain data shapes shared by every provider, the extractor and the store."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class Email:
    account_id: str
    id: str
    thread_id: str
    sender: str
    subject: str
    received_at: str  # ISO 8601, UTC
    body: str  # plain text
    link: str = ""


class TodoItem(BaseModel):
    title: str
    due: str | None = None  # ISO date or datetime, if the email states one
    priority: Literal["low", "normal", "high"] = "normal"
    confidence: float = Field(default=1.0, ge=0, le=1)


class EventItem(BaseModel):
    title: str
    start: str  # ISO 8601; a bare date means all-day
    end: str | None = None
    location: str | None = None
    confidence: float = Field(default=1.0, ge=0, le=1)


class Extraction(BaseModel):
    todos: list[TodoItem] = Field(default_factory=list)
    event: EventItem | None = None
