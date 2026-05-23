# Test Suite — AI Studio Accademia Milano

## Philosophy: Test-Driven Development

Tests are written **before** the implementation. Every test file in this folder is currently **RED** (failing) because the code it tests does not exist yet. This is intentional.

```
RED   →  write failing test
GREEN →  write minimum code to pass
REFACTOR → clean up, keep passing
```

---

## Current status

| File | Covers | Tests | Status |
|------|--------|-------|--------|
| `test_iss002_intent_registry.py` | ISS-002: `process/intent_registry.yaml` | 8 | 🔴 ALL FAILING |
| `test_iss003_credential_manager.py` | ISS-003: `scripts/credential_manager.py` | 10 | 🔴 ALL FAILING |
| `test_iss004_templates.py` | ISS-004: `templates/pdf/` + `templates/streamlit/` | 11 | 🔴 ALL FAILING |
| `test_iss005_tiered_thresholds.py` | ISS-005: tiered thresholds in `learning_loop.py` | 7 | 🔴 ALL FAILING |
| `test_iss006_source_citation.py` | ISS-006: `validate_advisory_output()` | 6 | 🔴 ALL FAILING |
| `test_iss007_provider_agnostic_chatbot.py` | ISS-007: provider-agnostic `ChatbotTemplate` | 9 | 🔴 ALL FAILING |

**Total: 51 failing tests. 0 passing. Target: 51 passing.**

---

## Run all tests

```bash
pip install pytest pyyaml fpdf2 streamlit openai anthropic groq
pytest tests/ -v
```

Expected output right now:
```
IMPORTERROR: No module named 'scripts.credential_manager'
IMPORTERROR: No module named 'templates.pdf.invoice_standard'
IMPORTERROR: No module named 'templates.streamlit.chatbot'
... and so on
```

## Run a single issue

```bash
pytest tests/test_iss002_intent_registry.py -v
pytest tests/test_iss003_credential_manager.py -v
pytest tests/test_iss004_templates.py -v
pytest tests/test_iss005_tiered_thresholds.py -v
pytest tests/test_iss006_source_citation.py -v
pytest tests/test_iss007_provider_agnostic_chatbot.py -v
```

## Implementation order (recommended)

1. **ISS-005** — tiered thresholds: one function in existing `learning_loop.py` — smallest change
2. **ISS-006** — source citation: one function in existing `learning_loop.py`
3. **ISS-002** — intent registry: one YAML file + Stacy reads it
4. **ISS-003** — credential manager: new `scripts/credential_manager.py`
5. **ISS-004** — invoice template: new `templates/pdf/invoice_standard.py`
6. **ISS-007** — chatbot template: new `templates/streamlit/chatbot.py` (depends on ISS-004 pattern)
