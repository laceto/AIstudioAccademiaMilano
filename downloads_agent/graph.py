from __future__ import annotations

import json
from pathlib import Path

from langgraph.graph import END, START, StateGraph

from .nodes import execute_node, plan_node, route_after_plan
from .state import DownloadsState


def build_graph(checkpointer):
    g = StateGraph(DownloadsState)
    g.add_node("plan", plan_node)
    g.add_node("execute", execute_node)
    g.add_edge(START, "plan")
    g.add_conditional_edges("plan", route_after_plan, {"execute": "execute", "__end__": END})
    g.add_edge("execute", END)
    return g.compile(checkpointer=checkpointer, interrupt_before=["execute"])


def undo_last_run(state_dir: str) -> int:
    """Reverse the last journal entry. Returns number of files restored."""
    jp = Path(state_dir) / "journal.jsonl"
    if not jp.exists():
        return 0
    lines = [l for l in jp.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not lines:
        return 0
    entry = json.loads(lines[-1])
    restored = 0
    for m in reversed(entry["moved"]):
        dst, src = Path(m["dst"]), Path(m["src"])
        if dst.is_file() and not src.exists():
            dst.rename(src)
            restored += 1
    jp.write_text("".join(l + "\n" for l in lines[:-1]), encoding="utf-8")
    return restored
