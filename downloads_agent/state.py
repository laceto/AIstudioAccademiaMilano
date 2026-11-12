from __future__ import annotations

from typing import Annotated, List, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class DownloadsState(TypedDict, total=False):
    plan: List[dict]      # {"src", "category"}
    skipped: List[dict]   # {"name", "reason"}
    decision: str         # "approved" | "rejected" | "" (set externally via update_state)
    moved: List[dict]     # {"src", "dst"}
    messages: Annotated[List[BaseMessage], add_messages]
