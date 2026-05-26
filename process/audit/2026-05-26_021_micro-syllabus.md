# Audit Log — Request 021

```yaml
request_id: "021"
date: "2026-05-26"
time: "12:30"
input_type: text
raw_input: |
  Build an AI-Powered "Micro-Syllabus" & Flashcard Generator. Take a
  complex learning goal and a daily time budget, output a folder
  containing syllabus.md (7-day roadmap with core concept, drill, why
  it matters) and flashcards.csv (exactly 10 conceptual cards, strict
  CSV for Anki import). User asked us to "Try OpenAI" this time.
intent: micro_syllabus_flashcards
product_type: micro_syllabus_flashcards

agents_invoked:
  - name: Stacy
    role: intent_classifier
    duration_sec: 2
    status: success
    notes: >
      Classified as new product type `micro_syllabus_flashcards`.
      Closest neighbours: strategic_report (one-shot generation),
      chatbot_app (multi-file deliverable). Priced new key at €14.90
      (two-output deliverable, learning vertical, calendar_integration
      tier).
  - name: Gianni
    role: technical_scoping
    duration_sec: 4
    status: success
    notes: >
      Single OpenAI call (json_object mode) returns one payload for both
      files — cheaper and simpler than two separate calls, and lets the
      flashcards stay grounded in the syllabus content. Provider switch
      to OpenAI (was Anthropic for request 020) per user's "Try OpenAI"
      note — diversifies the studio's product line across providers.
      Renderer owns both output formats so future model swaps cannot
      drift the layout. CSV uses Python's csv module with QUOTE_ALL
      for RFC 4180 compliance, safe against quotes/commas in card text.
  - name: Chiara
    role: product_generator
    duration_sec: 75
    status: success
    notes: >
      5 source files: micro_syllabus.py (CLI with --dry-run), prompts.py
      (system prompt + JSON contract), renderers.py (validator +
      Markdown/CSV renderers), requirements.txt (openai only), README.md
      with Anki import steps. Sample worked example for Docker / 15 min
      in sample/understand-the-basics-of-docker/.
  - name: Stacy
    role: qa_agent
    duration_sec: 12
    status: success
    notes: >
      Dry-run end-to-end produces valid Markdown + CSV. Validator
      negative tests pass: rejects 6-day syllabi, broken day numbering,
      9-card decks, empty card fields, zero minutes, missing goal.
      CSV round-trip verified: embedded " and , in card text survive
      csv.reader. Bug caught & fixed during QA: validator was checking
      day field as string (it's an int) — fixed by splitting the
      key-check loop.
  - name: Marco
    role: transaction_manager
    duration_sec: 4
    status: success
    notes: >
      Added pricing key `micro_syllabus_flashcards` at €14.90 in both
      config/global_settings.json and CLAUDE.md. No `unknown_product:
      null` — Luigi approval not required.
  - name: Francesca
    role: delivery_agent
    duration_sec: 12
    status: pending_push
    notes: >
      Branch `claude/micro-syllabus-flashcards` off updated main per
      CLAUDE.md "fresh branch per feature" rule. Commit, push, PR,
      squash-merge per standing auto-merge rule.

skills_used:
  - openai_chat_completions_json_mode
  - json_schema_contract_for_llm_output
  - dryrun_offline_stub_pattern
  - rfc4180_csv_emission
  - anki_csv_import_format
  - validator_negative_testing

mcp_tools_used:
  - mcp__github__create_pull_request
  - mcp__github__merge_pull_request

hooks_fired:
  - post_delivery_audit_log
  - learning_loop_pricing_sync

qa_result: pass
qa_notes: >
  Live LLM call not exercised in this environment (no OPENAI_API_KEY);
  the contract is documented in prompts.py and enforced by
  renderers.validate(). Sample output was generated through the real
  render_syllabus_md / render_flashcards_csv with a hand-crafted
  payload, so the showcased sample matches what the script produces
  byte-for-byte.

learning_flags:
  new_skills:
    - openai_chat_completions_json_mode
    - rfc4180_csv_emission_with_QUOTE_ALL
  new_pricing:
    micro_syllabus_flashcards: "€14.90"
  new_mcp: []
  risk_score: 1

deliverable_path: deliverables/2026-05-26_021_micro-syllabus/
```

## What was built

A CLI that converts a learning goal + daily time budget into a 7-day
micro-syllabus (`syllabus.md`) plus a 10-card Anki-ready deck
(`flashcards.csv`). Single OpenAI call (json_object mode), strict schema
validation, deterministic renderers.

## Why this design

1. **One call, two files** — the flashcards stay grounded in the
   syllabus content because they're generated in the same model turn
   with the explicit constraint "answerable from the syllabus only".
   Two separate calls would risk drift.
2. **JSON contract, not "write me CSV"** — letting the LLM produce CSV
   directly is a footgun (quote-escaping, locale separators). Renderer
   uses Python's `csv` module with `QUOTE_ALL`, RFC 4180 compliant.
3. **Provider diversity** — request 020 used Anthropic; this one uses
   OpenAI. The studio now has working reference implementations against
   both major providers, both using the same JSON-contract pattern.

## Follow-ups (not in scope)

- Generate `apkg` (Anki binary package) instead of CSV — needs the
  `genanki` library; CSV is universal and "good enough" for v1.
- "Continue" mode: feed the output back in to generate days 8-14,
  building a 4-week curriculum.
- Streamlit UI: two text inputs and a "Download .zip" button on top of
  the existing `micro_syllabus` module.
```
