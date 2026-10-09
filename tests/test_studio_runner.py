"""gateway/studio_runner.py — one gateway job through the whole LangGraph pipeline.

The LLM is replaced by a scripted fake keyed on each agent's system prompt, so the
real graph (routing, parallel risk fan-out, QA retry loop, Marco's invoice) runs
end to end without network, git, mail or disk writes.
"""

import json
import subprocess

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from gateway import studio_runner as sr


@pytest.fixture(scope="module")
def pipe():
    return sr.load_pipeline()


def _text(value) -> str:
    if hasattr(value, "to_string"):
        return value.to_string()
    return "\n".join(getattr(m, "content", str(m)) for m in value)


class Script:
    """Scripted answers per agent. Override attributes to steer a scenario."""

    def __init__(self):
        self.product = "unknown_product"
        self.risk = 1
        self.qa_passes = True
        self.code = "print('eta')"
        self.filename = "age_api.py"
        self.seen_providers = []
        self.explode = None

    def answer(self, value) -> AIMessage:
        if self.explode:
            raise RuntimeError(self.explode)
        text = _text(value)
        if '"risk_score"' in text:
            return AIMessage(content=json.dumps({"risk_score": self.risk, "findings": []}))
        if "Stacy in QA mode" in text:
            return AIMessage(content=json.dumps({
                "qa_passed": self.qa_passes, "checks": {}, "issues": [] if self.qa_passes else ["manca il disclaimer"],
            }))
        if "Stacy, Input-Orchestrator" in text:
            return AIMessage(content=json.dumps({
                "intent": "other", "product_type": self.product, "dependencies_ok": True, "input_type": "text",
            }))
        if "Gianni, Request-Analyzer" in text:
            return AIMessage(content=json.dumps({
                "technical_spec": {"overview": "x", "components": [], "api_integrations": [], "data_model": ""},
                "stack": ["Python"], "deployment_target": "local", "estimated_hours": 1.0, "blockers": [],
            }))
        if "Extract page metadata" in text:  # Chiara's landing-page template strategy
            return AIMessage(content=json.dumps({"TITLE": "Il mio sito", "DESCRIPTION": "d", "SITE_NAME": "s", "LANG": "it"}))
        if "Extract invoice fields" in text:  # Chiara's invoice strategy
            return AIMessage(content=json.dumps({
                "invoice_number": "INV-9", "client_name": "Amico", "amount": 50.0, "service": "Consulenza", "date": "2026-10-09",
            }))
        if "Chiara, Product-Generator" in text:
            return AIMessage(content=f"SKILLS: python\nFILE: {self.filename}\n\n{self.code}")
        raise AssertionError(f"unscripted prompt: {text[:80]!r}")


@pytest.fixture
def script(pipe, monkeypatch):
    s = Script()
    fake = RunnableLambda(s.answer)

    def fake_get_llm(provider, tier="fast", **kwargs):
        s.seen_providers.append(provider)
        return fake

    monkeypatch.setattr(pipe.nodes, "get_llm", fake_get_llm)
    # Francesca must never run: any git/mail call is a bug.
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("subprocess.run called by the headless pipeline"))
    return s


def _job(price=5.5, text="Api service to get current age", job_id="0baa44db93"):
    return {"job_id": job_id, "text": text, "price": price, "status": "running", "channel": "telegram"}


# ── a clean run ──────────────────────────────────────────────────────────────


def test_an_unknown_product_runs_at_the_approved_price(script):
    res = sr.run_job(_job(price=5.5))
    assert res.ok, res.error
    assert res.filename == "age_api.py" and res.content == "print('eta')"
    assert res.price == 5.5 and res.invoice_id and res.product_type == "unknown_product"
    assert res.qa_passed is True and res.risk_score == 1.0 and res.high_risk is False
    assert any("[Marco] Invoice" in s for s in res.steps)
    assert any("[Francesca] READY" in s for s in res.steps)


def test_a_free_job_runs_too(script):
    res = sr.run_job(_job(price=0.0))
    assert res.ok, res.error
    assert res.price == 0.0


def test_the_openai_provider_is_used_by_default(script):
    sr.run_job(_job())
    assert set(script.seen_providers) == {"openai"}


def test_the_provider_can_be_chosen(script):
    sr.run_job(_job(), provider="anthropic")
    assert set(script.seen_providers) == {"anthropic"}


def test_a_catalogue_product_is_priced_by_luigi_not_the_table(script):
    script.product = "static_landing_page"
    res = sr.run_job(_job(price=12.0, text="voglio un sito"))
    assert res.ok, res.error
    assert res.price == 12.0 and res.filename == "index.html"  # the table says 9.90; Luigi said 12
    assert "Il mio sito" in res.content  # the HTML template was filled in


