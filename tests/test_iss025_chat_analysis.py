"""Tests for Chat-to-Insights RSS Pipeline (deliverable 025)."""
import json
from datetime import datetime
from pathlib import Path

import pytest

from scripts.chat_analysis.models import Feed, FeedItem
from scripts.chat_analysis.whatsapp_parser import parse_whatsapp_text
from scripts.chat_analysis.claude_parser import load_audit_feeds, _parse_jsonl_session
from scripts.chat_analysis.analyzer import analyze_feeds
from scripts.chat_analysis.rss_builder import feed_to_rss, feeds_to_opml, all_feeds_to_rss


# ── Fixtures ─────────────────────────────────────────────────────────────────

WHATSAPP_IOS = """\
[27/05/2026, 10:00:00] Luigi: Ciao Marco come stai
[27/05/2026, 10:01:15] Marco: Tutto bene grazie Luigi
[27/05/2026, 10:02:00] Luigi: Ottimo perfetto ci vediamo dopo
[27/05/2026, 11:30:00] Marco: Sì confermato a presto
"""

WHATSAPP_ANDROID = """\
27/05/2026, 10:00 - Luigi: Ciao Marco come stai
27/05/2026, 10:01 - Marco: Tutto bene grazie Luigi
27/05/2026, 10:02 - Luigi: Ottimo perfetto ci vediamo dopo
"""

JSONL_SESSION = "\n".join([
    json.dumps({"role": "user", "content": "How does the RSS pipeline work?", "timestamp": "2026-05-27T09:00:00Z"}),
    json.dumps({"role": "assistant", "content": "The RSS pipeline parses chat feeds and produces insights.", "timestamp": "2026-05-27T09:00:05Z"}),
    json.dumps({"role": "user", "content": "Can it handle WhatsApp exports?", "timestamp": "2026-05-27T09:01:00Z"}),
])


# ── WhatsApp parser ───────────────────────────────────────────────────────────

def test_whatsapp_ios_parses_messages():
    feed = parse_whatsapp_text(WHATSAPP_IOS, "ios_chat")
    assert feed.item_count == 4
    assert feed.source_type == "whatsapp"
    assert "Luigi" in feed.authors
    assert "Marco" in feed.authors


def test_whatsapp_android_parses_messages():
    feed = parse_whatsapp_text(WHATSAPP_ANDROID, "android_chat")
    assert feed.item_count == 3
    assert "Luigi" in feed.authors


def test_whatsapp_timestamps():
    feed = parse_whatsapp_text(WHATSAPP_IOS, "ts_test")
    ts = feed.items[0].timestamp
    assert ts.year == 2026
    assert ts.month == 5
    assert ts.day == 27


def test_whatsapp_empty_file():
    feed = parse_whatsapp_text("", "empty")
    assert feed.item_count == 0


def test_whatsapp_multiline_message():
    text = "[27/05/2026, 10:00:00] Luigi: Prima riga\nSeconda riga\nTerza riga\n[27/05/2026, 10:01:00] Marco: Ok\n"
    feed = parse_whatsapp_text(text, "multiline")
    assert feed.item_count == 2
    assert "Seconda riga" in feed.items[0].content


# ── Claude JSONL parser ───────────────────────────────────────────────────────

def test_jsonl_parse(tmp_path):
    p = tmp_path / "session.jsonl"
    p.write_text(JSONL_SESSION)
    feed = _parse_jsonl_session(p)
    assert feed.item_count == 3
    assert feed.source_type == "claude_session"
    authors = {i.author for i in feed.items}
    assert "user" in authors
    assert "assistant" in authors


def test_jsonl_empty_file(tmp_path):
    p = tmp_path / "empty.jsonl"
    p.write_text("")
    feed = _parse_jsonl_session(p)
    assert feed.item_count == 0


# ── Audit log parser ──────────────────────────────────────────────────────────

def test_audit_log_loads(tmp_path):
    md = tmp_path / "2026-05-27_025_chat-analysis.md"
    md.write_text("""---
request_id: "025"
intent: chat_analysis
outcome: success
---
## Summary
This is the summary section.
## Details
More detail here.
""")
    feeds = load_audit_feeds(tmp_path)
    assert len(feeds) == 1
    assert feeds[0].source_type == "audit_log"
    assert feeds[0].item_count >= 1


# ── Analyzer ─────────────────────────────────────────────────────────────────

def test_analyze_single_feed():
    feed = parse_whatsapp_text(WHATSAPP_IOS, "test_feed")
    insights = analyze_feeds([feed])
    assert "error" not in insights
    assert insights["summary"]["feed_count"] == 1
    assert insights["summary"]["message_count"] == 4
    assert isinstance(insights["keywords"], list)
    assert len(insights["keywords"]) > 0


def test_analyze_multiple_feeds():
    f1 = parse_whatsapp_text(WHATSAPP_IOS, "f1")
    f2 = parse_whatsapp_text(WHATSAPP_ANDROID, "f2")
    insights = analyze_feeds([f1, f2])
    assert insights["summary"]["feed_count"] == 2
    assert insights["summary"]["message_count"] == 7


def test_analyze_empty_feeds():
    insights = analyze_feeds([])
    assert "error" in insights


def test_sentiment_keys():
    feed = parse_whatsapp_text(WHATSAPP_IOS, "sent_test")
    insights = analyze_feeds([feed])
    sent = insights["sentiment"]
    assert set(sent.keys()) == {"positive", "negative", "neutral"}


def test_activity_by_day():
    feed = parse_whatsapp_text(WHATSAPP_IOS, "timeline_test")
    insights = analyze_feeds([feed])
    assert len(insights["activity_by_day"]) >= 1


def test_author_stats():
    feed = parse_whatsapp_text(WHATSAPP_IOS, "author_test")
    insights = analyze_feeds([feed])
    authors = {a["author"] for a in insights["authors"]}
    assert "Luigi" in authors
    assert "Marco" in authors


# ── RSS builder ───────────────────────────────────────────────────────────────

def test_feed_to_rss_valid_xml():
    from xml.etree.ElementTree import fromstring
    feed = parse_whatsapp_text(WHATSAPP_IOS, "rss_test")
    rss_bytes = feed_to_rss(feed)
    assert b"<rss" in rss_bytes
    root = fromstring(rss_bytes.decode())
    assert root.tag == "rss"
    items = root.findall(".//item")
    assert len(items) == 4


def test_feeds_to_opml():
    from xml.etree.ElementTree import fromstring
    f1 = parse_whatsapp_text(WHATSAPP_IOS, "f1")
    f2 = parse_whatsapp_text(WHATSAPP_ANDROID, "f2")
    opml = feeds_to_opml([f1, f2])
    assert b"<opml" in opml
    root = fromstring(opml.decode())
    outlines = root.findall(".//outline[@type='rss']")
    assert len(outlines) == 2


def test_all_feeds_to_rss_top_n():
    from xml.etree.ElementTree import fromstring
    f1 = parse_whatsapp_text(WHATSAPP_IOS, "f1")
    f2 = parse_whatsapp_text(WHATSAPP_ANDROID, "f2")
    rss = all_feeds_to_rss([f1, f2], top_n=3)
    root = fromstring(rss.decode())
    items = root.findall(".//item")
    assert len(items) <= 3


def test_rss_contains_author():
    from xml.etree.ElementTree import fromstring
    feed = parse_whatsapp_text(WHATSAPP_IOS, "author_rss")
    rss = feed_to_rss(feed)
    root = fromstring(rss.decode())
    authors = [el.text for el in root.findall(".//author")]
    assert "Luigi" in authors or "Marco" in authors
