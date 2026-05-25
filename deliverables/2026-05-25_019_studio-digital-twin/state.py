"""
Studio Digital Twin — state definition.
TwinState flows through the simulation graph unchanged except for
department_impacts, which accumulates via operator.add as parallel
department nodes complete.
"""
from __future__ import annotations

import operator
from typing import Annotated, List, Optional, TypedDict


class TwinState(TypedDict):
    event: dict                                              # injected external shock
    studio_baseline: dict                                    # live state loaded from config
    department_impacts: Annotated[List[dict], operator.add]  # parallel fan-in accumulator
    simulation_report: Optional[dict]                        # final synthesis output
    finished: bool