# ── nothing leaves the container ─────────────────────────────────────────────


def test_no_files_are_written_into_the_repo(script, pipe):
    before = sorted(p.name for p in (sr.ROOT / "deliverables").iterdir())
    audit_before = sorted(p.name for p in (sr.ROOT / "process" / "audit").iterdir())
    assert sr.run_job(_job()).ok
    assert sorted(p.name for p in (sr.ROOT / "deliverables").iterdir()) == before
    assert sorted(p.name for p in (sr.ROOT / "process" / "audit").iterdir()) == audit_before


def test_runs_do_not_share_state(script):
    first = sr.run_job(_job(job_id="aaa", text="uno"))
    script.code = "print('due')"
    second = sr.run_job(_job(job_id="bbb", text="due"))
    assert first.content == "print('eta')" and second.content == "print('due')"
    assert first.invoice_id != second.invoice_id


# ── the human stays in charge of risk ────────────────────────────────────────


def test_a_high_risk_result_still_comes_back_but_is_flagged(script):
    script.risk = 5
    res = sr.run_job(_job())
    assert res.ok, res.error  # Luigi's approval covers product and price; he reviews the output next
    assert res.high_risk is True and res.risk_score == 5.0


# ── failure modes ────────────────────────────────────────────────────────────


def test_qa_that_never_passes_is_a_failure_with_its_reason(script):
    script.qa_passes = False
    res = sr.run_job(_job())
    assert not res.ok and "QA" in res.error and "disclaimer" in res.error
    assert res.content is None  # nothing half-finished is handed out


def test_an_llm_error_is_a_failure_and_never_leaks_a_key(script):
    fake_key = "sk-" + "proj-ABCDEF1234567890"  # built at runtime so the repo's secret scan has nothing to flag
    script.explode = f"Incorrect API key provided: {fake_key}. You can find your key"
    res = sr.run_job(_job())
    assert not res.ok
    assert fake_key not in json.dumps(res.to_dict())


def test_an_empty_deliverable_is_a_failure(script):
    script.code = "   "
    res = sr.run_job(_job())
    assert not res.ok and res.content is None


def test_an_oversized_deliverable_is_refused(script):
    script.code = "x" * (sr.MAX_DELIVERABLE_BYTES + 1)
    res = sr.run_job(_job())
    assert not res.ok and "troppo grande" in res.error


@pytest.mark.parametrize("price", [None, -1, "abc", float("nan")])
def test_a_job_without_a_sane_approved_price_is_not_run(script, price):
    res = sr.run_job(_job(price=price))
    assert not res.ok and "prezzo" in res.error.lower()
    assert script.seen_providers == []  # no LLM money spent


# ── what is stored ───────────────────────────────────────────────────────────


def test_the_result_is_json_ready_for_firestore(script):
    d = sr.run_job(_job()).to_dict()
    json.dumps(d)
    assert {"ok", "filename", "content", "price", "qa_passed", "risk_score", "steps", "invoice_id"} <= set(d)


def test_scrub_hides_keys_and_tokens():
    out = sr.scrub("key " + "sk-" + "proj-AAAA1111 and bot123456:ABC-def_GHI and Bearer abc.def.ghi")
    assert "AAAA1111" not in out and "ABC-def_GHI" not in out and "abc.def.ghi" not in out


# ── every Chiara strategy actually runs (two of them had broken prompts) ─────
# "{...}" in a ChatPromptTemplate is a variable: unescaped JSON examples made the
# invoice and landing-page strategies fail on every request.


@pytest.mark.parametrize(
    "product,filename,marker",
    [
        ("invoice_pdf", "generate_invoice.py", "InvoiceTemplate"),
        ("static_landing_page", "index.html", "Il mio sito"),
        ("chatbot_app", "app.py", "streamlit"),
        ("unknown_product", "age_api.py", "print('eta')"),
    ],
)
def test_each_chiara_strategy_delivers(script, product, filename, marker):
    script.product = product
    res = sr.run_job(_job(price=9.9, text="richiesta di prova"))
    assert res.ok, res.error
    assert res.filename == filename and marker in res.content
    assert res.price == 9.9


def test_no_prompt_has_stray_template_variables(pipe):
    import inspect
    import re

    from langchain_core.prompts import ChatPromptTemplate

    allowed = {"request", "intent", "product_type", "spec", "stack", "content"}
    src = inspect.getsource(pipe.nodes)
    found = 0
    for block in re.findall(r"ChatPromptTemplate\.from_messages\(\[(.*?)\]\)", src, re.S):
        found += 1
        variables = set(ChatPromptTemplate.from_messages(eval("[" + block + "]")).input_variables)
        assert variables <= allowed, f"stray variables {variables - allowed}"
    assert found >= 9  # the check really looked at the prompts
