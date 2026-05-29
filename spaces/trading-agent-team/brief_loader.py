"""Parse the myfinance2 daily brief — all signal sections.

Returns structured data for:
  - Bull / bear candidates (conviction, score, daily_return, etc.)
  - Signal flips (which methods fired per symbol today)
  - Regime flips (bullish/bearish regime changes from today)
"""
from __future__ import annotations

import re
import urllib.request

BRIEF_URL = (
    "https://raw.githubusercontent.com/laceto/myfinance2/main"
    "/data/results/it/daily_brief.txt"
)
_COMMITS_API = (
    "https://api.github.com/repos/laceto/myfinance2/commits"
    "?path=data/results/it/daily_brief.txt&per_page={n}"
)
_RAW_AT_SHA = (
    "https://raw.githubusercontent.com/laceto/myfinance2/{sha}"
    "/data/results/it/daily_brief.txt"
)

SIGNAL_METHODS = {
    "rbo_20", "rbo_50",
    "rema_100150", "rema_50100", "rema_50100150",
    "rsma_100150", "rsma_50100", "rsma_50100150",
    "rtt_5020",
}


def fetch_brief_history(n_days: int = 7) -> list[dict]:
    """Fetch signal flips from the last n_days versions of daily_brief.txt.

    Returns a list of parsed briefs (same structure as fetch_brief()),
    ordered newest-first. Today's brief is index 0.
    Skips commits that fail to fetch or parse — never raises.
    """
    import json

    try:
        url = _COMMITS_API.format(n=n_days + 1)  # +1 buffer for weekends/gaps
        with urllib.request.urlopen(url, timeout=10) as resp:
            commits = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return [{"date": "", "bull": [], "bear": [], "signal_flips": {},
                 "regime_flips": {}, "error": str(exc)}]

    results = []
    for commit in commits[:n_days]:
        sha = commit["sha"]
        raw_url = _RAW_AT_SHA.format(sha=sha)
        try:
            with urllib.request.urlopen(raw_url, timeout=10) as resp:
                text = resp.read().decode("utf-8")
            results.append(_parse(text))
        except Exception:
            continue  # skip failed days silently

    return results


def fetch_brief(url: str = BRIEF_URL) -> dict:
    """Fetch and fully parse the daily brief.

    Returns:
      {
        date: str,
        bull: [CandidateDict, ...],   # long candidates, ranked by conviction
        bear: [CandidateDict, ...],   # short candidates
        signal_flips: {symbol: [method, ...]},   # methods that fired today
        regime_flips: {symbol: {"date": str, "rrg": float}},  # today's flips
        error: str | None,
      }

    CandidateDict keys: symbol, name, sector, conviction, score, score_delta,
                        days_since_change, momentum, daily_return
    """
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            text = resp.read().decode("utf-8")
        return _parse(text)
    except Exception as exc:
        return {
            "date": "", "bull": [], "bear": [],
            "signal_flips": {}, "regime_flips": {}, "error": str(exc),
        }


# ── parsers ───────────────────────────────────────────────────────────────────

def _parse(text: str) -> dict:
    m = re.search(r"DAILY BRIEF\s*[—-]\s*(\d{4}-\d{2}-\d{2})", text)
    date = m.group(1) if m else ""

    bull, bear = _parse_candidates(text)
    signal_flips = _parse_signal_flips(text)
    regime_flips = _parse_regime_flips(text, date)

    return {
        "date": date,
        "bull": bull,
        "bear": bear,
        "signal_flips": signal_flips,
        "regime_flips": regime_flips,
        "error": None,
    }


def _parse_candidates(text: str) -> tuple[list[dict], list[dict]]:
    bull: list[dict] = []
    bear: list[dict] = []
    section: str | None = None

    for line in text.splitlines():
        if "BULL CANDIDATES" in line:
            section = "bull"; continue
        if "BEAR CANDIDATES" in line:
            section = "bear"; continue
        if any(k in line for k in ("REGIME FLIPS", "VOLUME MOVERS", "SIGNAL FLIPS")):
            section = None; continue
        if section not in ("bull", "bear"):
            continue

        parts = line.split()
        # Data lines: conviction  score  score_delta  symbol  ...  momentum  daily_return
        if len(parts) < 9:
            continue
        try:
            conviction = float(parts[0])
            score = int(parts[1])
            score_delta = float(parts[2])
        except ValueError:
            continue

        symbol = parts[3]
        if "." not in symbol:
            continue

        # name runs from parts[4] until a numeric field; find last non-numeric block
        # fields after name: sector (1-2 words), days_since_change, momentum, daily_return
        try:
            daily_return = float(parts[-1])
            momentum = float(parts[-2])
            days_since_change = int(parts[-3])
        except (ValueError, IndexError):
            daily_return = momentum = 0.0
            days_since_change = 0

        entry = {
            "symbol": symbol,
            "conviction": conviction,
            "score": score,
            "score_delta": score_delta,
            "days_since_change": days_since_change,
            "momentum": momentum,
            "daily_return": daily_return,
        }
        (bull if section == "bull" else bear).append(entry)

    return bull, bear


def _parse_signal_flips(text: str) -> dict[str, dict]:
    """Return {symbol: {direction: 'bull_flip'|'bear_flip', methods: [...]}}
    from the SIGNAL FLIPS — last bar section."""
    flips: dict[str, dict] = {}
    in_section = False
    current_method: str | None = None

    for line in text.splitlines():
        if "SIGNAL FLIPS" in line and "last bar" in line:
            in_section = True; continue
        if not in_section:
            continue
        if "====" in line:
            break  # end of file separator

        m = re.match(r"\s*\[(\w+)\]", line)
        if m:
            current_method = m.group(1)
            continue

        if current_method is None:
            continue

        parts = line.split()
        if len(parts) < 2:
            continue
        direction = parts[0]
        if direction not in ("bull_flip", "bear_flip"):
            continue

        symbol = parts[1]
        if "." not in symbol:
            continue

        if symbol not in flips:
            flips[symbol] = {"direction": direction, "methods": []}
        flips[symbol]["methods"].append(current_method)

    return flips


def _parse_regime_flips(text: str, brief_date: str) -> dict[str, dict]:
    """Return {symbol: {date, rrg}} for regime flips that occurred today."""
    flips: dict[str, dict] = {}
    in_section = False

    for line in text.splitlines():
        if "REGIME FLIPS" in line:
            in_section = True; continue
        if not in_section:
            continue

        parts = line.split()
        # data lines: date  symbol  name...  rrg
        if len(parts) < 3:
            continue
        try:
            flip_date = parts[0]
            rrg = float(parts[-1])
        except ValueError:
            continue
        if not re.match(r"\d{4}-\d{2}-\d{2}", flip_date):
            continue

        symbol = parts[1]
        if "." not in symbol:
            continue

        # only include today's flips
        if flip_date == brief_date:
            flips[symbol] = {"date": flip_date, "rrg": rrg}

    return flips
