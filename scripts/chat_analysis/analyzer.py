"""Extract insights from a collection of Feeds without heavy NLP dependencies.

Produces:
  - keyword / topic frequency (stopword-filtered)
  - activity timeline (messages per day)
  - top authors
  - hourly heatmap
  - longest / most active feeds
  - simple sentiment proxy (positive/negative keyword ratio)
"""
import re
from collections import Counter, defaultdict
from datetime import datetime, date
from typing import Any

from .models import Feed, FeedItem


# Minimal multilingual stopword set (Italian + English)
_STOPWORDS = {
    "the","a","an","in","on","at","to","of","and","or","is","it","be","for",
    "this","that","with","from","by","as","are","was","were","have","has",
    "i","you","he","she","we","they","my","your","his","her","our","their",
    "me","him","us","them","not","but","if","so","do","did","done","can",
    "will","would","could","should","may","might","shall","been","being",
    # Italian
    "il","la","lo","le","gli","un","una","uno","del","della","dei","degli",
    "delle","e","è","in","a","di","da","per","su","con","non","ma","se",
    "ho","hai","ha","abbiamo","avete","hanno","sono","sei","siamo","siete",
    "mi","ti","si","ci","vi","che","chi","come","cosa","quando","dove","perché",
    "anche","già","ancora","sempre","mai","tutto","tutti","ogni","più","meno",
    "molto","poco","questo","quello","qui","lì","no","sì","io","tu","lui","lei",
    "noi","voi","loro","me","te","gli","ne","lo","la","li","le","ne","al","del",
    "nel","sul","col","tra","fra","poi","però","quindi","allora","mentre",
    "perché","però","quindi","invece","tuttavia","comunque",
    # Common chat noise
    "ok","okay","yes","no","yeah","nope","lol","omg","wtf","haha","hehe",
    "https","http","www","com","it","org","net","media","omitted","message",
    "deleted","this","image","video","audio","sticker","gif","document",
}

_POSITIVE = {"buono","bene","ottimo","perfetto","grazie","bravo","brava","sì",
              "good","great","excellent","perfect","thanks","nice","love","happy",
              "sure","yes","ok","done","success","complete","amazing"}
_NEGATIVE = {"male","brutto","sbagliato","errore","problema","no","non","mai",
              "bad","wrong","error","problem","fail","issue","broken","sad",
              "sorry","unfortunately","not","never","cannot","can't","won't"}


def _tokenize(text: str) -> list[str]:
    return [w.lower() for w in re.findall(r"[a-zA-ZÀ-ÿ]{3,}", text)]


def _keywords(items: list[FeedItem], top_n: int = 30) -> list[tuple[str, int]]:
    counter: Counter = Counter()
    for item in items:
        for tok in _tokenize(item.content):
            if tok not in _STOPWORDS:
                counter[tok] += 1
    return counter.most_common(top_n)


def _activity_by_day(items: list[FeedItem]) -> dict[date, int]:
    by_day: dict[date, int] = defaultdict(int)
    for item in items:
        by_day[item.timestamp.date()] += 1
    return dict(sorted(by_day.items()))


def _hourly_heatmap(items: list[FeedItem]) -> dict[int, int]:
    by_hour: dict[int, int] = defaultdict(int)
    for item in items:
        by_hour[item.timestamp.hour] += 1
    return dict(sorted(by_hour.items()))


def _author_stats(items: list[FeedItem]) -> list[dict]:
    by_author: dict[str, dict] = defaultdict(lambda: {"messages": 0, "words": 0})
    for item in items:
        by_author[item.author]["messages"] += 1
        by_author[item.author]["words"] += item.word_count
    return sorted(
        [{"author": k, **v} for k, v in by_author.items()],
        key=lambda x: x["messages"],
        reverse=True,
    )


def _sentiment(items: list[FeedItem]) -> dict[str, float]:
    pos = neg = total = 0
    for item in items:
        toks = set(_tokenize(item.content))
        pos += len(toks & _POSITIVE)
        neg += len(toks & _NEGATIVE)
        total += 1
    if total == 0:
        return {"positive": 0.0, "negative": 0.0, "neutral": 1.0}
    p = pos / total
    n = neg / total
    neutral = max(0.0, 1.0 - p - n)
    return {"positive": round(p, 3), "negative": round(n, 3), "neutral": round(neutral, 3)}


def analyze_feeds(feeds: list[Feed]) -> dict[str, Any]:
    """Run all analysis passes over a list of feeds and return an insights dict."""
    all_items: list[FeedItem] = [item for feed in feeds for item in feed.items]

    if not all_items:
        return {"error": "No items found across all feeds."}

    dates = [i.timestamp for i in all_items]
    total_words = sum(i.word_count for i in all_items)

    return {
        "summary": {
            "feed_count": len(feeds),
            "message_count": len(all_items),
            "total_words": total_words,
            "avg_words_per_message": round(total_words / len(all_items), 1),
            "date_range": {
                "first": min(dates).isoformat(),
                "last": max(dates).isoformat(),
            },
            "source_types": list({f.source_type for f in feeds}),
        },
        "keywords": _keywords(all_items, top_n=40),
        "activity_by_day": {str(k): v for k, v in _activity_by_day(all_items).items()},
        "hourly_heatmap": _hourly_heatmap(all_items),
        "authors": _author_stats(all_items),
        "sentiment": _sentiment(all_items),
        "feeds": [
            {
                "id": f.id,
                "title": f.title,
                "type": f.source_type,
                "messages": f.item_count,
                "authors": f.authors,
                "first": f.first_date.isoformat() if f.first_date else None,
                "last": f.last_date.isoformat() if f.last_date else None,
            }
            for f in sorted(feeds, key=lambda x: x.item_count, reverse=True)
        ],
        "per_feed_keywords": {
            f.id: [kw for kw, _ in _keywords(f.items, top_n=10)]
            for f in feeds
        },
    }
