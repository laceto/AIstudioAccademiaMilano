from __future__ import annotations

import json
import os
import time
from pathlib import Path

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig

from .categories import IGNORED_NAMES, PARTIAL_EXTS, classify
from .extract import READABLE, extract_text
from .report import render_report
from .state import DownloadsState
from .summarize import DEFAULT_MODEL, ollama_chat, summarize

# The folder the agent looks after: <repo>/data/Download (not the Windows ~/Downloads).
DEFAULT_ROOT = Path(__file__).resolve().parent.parent / "data" / "Download"
DEFAULT_MIN_AGE_MIN = 10


def default_state_dir() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "downloads_agent"


def _cfg(config: RunnableConfig) -> dict:
    return (config or {}).get("configurable", {})


def root_of(config: RunnableConfig) -> Path:
    return Path(_cfg(config).get("root") or DEFAULT_ROOT)


def state_dir_of(config: RunnableConfig) -> Path:
    return Path(_cfg(config).get("state_dir") or default_state_dir())


def plan_node(state: DownloadsState, config: RunnableConfig) -> dict:
    """Scan top-level files only; decide which would move. Touches nothing."""
    root = root_of(config)
    min_age = _cfg(config).get("min_age_minutes", DEFAULT_MIN_AGE_MIN) * 60
    plan, skipped = [], []
    for p in sorted(root.iterdir()):
        if not p.is_file() or p.name.lower() in IGNORED_NAMES:
            continue
        if p.suffix.lower() in PARTIAL_EXTS:
            skipped.append({"name": p.name, "reason": "download in progress"})
        elif time.time() - p.stat().st_mtime < min_age:
            skipped.append({"name": p.name, "reason": "modified recently"})
        elif (cat := classify(p.name)) is None:
            skipped.append({"name": p.name, "reason": "unknown type"})
        else:
            plan.append({"src": str(p), "category": cat})
    return {
        "plan": plan, "skipped": skipped, "decision": "", "moved": [],
        "messages": [AIMessage(content=f"[Planner] {len(plan)} to move, {len(skipped)} skipped")],
    }


def _load_cache(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def summarize_node(state: DownloadsState, config: RunnableConfig) -> dict:
    """Add a one-line 'summary' to each planned file. Off unless config summarize=True.

    Only readable documents are sent to the (local) model; everything else gets a type note.
    A model failure never breaks the plan.
    """
    cfg = _cfg(config)
    plan = state.get("plan") or []
    if not cfg.get("summarize") or not plan:
        return {}
    model = cfg.get("model") or DEFAULT_MODEL
    chat = cfg.get("chat") or ollama_chat(model)
    limit = cfg.get("max_summaries")
    sd = state_dir_of(config)
    sd.mkdir(parents=True, exist_ok=True)
    cache_file = sd / "summary_cache.json"
    cache = _load_cache(cache_file)
    calls, down, out = 0, False, []
    for item in plan:
        item = dict(item)
        src = Path(item["src"])
        if src.suffix.lower() not in READABLE:
            item["summary"] = f"{item['category']}: content not read"
            out.append(item)
            continue
        st = src.stat()
        key = f"{src}|{st.st_size}|{st.st_mtime_ns}|{model}"
        if key in cache:
            item["summary"] = cache[key]
        else:
            text, note = extract_text(src)
            if note:
                item["summary"] = f"({note})"
            elif down:
                item["summary"] = "(summary skipped: Ollama not reachable)"
            elif limit is not None and calls >= limit:
                item["summary"] = "(summary skipped: limit reached)"
            else:
                calls += 1
                try:
                    item["summary"] = cache[key] = summarize(src.name, text, chat)
                except ConnectionError:
                    down = True
                    item["summary"] = "(summary skipped: Ollama not reachable)"
                except Exception as e:
                    item["summary"] = f"(summary unavailable: {type(e).__name__})"
        out.append(item)
    cache_file.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    (sd / "summary.html").write_text(
        render_report(out, state.get("skipped", []), model), encoding="utf-8")
    return {"plan": out, "messages": [AIMessage(content=f"[Summarizer] {calls} model call(s)")]}


def route_after_plan(state: DownloadsState) -> str:
    return "execute" if state.get("plan") else "__end__"


def _free_name(dst: Path) -> Path:
    if not dst.exists():
        return dst
    n = 1
    while (cand := dst.with_name(f"{dst.stem} ({n}){dst.suffix}")).exists():
        n += 1
    return cand


def execute_node(state: DownloadsState, config: RunnableConfig) -> dict:
    """Runs only after the human interrupt; moves nothing unless decision == approved."""
    if state.get("decision") != "approved":
        return {"messages": [AIMessage(content="[Executor] not approved, nothing moved")]}
    root = root_of(config)
    moved = []
    for item in state["plan"]:
        src = Path(item["src"])
        if not src.is_file():  # vanished since planning
            continue
        dest_dir = root / item["category"]
        dest_dir.mkdir(exist_ok=True)
        dst = _free_name(dest_dir / src.name)
        src.rename(dst)
        moved.append({"src": str(src), "dst": str(dst)})
    sd = state_dir_of(config)
    sd.mkdir(parents=True, exist_ok=True)
    with open(sd / "journal.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.time(), "moved": moved}) + "\n")
    return {"moved": moved, "messages": [AIMessage(content=f"[Executor] moved {len(moved)} files")]}
