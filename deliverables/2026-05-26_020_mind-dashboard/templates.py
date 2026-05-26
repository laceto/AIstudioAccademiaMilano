"""Render a validated briefing dict into Markdown and HTML."""

from __future__ import annotations

from typing import Any

REQUIRED_KEYS = (
    "tldr",
    "metrics",
    "wins",
    "tasks_completed",
    "anxieties_backlog",
    "insight",
    "tomorrow_top_3",
)


def validate(briefing: dict[str, Any]) -> None:
    missing = [k for k in REQUIRED_KEYS if k not in briefing]
    if missing:
        raise ValueError(f"Briefing missing keys: {missing}")
    if not isinstance(briefing["metrics"], list) or not briefing["metrics"]:
        raise ValueError("metrics must be a non-empty list")
    for m in briefing["metrics"]:
        if "name" not in m or "value" not in m:
            raise ValueError(f"Bad metric entry: {m!r}")
    top3 = briefing["tomorrow_top_3"]
    if not isinstance(top3, list) or len(top3) != 3:
        raise ValueError("tomorrow_top_3 must be a list of exactly 3 items")


def _bullets(items: list[str]) -> str:
    if not items:
        return "_None recorded._"
    return "\n".join(f"- {item}" for item in items)


def render_markdown(briefing: dict[str, Any], date_str: str) -> str:
    validate(briefing)
    metric_rows = "\n".join(
        f"| {m['name']} | {m['value']} |" for m in briefing["metrics"]
    )
    tomorrow = "\n".join(
        f"{i + 1}. {item}" for i, item in enumerate(briefing["tomorrow_top_3"])
    )
    return f"""# Mind Dashboard — {date_str}

## ⚡ The TL;DR

{briefing["tldr"]}

## 📊 Metric Extraction

| Metric | Value |
|---|---|
{metric_rows}

## 🏷️ Categorized Log

### Wins
{_bullets(briefing["wins"])}

### Tasks Completed
{_bullets(briefing["tasks_completed"])}

### Anxieties / Backlog
{_bullets(briefing["anxieties_backlog"])}

## 💡 The AI Insight

{briefing["insight"]}

## 🌱 Tomorrow's Top 3

{tomorrow}
"""


_HTML_SHELL = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Mind Dashboard — {date}</title>
<style>
:root {{ color-scheme: light dark; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
       max-width: 760px; margin: 2.5rem auto; padding: 0 1.25rem; line-height: 1.55; }}
h1 {{ font-size: 1.9rem; margin-bottom: 0.25rem; }}
h2 {{ margin-top: 2.25rem; border-bottom: 1px solid rgba(127,127,127,0.25); padding-bottom: 0.3rem; }}
h3 {{ margin-top: 1.4rem; font-size: 1.05rem; opacity: 0.85; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ text-align: left; padding: 0.45rem 0.6rem; border-bottom: 1px solid rgba(127,127,127,0.2); }}
th {{ font-weight: 600; }}
.tldr {{ font-size: 1.1rem; padding: 0.9rem 1.1rem; border-left: 3px solid #4f46e5;
        background: rgba(79,70,229,0.07); border-radius: 0 6px 6px 0; }}
.insight {{ padding: 0.9rem 1.1rem; border-left: 3px solid #16a34a;
           background: rgba(22,163,74,0.07); border-radius: 0 6px 6px 0; }}
ol, ul {{ padding-left: 1.3rem; }}
li {{ margin: 0.2rem 0; }}
.muted {{ opacity: 0.6; font-style: italic; }}
</style>
</head>
<body>
<h1>Mind Dashboard</h1>
<div class="muted">{date}</div>

<h2>⚡ The TL;DR</h2>
<p class="tldr">{tldr}</p>

<h2>📊 Metric Extraction</h2>
<table><thead><tr><th>Metric</th><th>Value</th></tr></thead><tbody>
{metric_rows}
</tbody></table>

<h2>🏷️ Categorized Log</h2>
<h3>Wins</h3>{wins}
<h3>Tasks Completed</h3>{tasks}
<h3>Anxieties / Backlog</h3>{anx}

<h2>💡 The AI Insight</h2>
<p class="insight">{insight}</p>

<h2>🌱 Tomorrow's Top 3</h2>
<ol>{tomorrow}</ol>
</body>
</html>
"""


def _html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _html_list(items: list[str], ordered: bool = False) -> str:
    if not items:
        return '<p class="muted">None recorded.</p>'
    tag = "ol" if ordered else "ul"
    lis = "".join(f"<li>{_html_escape(item)}</li>" for item in items)
    return f"<{tag}>{lis}</{tag}>"


def render_html(briefing: dict[str, Any], date_str: str) -> str:
    validate(briefing)
    metric_rows = "\n".join(
        f"<tr><td>{_html_escape(m['name'])}</td><td>{_html_escape(m['value'])}</td></tr>"
        for m in briefing["metrics"]
    )
    tomorrow = "".join(
        f"<li>{_html_escape(item)}</li>" for item in briefing["tomorrow_top_3"]
    )
    return _HTML_SHELL.format(
        date=_html_escape(date_str),
        tldr=_html_escape(briefing["tldr"]),
        metric_rows=metric_rows,
        wins=_html_list(briefing["wins"]),
        tasks=_html_list(briefing["tasks_completed"]),
        anx=_html_list(briefing["anxieties_backlog"]),
        insight=_html_escape(briefing["insight"]),
        tomorrow=tomorrow,
    )
