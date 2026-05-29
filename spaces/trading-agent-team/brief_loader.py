"""Parse the myfinance2 daily brief for bull/bear Italian stock candidates.

Fetches from raw GitHub on demand; callers use st.cache_data for TTL.
"""
from __future__ import annotations

import re
import urllib.request

BRIEF_URL = (
    "https://raw.githubusercontent.com/laceto/myfinance2/main"
    "/data/results/it/daily_brief.txt"
)


def fetch_brief(url: str = BRIEF_URL) -> dict:
    """Return {bull: [symbols], bear: [symbols], date: str, error: str|None}."""
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            text = resp.read().decode("utf-8")
        return _parse(text)
    except Exception as exc:
        return {"bull": [], "bear": [], "date": "", "error": str(exc)}


def _parse(text: str) -> dict:
    bull: list[str] = []
    bear: list[str] = []

    m = re.search(r"DAILY BRIEF\s*[—-]\s*(\d{4}-\d{2}-\d{2})", text)
    date = m.group(1) if m else ""

    section: str | None = None
    for line in text.splitlines():
        if "BULL CANDIDATES" in line:
            section = "bull"
            continue
        if "BEAR CANDIDATES" in line:
            section = "bear"
            continue
        if any(kw in line for kw in ("REGIME FLIPS", "VOLUME MOVERS", "SIGNAL FLIPS")):
            section = None
            continue

        if section not in ("bull", "bear"):
            continue

        parts = line.split()
        if len(parts) < 4:
            continue
        try:
            float(parts[0])          # first field must be a numeric conviction score
        except ValueError:
            continue

        symbol = parts[3]
        if "." not in symbol:        # e.g. OVS.MI — must have exchange suffix
            continue

        (bull if section == "bull" else bear).append(symbol)

    return {"bull": bull, "bear": bear, "date": date, "error": None}
