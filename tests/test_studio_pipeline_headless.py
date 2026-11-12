"""The studio pipeline, as the gateway needs it.

Luigi's approval (and the price he chose) has to survive the pipeline's own
re-classification, and Francesca (git push, Gmail, repo writes) has to be
replaceable. Both changes must leave the pipeline's normal behaviour intact.
"""

import inspect

import pytest
from langchain_core.messages import AIMessage

from gateway.studio_runner import load_pipeline


@pytest.fixture(scope="module")
def pipe():
    return load_pipeline()


# ── Marco honours the price Luigi approved ───────────────────────────────────


def _state(**over):
    base = {"product_type": "unknown_product", "user_name": "Amico"}
    base.update(over)
    return base


def test_marco_uses_the_approved_price_for_an_unknown_product(pipe):
    out = pipe.nodes.marco_invoice(_state(approved_price="5.50"))
    assert out["invoice"]["price_eur"] == 5.5 and out["product_price"] == "5.50"
    assert not out.get("escalate_to_luigi")


def test_a_free_approval_is_not_mistaken_for_no_price(pipe):
    out = pipe.nodes.marco_invoice(_state(approved_price="0.00"))
    assert out["invoice"]["price_eur"] == 0.0 and not out.get("escalate_to_luigi")


def test_the_approved_price_beats_the_catalogue(pipe):
    out = pipe.nodes.marco_invoice(_state(product_type="static_landing_page", approved_price="12.00"))
    assert out["invoice"]["price_eur"] == 12.0


def test_without_an_approved_price_marco_behaves_as_before(pipe):
    blocked = pipe.nodes.marco_invoice(_state())
    assert blocked["escalate_to_luigi"] is True and "BLOCKED" in blocked["messages"][0].content
    priced = pipe.nodes.marco_invoice(_state(product_type="static_landing_page"))
    assert priced["invoice"]["price_eur"] == 9.9


def test_state_declares_the_new_field(pipe):
    assert "approved_price" in pipe.state.StudioState.__annotations__


# ── the delivery step can be replaced; the default is unchanged ──────────────


def test_build_studio_graph_defaults_are_unchanged(pipe):
    sig = inspect.signature(pipe.graph.build_studio_graph)
    assert sig.parameters["deliver"].default is pipe.nodes.francesca_deliver
    assert pipe.graph.studio_graph is not None


def test_run_pipeline_accepts_a_graph_and_extra_state(pipe):
    class StubGraph:
        def __init__(self):
            self.initial = None

        def stream(self, initial, config=None, stream_mode=None):
            self.initial = initial
            yield {"messages": [AIMessage(content="[Stub] hi")], "finished": True}

        def update_state(self, *a, **k):
            raise AssertionError("no resume expected for a finished run")

    stub = StubGraph()
    steps, final = pipe.graph.run_pipeline(
        "voglio un sito", user_name="Amico", graph=stub,
        extra_state={"approved_price": "5.50", "luigi_decision": "approved"},
        config={"configurable": {"provider": "openai"}},
    )
    assert stub.initial["approved_price"] == "5.50" and stub.initial["luigi_decision"] == "approved"
    assert stub.initial["request"] == "voglio un sito" and stub.initial["user_name"] == "Amico"
    assert final["finished"] is True and steps[0]["content"] == "[Stub] hi"


def test_run_pipeline_keeps_its_old_signature_working(pipe):
    sig = inspect.signature(pipe.graph.run_pipeline)
    for old in ("request", "user_name", "user_email", "config", "auto_approve"):
        assert old in sig.parameters
    assert sig.parameters["graph"].default is None and sig.parameters["extra_state"].default is None


# ── an approved risk escalation continues to QA instead of starting over ─────


def test_approval_after_a_risk_escalation_goes_to_qa(pipe):
    from langgraph.graph import END

    route = pipe.graph.route_after_luigi
    assert route({"luigi_decision": "approved", "deliverable_content": "<html>"}) == "stacy_qa"
    assert route({"luigi_decision": "approved"}) == "gianni_scope"  # unknown product: scope it first
    assert route({"luigi_decision": "approved", "deliverable_content": "  "}) == "gianni_scope"
    assert route({"luigi_decision": "rejected", "deliverable_content": "<html>"}) == END
