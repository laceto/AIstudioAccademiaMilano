"""WP-A: the front half of the studio pipeline (Stacy, Gianni) and the graph's failure routing.

Everything runs against a fake LLM: no network, no git, no repo writes.
"""

import json

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from langgraph.graph import END

from gateway.studio_runner import load_pipeline


@pytest.fixture(scope="module")
def pipe():
    return load_pipeline()


class FakeLLM:
    """Stands in for get_llm(): records the prompt, answers with canned text (or raises)."""

    def __init__(self, reply):
        self.reply = reply
        self.prompts: list[str] = []

    def runnable(self):
        def _call(prompt_value):
            self.prompts.append(prompt_value.to_string())
            if isinstance(self.reply, Exception):
                raise self.reply
            text = self.reply if isinstance(self.reply, str) else json.dumps(self.reply)
            return AIMessage(content=text)

        return RunnableLambda(_call)


def _use(monkeypatch, pipe, reply) -> FakeLLM:
    fake = FakeLLM(reply)
    monkeypatch.setattr(pipe.nodes, "get_llm", lambda *a, **k: fake.runnable())
    return fake


GOOD_SPEC = {
    "technical_spec": {"overview": "A page", "components": ["hero", "footer"]},
    "stack": ["HTML", "Tailwind"],
    "deployment_target": "Vercel",
    "estimated_hours": 2.5,
    "blockers": [],
}


# ── Stacy: catalogue is the single source of truth ───────────────────────────


def test_every_catalogue_product_is_in_the_prompt(monkeypatch, pipe):
    fake = _use(monkeypatch, pipe, {"intent": "chatbot_app", "product_type": "chatbot_app"})
    pipe.nodes.stacy_classify({"request": "una chat"}, {})
    prompt = fake.prompts[0]
    products = [k for k, v in pipe.state.PRICING_TABLE.items() if v is not None]
    assert len(products) >= 17
    for key in products:
        assert key in prompt, key
    for key in ("algo_trading", "mind_dashboard_journal", "micro_syllabus_flashcards",
                "family_archivist", "mediterranean_meal_planner", "niccolo_chronicles"):
        assert key in prompt


def test_intent_enum_is_built_from_the_catalogue(pipe):
    helper = pipe.state.catalogue_products()
    assert "unknown_product" not in helper and "algo_trading" in helper
    enum = pipe.state.intent_enum()
    assert enum.endswith("other") and "niccolo_chronicles" in enum


def test_product_outside_the_table_becomes_unknown_product(monkeypatch, pipe):
    _use(monkeypatch, pipe, {"intent": "other", "product_type": "flying_car"})
    out = pipe.nodes.stacy_classify({"request": "x"}, {})
    assert out["product_type"] == "unknown_product"
    assert out["escalate_to_luigi"] is True and "flying_car" in out["escalation_reason"]
    assert not out.get("error")


def test_non_string_product_does_not_crash(monkeypatch, pipe):
    _use(monkeypatch, pipe, {"intent": "other", "product_type": ["a"]})
    out = pipe.nodes.stacy_classify({"request": "x"}, {})
    assert out["product_type"] == "unknown_product" and out["escalate_to_luigi"] is True


def test_known_product_is_priced_and_not_escalated(monkeypatch, pipe):
    _use(monkeypatch, pipe, {"intent": "algo_trading", "product_type": "algo_trading"})
    out = pipe.nodes.stacy_classify({"request": "bot"}, {})
    assert out["product_type"] == "algo_trading" and out["escalate_to_luigi"] is False


# ── Stacy / Gianni: failures follow the error pattern ────────────────────────


def test_stacy_failure_sets_error_and_finished(monkeypatch, pipe):
    _use(monkeypatch, pipe, RuntimeError("boom"))
    out = pipe.nodes.stacy_classify({"request": "x"}, {})
    assert out["error"] == "[Stacy] boom" and out["finished"] is True
    assert out["messages"][0].content.startswith("[Stacy]")


def test_stacy_unparseable_output_is_an_error(monkeypatch, pipe):
    _use(monkeypatch, pipe, "not json at all")
    out = pipe.nodes.stacy_classify({"request": "x"}, {})
    assert out["finished"] is True and out["error"].startswith("[Stacy]")


def test_gianni_happy_path_keeps_blockers(monkeypatch, pipe):
    spec = {**GOOD_SPEC, "blockers": ["needs API key"]}
    _use(monkeypatch, pipe, spec)
    out = pipe.nodes.gianni_scope({"request": "x", "intent": "i", "product_type": "chatbot_app"}, {})
    assert not out.get("error")
    assert out["blockers"] == ["needs API key"]
    assert out["stack"] == ["HTML", "Tailwind"] and out["estimated_hours"] == 2.5
    assert out["technical_spec"]["components"] == ["hero", "footer"]


