"""State for the v2 pipeline: v1's StudioState plus what the added roles produce."""
from __future__ import annotations

import operator
from typing import Annotated, List, Optional, TypedDict, get_type_hints

from studio_pipeline.state import PRICING_TABLE, StudioState  # v1 is loaded first (gateway.studio_runner)


REPORTS_RESET = {"agent": "_reset"}


def accumulate_reports(old: Optional[List[dict]], new: Optional[List[dict]]) -> List[dict]:
    """Reducer for risk_reports. Parallel reviewers append, but v1's `operator.add` never forgets: after a QA
    retry the panel still held the rejected build's scores, so one old critical 5 sent every rebuild to Luigi
    again. A REPORTS_RESET in the update means "a new build starts here": keep only what follows it."""
    old, new = list(old or []), list(new or [])
    if REPORTS_RESET in new:
        return [r for r in new if r != REPORTS_RESET]
    return old + new


# v1's fields, except risk_reports: LangGraph refuses a subclass that redeclares a channel with another
# reducer, so v2 is built from v1's field list instead of inheriting from it.
_V1_FIELDS = {k: v for k, v in get_type_hints(StudioState, include_extras=True).items() if k != "risk_reports"}

StudioStateV2 = TypedDict("StudioStateV2", {
    **_V1_FIELDS,
    # Same field as v1, but a rebuild starts a fresh panel (see accumulate_reports).
    "risk_reports": Annotated[List[dict], accumulate_reports],
    # Lorenzo: result of the prompt-injection scan of the raw request
    "injection_flag": Optional[dict],
    # Devil's Advocate (price tier) and Financial Controller (margin), both before Chiara builds
    "price_challenge": Optional[dict],
    "finance_check": Optional[dict],
    # Roles that advise Luigi without blocking (Core Architect, IT Staff, price/margin notes, failed reviewers).
    # Each note: {"agent": str, "note": str, ...}. Accumulated, never acted on by the pipeline.
    "advisory_notes": Annotated[List[dict], operator.add],
    # Valentina's announcement draft. A draft only: nothing publishes it.
    "draft_post": Optional[str],
})


__all__ = ["PRICING_TABLE", "StudioStateV2"]
