"""Shared data models — Feed, FeedItem, Insight."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class FeedItem:
    """Single message / conversation turn — analogous to an RSS <item>."""
    id: str
    feed_id: str
    timestamp: datetime
    author: str          # "user" | "assistant" | WhatsApp display name
    content: str
    word_count: int = 0
    tags: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.word_count:
            self.word_count = len(self.content.split())


@dataclass
class Feed:
    """One chat source — analogous to an RSS <channel>."""
    id: str
    title: str
    source_type: str     # "claude_session" | "whatsapp" | "audit_log"
    source_path: str
    items: list[FeedItem] = field(default_factory=list)
    description: str = ""

    @property
    def item_count(self) -> int:
        return len(self.items)

    @property
    def first_date(self) -> Optional[datetime]:
        return min((i.timestamp for i in self.items), default=None)

    @property
    def last_date(self) -> Optional[datetime]:
        return max((i.timestamp for i in self.items), default=None)

    @property
    def authors(self) -> list[str]:
        return sorted(set(i.author for i in self.items))
