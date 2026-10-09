"""Run the 6-agent studio pipeline for a gateway job, headlessly.

The pipeline lives in deliverables/2026-05-25_016_aistudio-langgraph: a LangGraph
StateGraph (Stacy -> Gianni -> Chiara -> risk panel -> QA -> Marco -> Francesca).
Francesca is built for a developer laptop: she writes into the repo, runs
`git commit` + `git push` and sends mail through a separate Gmail account. None
of that belongs in a Cloud Run container, so the gateway swaps her for
`headless_deliver`, which only hands the finished deliverable back.

Luigi has already approved the product and the price (gateway/admin.py), so the
job enters the pipeline with that decision and price in its state. He still
reviews the output before the customer gets it (gateway/pipeline_worker.py);
the risk panel's score travels with the result so he can see it.

This module loads the package (its folder name has hyphens, so it cannot be
imported normally), builds that variant of the graph and runs one job.
"""

from __future__ import annotations

import importlib.util
import math
import re
import sys
import types
from dataclasses import asdict, dataclass, field
from pathlib import Path
from types import SimpleNamespace

from gateway.admin import MAX_PRICE

ROOT = Path(__file__).resolve().parent.parent
PIPELINE_DIR = ROOT / "deliverables" / "2026-05-25_016_aistudio-langgraph"
_PKG = "studio_pipeline"

# A Firestore document holds 1 MiB; the deliverable shares it with the run trace.
MAX_DELIVERABLE_BYTES = 400_000
# The pipeline's own threshold (risk_aggregator passes when the average is below 3.5).
HIGH_RISK_SCORE = 3.5
_MAX_ERROR_CHARS = 300

_SECRET_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{4,}"), "sk-***"),
    (re.compile(r"bot\d+:[A-Za-z0-9_\-]+"), "bot<token>"),
    (re.compile(r"\b\d{6,}:[A-Za-z0-9_\-]{20,}\b"), "<token>"),
    (re.compile(r"Bearer\s+[A-Za-z0-9._\-]+"), "Bearer ***"),
]


def scrub(text: object) -> str:
    """Hide API keys and bot tokens that provider errors like to echo back, and cap the length."""
    out = str(text)
    for pattern, replacement in _SECRET_PATTERNS:
        out = pattern.sub(replacement, out)
    return out[:_MAX_ERROR_CHARS]


def load_pipeline() -> SimpleNamespace:
    """Import the pipeline package once and return its modules (state, llm_factory, nodes, graph)."""
    graph_name = f"{_PKG}.graph"
    if graph_name not in sys.modules:
        pkg = types.ModuleType(_PKG)
        pkg.__path__ = [str(PIPELINE_DIR)]
        pkg.__package__ = _PKG
        sys.modules[_PKG] = pkg
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))  # for config.brand and friends

        for name in ("state", "llm_factory", "nodes", "graph"):  # dependency order
            fqn = f"{_PKG}.{name}"
            spec = importlib.util.spec_from_file_location(
                fqn, PIPELINE_DIR / f"{name}.py", submodule_search_locations=[str(PIPELINE_DIR)]
            )
            module = importlib.util.module_from_spec(spec)
            module.__package__ = _PKG
            sys.modules[fqn] = module
            spec.loader.exec_module(module)

    return SimpleNamespace(
        state=sys.modules[f"{_PKG}.state"],
        llm_factory=sys.modules[f"{_PKG}.llm_factory"],
        nodes=sys.modules[f"{_PKG}.nodes"],
        graph=sys.modules[graph_name],
    )


def headless_deliver(state: dict) -> dict:
    """Francesca without the side effects: no repo writes, no git, no mail. Hands the result back."""
    from langchain_core.messages import AIMessage

    content = state.get("deliverable_content") or ""
    if not content.strip():
        return {
            "error": "empty deliverable - Chiara produced no content",
            "messages": [AIMessage(content="[Francesca] ERROR: empty deliverable, nothing to hand over")],
        }
    filename = Path(state.get("deliverable_path") or "").name or "deliverable.txt"
    return {
        "delivery_result": {"status": "ready", "deliverable_filename": filename},
        "finished": True,
        "messages": [AIMessage(content=f"[Francesca] READY (headless) | {filename}")],
    }


@dataclass
class RunResult:
    ok: bool
    error: str | None = None
    filename: str | None = None
    content: str | None = None
    product_type: str | None = None
    price: float | None = None
    invoice_id: str | None = None
    qa_passed: bool = False
    risk_score: float = 0.0
    high_risk: bool = False
    skills: list = field(default_factory=list)
    steps: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _failure(error: str, **extra) -> RunResult:
    return RunResult(ok=False, error=scrub(error), **extra)


def _valid_price(price) -> bool:
    return (
        isinstance(price, (int, float))
        and not isinstance(price, bool)
        and math.isfinite(price)
        and 0 <= price <= MAX_PRICE
    )


def run_job(job: dict, *, provider: str = "openai") -> RunResult:
    """Run one approved job through the pipeline. Never raises: failures come back as ok=False."""
    price = job.get("price")
    if not _valid_price(price):
        return _failure("Prezzo approvato mancante o non valido: la pipeline non e' stata avviata.")

    try:
        pipe = load_pipeline()
        # A fresh graph (and MemorySaver) per run, so nothing is shared between jobs.
        graph = pipe.graph.build_studio_graph(deliver=headless_deliver)
        steps, final = pipe.graph.run_pipeline(
            request=job["text"],
            user_name="Cliente",
            user_email=None,
            config={"configurable": {"provider": provider}},
            auto_approve=True,
            graph=graph,
            extra_state={"approved_price": f"{float(price):.2f}", "luigi_decision": "approved"},
        )
    except Exception as exc:
        return _failure(f"{type(exc).__name__}: {exc}")

    trace = [scrub(s["content"]) for s in steps]
    delivery = final.get("delivery_result") or {}
    content = final.get("deliverable_content") or ""
    risk = float(final.get("aggregate_risk_score") or 0.0)
    common = dict(
        product_type=final.get("product_type"),
        qa_passed=bool(final.get("qa_passed")),
        risk_score=risk,
        high_risk=risk >= HIGH_RISK_SCORE,
        steps=trace,
    )

    if not (final.get("finished") and delivery.get("status") == "ready" and content.strip()):
        qa = final.get("qa_result") or {}
        if qa and not final.get("qa_passed"):
            attempts = final.get("qa_iteration", 0)
            return _failure(f"QA non superata dopo {attempts} tentativi: {qa.get('issues')}", **common)
        return _failure(final.get("error") or "La pipeline e' terminata senza un risultato.", **common)

    size = len(content.encode("utf-8"))
    if size > MAX_DELIVERABLE_BYTES:
        return _failure(f"Il risultato e' troppo grande ({size} byte, massimo {MAX_DELIVERABLE_BYTES}).", **common)

    return RunResult(
        ok=True,
        filename=delivery.get("deliverable_filename") or "deliverable.txt",
        content=content,
        price=float(price),
        invoice_id=final.get("invoice_id"),
        skills=list(final.get("skills_used") or []),
        **common,
    )
