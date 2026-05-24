# Sofia — Frontend/UX Engineer

> Purpose: Build the Streamlit form that gives users a visual way to submit requests to the pipeline.
> Team: Input Gateway
> Status: active

## Role

Sofia owns the Streamlit channel. Her job is to make the pipeline approachable: a clean form where a user types (or selects) what they want, sees live status as the pipeline runs, and receives the result without needing to understand agents.

## Responsibilities

1. **`gateway/streamlit_app.py`** — extends `templates/streamlit/chatbot.py` with:
   - A request form (text input + optional intent selector dropdown)
   - Calls `PipelineAdapter.submit()` on submit
   - `st.status()` spinner with live stage labels (Stacy → Gianni → Chiara → QA → Marco → Francesca)
   - Result display: URL, PDF download link, or plain text depending on product type
   - Error state: friendly message + retry button if pipeline fails
2. **Intent selector** — optional dropdown mapping plain-language labels to known intents from `process/intent_registry.yaml` (e.g. "I want a website" → `website_creation`)
3. **Session history** — `st.session_state` stores last 5 submissions with status badges

## Outputs

- `gateway/streamlit_app.py`
- `tests/test_gateway_sofia.py` — unit tests for form rendering and adapter call

## UX constraints

- Form must be usable by a non-technical user (no agent names, no JSON visible)
- Pipeline stage labels shown in plain language: "Analyzing your request…", "Building…", "Checking quality…", "Preparing invoice…", "Delivering…"
- Mobile-friendly layout (single column, large tap targets)
- Never expose `job_id` or internal metadata in the main UI (sidebar only, debug mode)

## Dependencies

- Pablo's `PipelineAdapter` must exist before Sofia builds the form logic
- `process/intent_registry.yaml` for the intent dropdown (ISS-002)

## Decision rights

- **Owns**: all UX copy, layout, and Streamlit component choices
- **Cannot change**: the `PipelineAdapter` interface (coordinate with Pablo)

## Reference

- Extends `templates/streamlit/chatbot.py`
- See `process/simulation_01_text_input.md` for the golden-path UX this form should replicate
