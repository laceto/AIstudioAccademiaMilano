"""Parse Claude Code JSONL conversation files and audit log YAML/MD files into Feeds."""
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .models import Feed, FeedItem


def _parse_jsonl_session(path: Path) -> Feed:
    """Parse a Claude Code .jsonl conversation file."""
    items: list[FeedItem] = []
    feed_id = path.stem

    with open(path, encoding="utf-8", errors="replace") as fh:
        for line_no, raw in enumerate(fh, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue

            # Claude Code JSONL: {type, role, content, timestamp, ...}
            role = obj.get("role") or obj.get("type", "unknown")
            ts_raw = obj.get("timestamp") or obj.get("created_at")
            if ts_raw:
                try:
                    ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
                except ValueError:
                    ts = datetime.now(timezone.utc)
            else:
                ts = datetime.now(timezone.utc)

            content = ""
            raw_content = obj.get("content", "")
            if isinstance(raw_content, str):
                content = raw_content
            elif isinstance(raw_content, list):
                parts = []
                for block in raw_content:
                    if isinstance(block, dict):
                        parts.append(block.get("text", block.get("content", "")))
                    elif isinstance(block, str):
                        parts.append(block)
                content = " ".join(p for p in parts if p)

            if not content:
                continue

            items.append(FeedItem(
                id=f"{feed_id}_{line_no}",
                feed_id=feed_id,
                timestamp=ts,
                author=role,
                content=content,
            ))

    title = path.parent.name + "/" + path.stem
    return Feed(
        id=feed_id,
        title=title,
        source_type="claude_session",
        source_path=str(path),
        items=items,
        description=f"Claude Code session from {path.name}",
    )


def _parse_audit_log(path: Path) -> Feed:
    """Parse a process/audit/*.md file (YAML front-matter + Markdown body)."""
    text = path.read_text(encoding="utf-8", errors="replace")
    feed_id = path.stem

    # Extract date from filename: YYYY-MM-DD_NNN_slug.md
    date_match = re.match(r"(\d{4}-\d{2}-\d{2})", path.stem)
    if date_match:
        try:
            base_ts = datetime.fromisoformat(date_match.group(1))
        except ValueError:
            base_ts = datetime.now()
    else:
        base_ts = datetime.now()

    # Extract YAML fields for basic metadata
    intent_match = re.search(r"intent:\s*(.+)", text)
    outcome_match = re.search(r"outcome:\s*(.+)", text)
    intent = intent_match.group(1).strip() if intent_match else "unknown"
    outcome = outcome_match.group(1).strip() if outcome_match else "unknown"

    # Each H2 section becomes a feed item
    sections = re.split(r"\n## ", text)
    items: list[FeedItem] = []
    for idx, section in enumerate(sections):
        section = section.strip()
        if not section:
            continue
        lines = section.splitlines()
        heading = lines[0].lstrip("#").strip() if lines else f"Section {idx}"
        body = "\n".join(lines[1:]).strip()
        if not body:
            body = section

        items.append(FeedItem(
            id=f"{feed_id}_{idx}",
            feed_id=feed_id,
            timestamp=base_ts,
            author="audit_log",
            content=body or heading,
            tags=[intent, outcome],
        ))

    return Feed(
        id=feed_id,
        title=path.stem,
        source_type="audit_log",
        source_path=str(path),
        items=items,
        description=f"Audit log — intent={intent}, outcome={outcome}",
    )


def load_claude_feeds(claude_dir: Path) -> list[Feed]:
    """Scan a .claude directory tree for JSONL session files."""
    feeds: list[Feed] = []
    for jsonl_path in claude_dir.rglob("*.jsonl"):
        try:
            feed = _parse_jsonl_session(jsonl_path)
            if feed.items:
                feeds.append(feed)
        except Exception:
            pass
    return feeds


def load_audit_feeds(audit_dir: Path) -> list[Feed]:
    """Load all audit log .md files as feeds."""
    feeds: list[Feed] = []
    for md_path in sorted(audit_dir.glob("*.md")):
        if md_path.name == "README.md":
            continue
        try:
            feed = _parse_audit_log(md_path)
            if feed.items:
                feeds.append(feed)
        except Exception:
            pass
    return feeds
