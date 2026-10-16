"""State for the v2 pipeline: v1's StudioState plus what the added roles produce."""
from __future__ import annotations

import operator
from typing import Annotated, List, Optional

from studio_pipeline.state import PRICING_TABLE, StudioState  # v1 is loaded first (gateway.studio_runner)


class StudioStateV2(StudioState):
    # Lorenzo: result of the prompt-injection scan of the raw request
    injection_flag: Optional[dict]
    # Devil's Advocate (price tier) and Financial Controller (margin), both before Chiara builds
    price_challenge: Optional[dict]
    finance_check: Optional[dict]
    # Roles that advise Luigi without blocking (Core Architect, IT Staff, price/margin notes, failed reviewers).
    # Each note: {"agent": str, "note": str, ...}. Accumulated, never acted on by the pipeline.
    advisory_notes: Annotated[List[dict], operator.add]
    # Valentina's announcement draft. A draft only: nothing publishes it.
    draft_post: Optional[str]


__all__ = ["PRICING_TABLE", "StudioStateV2"]