@pytest.mark.parametrize("mutate", [
    lambda d: d.pop("technical_spec"),
    lambda d: d.update(technical_spec={}),
    lambda d: d["technical_spec"].pop("overview"),
    lambda d: d["technical_spec"].pop("components"),
    lambda d: d["technical_spec"].update(components="hero"),
    lambda d: d.pop("stack"),
    lambda d: d.update(stack="Python"),
    lambda d: d.pop("deployment_target"),
    lambda d: d.update(deployment_target=""),
    lambda d: d.pop("estimated_hours"),
    lambda d: d.update(estimated_hours="two"),
    lambda d: d.update(estimated_hours=True),
    lambda d: d.pop("blockers"),
    lambda d: d.update(blockers="none"),
])
def test_gianni_malformed_output_is_an_error_not_an_empty_spec(monkeypatch, pipe, mutate):
    spec = json.loads(json.dumps(GOOD_SPEC))
    mutate(spec)
    _use(monkeypatch, pipe, spec)
    out = pipe.nodes.gianni_scope({"request": "x"}, {})
    assert out["error"].startswith("[Gianni]") and out["finished"] is True
    assert "technical_spec" not in out


def test_gianni_llm_exception_follows_error_pattern(monkeypatch, pipe):
    _use(monkeypatch, pipe, RuntimeError("down"))
    out = pipe.nodes.gianni_scope({"request": "x"}, {})
    assert out["error"] == "[Gianni] down" and out["finished"] is True


# ── graph routing ────────────────────────────────────────────────────────────


def test_error_after_stacy_goes_to_end(pipe):
    r = pipe.graph.route_after_classify
    assert r({"error": "[Stacy] boom", "escalate_to_luigi": True}) == END
    assert r({"escalate_to_luigi": True}) == "luigi_escalate"
    assert r({}) == "gianni_scope"


def test_error_after_gianni_goes_to_end(pipe):
    r = pipe.graph.route_after_gianni
    assert r({"error": "[Gianni] x"}) == END
    assert r({}) == "chiara_implement"


def test_error_after_chiara_goes_to_end_else_fans_out(pipe):
    r = pipe.graph.route_after_chiara
    assert r({"error": "[Chiara] x"}) == END
    sends = r({"request": "x"})
    assert {s.node for s in sends} == {"technical_auditor", "compliance_agent", "reputation_guardian"}


def test_marco_to_francesca_only_with_a_price(pipe):
    r = pipe.graph.route_after_marco
    assert r({"product_price": "9.90"}) == "francesca_deliver"
    assert r({"product_price": "0.00"}) == "francesca_deliver"  # free approval is a price
    assert r({"escalate_to_luigi": True, "escalation_reason": "Marco blocked"}) == END
    assert r({"product_price": "9.90", "error": "boom"}) == END
    assert r({"product_type": "unknown_product"}) == END


def test_route_after_qa_is_unchanged(pipe):
    r = pipe.graph.route_after_qa
    assert r({"qa_passed": True}) == "marco_invoice"
    assert r({"qa_iteration": 3}) == END
    assert r({"qa_iteration": 1}) == "chiara_implement"


# ── end to end with a scripted LLM ───────────────────────────────────────────


def _scripted(pipe, monkeypatch, per_node):
    """Fake LLM that answers by looking at who is asking (system prompt wording)."""
    def _call(pv):
        text = pv.to_string() if hasattr(pv, "to_string") else "\n".join(m.content for m in pv)
        for marker, reply in per_node.items():
            if marker in text:
                if isinstance(reply, Exception):
                    raise reply
                return AIMessage(content=reply if isinstance(reply, str) else json.dumps(reply))
        raise AssertionError("unexpected prompt: " + text[:80])

    monkeypatch.setattr(pipe.nodes, "get_llm", lambda *a, **k: RunnableLambda(_call))


def test_graph_stops_at_end_when_gianni_fails(monkeypatch, pipe):
    _scripted(pipe, monkeypatch, {
        "You are Stacy, Input": {"intent": "chatbot_app", "product_type": "chatbot_app"},
        "You are Gianni": "garbage",
    })
    graph = pipe.graph.build_studio_graph(deliver=lambda s: {"finished": True})
    steps, final = pipe.graph.run_pipeline("una chat", graph=graph, auto_approve=False)
    assert final["error"].startswith("[Gianni]")
    assert not final.get("deliverable_content")
    assert not any(s["content"].startswith("[Chiara]") for s in steps)


def test_cli_run_with_unknown_product_stops_before_francesca(monkeypatch, pipe):
    """No approved_price, unknown product: Luigi (auto) approves, Marco blocks, nothing is delivered."""
    delivered = []
    _scripted(pipe, monkeypatch, {
        "You are Stacy, Input": {"intent": "other", "product_type": "flying_car"},
        "You are Gianni": GOOD_SPEC,
        "Output format": "SKILLS: python\nFILE: a.py\n\nprint(1)",
        "Technical Auditor": {"risk_score": 1, "findings": []},
        "Compliance Agent": {"risk_score": 1, "findings": []},
        "Reputation Guardian": {"risk_score": 1, "findings": []},
        "Stacy in QA mode": {"qa_passed": True, "issues": []},
    })
    graph = pipe.graph.build_studio_graph(deliver=lambda s: delivered.append(1) or {"finished": True})
    steps, final = pipe.graph.run_pipeline("una macchina volante", graph=graph, auto_approve=True)
    assert delivered == []

    assert any(s["content"].startswith("[Marco] BLOCKED") for s in steps)
    assert not final.get("delivery_result")
