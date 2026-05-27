"""Build a valid RSS 2.0 XML feed from a list of FeedItems.

Each FeedItem → <item> with title, description, pubDate, author, category tags.
Each Feed    → <channel> (multi-feed export wraps all channels in a custom root).
"""
from datetime import datetime, timezone
from email.utils import format_datetime
from xml.etree.ElementTree import (
    Element, SubElement, ElementTree, indent, tostring
)

from .models import Feed, FeedItem


def _rfc822(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return format_datetime(dt)


def _item_element(item: FeedItem) -> Element:
    el = Element("item")
    title_text = item.content[:80].replace("\n", " ")
    if len(item.content) > 80:
        title_text += "…"
    SubElement(el, "title").text = title_text
    SubElement(el, "description").text = item.content
    SubElement(el, "pubDate").text = _rfc822(item.timestamp)
    SubElement(el, "author").text = item.author
    SubElement(el, "guid").text = item.id
    for tag in item.tags:
        SubElement(el, "category").text = tag
    return el


def feed_to_rss(feed: Feed, site_link: str = "https://aistudio.local") -> bytes:
    """Render a single Feed as RSS 2.0 XML bytes."""
    rss = Element("rss", version="2.0")
    channel = SubElement(rss, "channel")
    SubElement(channel, "title").text = feed.title
    SubElement(channel, "link").text = site_link
    SubElement(channel, "description").text = feed.description
    SubElement(channel, "language").text = "it"
    if feed.last_date:
        SubElement(channel, "lastBuildDate").text = _rfc822(feed.last_date)

    for item in sorted(feed.items, key=lambda x: x.timestamp, reverse=True):
        channel.append(_item_element(item))

    indent(rss, space="  ")
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(rss, encoding="unicode").encode()


def feeds_to_opml(feeds: list[Feed], title: str = "AI Studio Chat Feeds") -> bytes:
    """Export feed list as OPML (like an RSS reader subscription list)."""
    opml = Element("opml", version="2.0")
    head = SubElement(opml, "head")
    SubElement(head, "title").text = title
    SubElement(head, "dateCreated").text = _rfc822(datetime.now(timezone.utc))
    body = SubElement(opml, "body")

    type_groups: dict[str, list[Feed]] = {}
    for f in feeds:
        type_groups.setdefault(f.source_type, []).append(f)

    for src_type, group in type_groups.items():
        group_el = SubElement(body, "outline", text=src_type, title=src_type)
        for f in group:
            SubElement(group_el, "outline",
                       text=f.title,
                       title=f.title,
                       type="rss",
                       xmlUrl=f"feed://{f.source_type}/{f.id}",
                       description=f.description)

    indent(opml, space="  ")
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(opml, encoding="unicode").encode()


def all_feeds_to_rss(feeds: list[Feed], top_n: int = 200) -> bytes:
    """Merge all feeds into a single RSS channel sorted by recency."""
    all_items = sorted(
        [item for f in feeds for item in f.items],
        key=lambda x: x.timestamp,
        reverse=True,
    )[:top_n]

    merged_feed = Feed(
        id="all_feeds_merged",
        title="AI Studio — All Chats",
        source_type="merged",
        source_path="",
        items=all_items,
        description=f"Merged feed from {len(feeds)} sources, {len(all_items)} most recent items.",
    )
    return feed_to_rss(merged_feed)
