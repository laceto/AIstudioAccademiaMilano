"""Sector sentiment loader from lacetohf/sector-analysis (HuggingFace dataset).

Adds live market context to the trading dashboard without touching the
price-bar / signal pipeline. Fails softly — callers handle ImportError and
empty results so the rest of the dashboard still works.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

_DATASET_ID = "lacetohf/sector-analysis"
_MAX_STALENESS_DAYS = 2


def load_sector_context(max_rows: int = 20) -> tuple[list[dict[str, Any]], bool, str]:
    """Load the latest sector sentiment snapshot from HuggingFace.

    Returns:
        rows        — list of dicts (one row per sector entry)
        is_fresh    — False if the latest date is older than _MAX_STALENESS_DAYS
        latest_date — ISO date string of the most recent record, or ""
    """
    from datasets import load_dataset  # ImportError surfaced to caller

    ds = load_dataset(_DATASET_ID, split="train")
    if len(ds) == 0:
        return [], False, ""

    df = ds.to_pandas()

    date_col = next(
        (c for c in ["date", "Date", "timestamp", "analysis_date"] if c in df.columns),
        None,
    )

    if date_col is None:
        return df.head(max_rows).to_dict("records"), True, ""

    df[date_col] = df[date_col].astype(str).str[:10]
    latest_date = df[date_col].max()

    try:
        parsed = date.fromisoformat(latest_date)
        is_fresh = (date.today() - parsed).days <= _MAX_STALENESS_DAYS
    except (ValueError, TypeError):
        is_fresh = True

    latest_rows = df[df[date_col] == latest_date].head(max_rows).to_dict("records")
    return latest_rows, is_fresh, latest_date
