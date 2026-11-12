# 05 — What happens when a Telegram request arrives

Verified against the code on 2026-10-16: `gateway/api.py` (webhook), `gateway/worker.py` (classification),
`gateway/pipeline_adapter.py` (job creation). Steps E–G come from
`deliverables/2026-10-09_036_approval-pipeline-worker/README.md` and were not re-checked line by line.

## Status flow

```
queued -> processing -> needs_review -> approved -> running -> awaiting_review -> delivering -> delivered
                    \-> refused                   \-> failed                  \-> discarded
needs_review -> rejected          error (classification threw)
```

## A. Telegram -> gateway (`POST /webhook/telegram`, `gateway/api.py`)

1. The header `X-Telegram-Bot-Api-Secret-Token` is compared with `TELEGRAM_WEBHOOK_SECRET`. A mismatch returns 403.
   Without the secret configured, ordinary users are served but every admin action stays off (fail closed).
2. A button press (`callback_query`) is an admin action. It is ignored unless the request is authentic.
3. A text message is offered to the admin handler first. Only Luigi's numeric ID counts, and only on an authentic
   request. A stranger's `/approve` is swallowed and never becomes a job.

## B. Messages that never become jobs

4. `/start` - short privacy notice.
5. `/privacy` - full notice, split into several messages.
6. `RIESAMINA` - the customer asks for a refusal to be reviewed; Luigi is alerted (`gateway/review_request.py`).
7. `/ask ...` or `?...` - forwarded to the RAG API (`RAG_API_URL`, `/chat/sync`).
8. `/cancella` - handled in `gateway/admin_telegram.py` and `gateway/erasure.py` (not traced here).

## C. Everything else becomes a job

9. Text is normalized: markdown characters stripped. Empty after that -> asks for a text request.
10. `PipelineAdapter.submit` removes control characters and cuts the text to 4000 characters.
11. A job is stored with status `queued`, a 10-character ID, and `expire_at` (default 90 days, `gateway/retention.py`).
12. A submit error answers "Non riesco a elaborare questa richiesta".

## D. Classification (`QueueWorker.process_job`, `gateway/worker.py`)

13. Status becomes `processing`.
14. `safety.check` (phrase filter) runs first; it needs no model call.
15. If it does not hit, Stacy classifies with an LLM: intent, product type, confidence, refuse flag.
16. If classification throws, the job is saved as `error` and the user is told "Classification failed".
17. Outcomes:
    - **refused** - customer gets the refusal text; retention drops to 30 days; Luigi gets a Telegram notice with
      Riesamina and no approve button.
    - **needs_review** - always, even for a catalogue product. Nothing runs or costs money before Luigi approves.
      The customer sees product and price if known, or "needs Luigi's approval" if not.
18. For `needs_review`, Luigi gets a Telegram card with buttons plus an email to the notify list.

On Cloud Run `GATEWAY_SYNC_REPLY` classifies inline, because the container freezes once the webhook returns.
Otherwise the user gets "Ricevuto" and a Job ID, and a background worker polls the queue.

## E. Luigi decides (`gateway/admin_telegram.py`)

19. Approva / Gratis / Imposta prezzo / Rifiuta, or `/approve`, `/prezzo`, `/reject`. Only his ID, once per decision.
20. Approving sets `approved` and enqueues Cloud Tasks queue `pipeline-runs` (max-attempts=1: a failed run is never
    retried automatically).

## F. Pipeline worker (private Cloud Run service)

21. The worker claims the job (`approved` -> `running`).
22. It runs the 6-agent LangGraph pipeline at the approved price (see the agents section below).
23. On completion the job is `awaiting_review`.
24. A job stuck in `running` is moved to `failed` by the sweep every 10 minutes (`gateway/recovery.py`); never relaunched
    automatically.

## G. Delivery

25. Luigi receives the file plus a card (product, price, QA, risk) with **Invia al cliente** / **Scarta**.
26. Invia sends the file (`delivering` -> `delivered`, once only). Scarta leaves the customer unaware.
27. The worker does not `git push`, send Francesca's email or write the audit log. Recording a delivery is manual.

## Step 22 in detail: the pipeline as implemented

Verified by reading `deliverables/2026-05-25_016_aistudio-langgraph/` (`P` below; nodes in `P/nodes.py`) and
`gateway/studio_runner.py`. Nothing was executed. Where this differs from `CLAUDE.md` / `agents/README.md`, the code wins.

### Skeleton

- `studio_runner.run_job` (:137-157) rejects a missing or out-of-range price, then calls
  `build_studio_graph(deliver=headless_deliver)` with a fresh MemorySaver and `run_pipeline(..., auto_approve=True,
  extra_state={"approved_price": "x.xx", "luigi_decision": "approved"})`. Provider is `openai` (the node default is `anthropic`).
- Wiring (`P/graph.py:89-140`): `stacy_classify` -> (`luigi_escalate` | `gianni_scope`) -> `chiara_implement` ->
  Send fan-out to 3 risk nodes -> `risk_aggregator` -> `stacy_qa` -> `marco_invoice` -> `francesca_deliver` -> END.
  QA failure loops back to Chiara up to 3 times. In reality there are 11 nodes, not 6.
- `get_llm(provider, tier)` (`P/llm_factory.py`): openai fast = gpt-4o-mini, smart = gpt-4o; anthropic fast = haiku-4-5,
  smart = sonnet-4-6. No retries or timeouts are set.
- `luigi_escalate` is always an `interrupt_before` point, but `run_pipeline` resumes it automatically (up to 3 times),
  and the pre-seeded `luigi_decision="approved"` makes it pass. In the worker, risk escalation never blocks.

### 1. Stacy - classify (`nodes.py:32-69`)

One fast-tier LLM call returns JSON (`intent`, `product_type`, `dependencies_ok`, `input_type`). The price comes from
`PRICING_TABLE` (`state.py:12-55`, fallback merged with `config/global_settings.json`). Unknown or null price sets
`escalate_to_luigi`.

- The prompt lists 12 of the 18 catalogue products. Missing: algo_trading, mind_dashboard_journal,
  micro_syllabus_flashcards, family_archivist, mediterranean_meal_planner, niccolo_chronicles.
- No keyword table, no `intent_registry.yaml`, no skill preload. `dependencies_ok` is never used for routing.
- On an exception it returns only `error`, and the graph carries on to Gianni with `product_type=None`.

### 2. Gianni - scope (`nodes.py:73-118`)

One smart-tier call returns `technical_spec`, `stack`, `deployment_target`, `estimated_hours`, `blockers`. No tools, RAG or
templates. The requirements gate and risk-surface analysis described in the docs do not exist; `blockers` and
`estimated_hours` are written and never read. On an exception the graph continues to Chiara with an empty spec.

### 3. Chiara - implement (`nodes.py:230-256`, strategies :221-227)

Dispatch is `_CHIARA_STRATEGIES.get(product_type, _chiara_llm_codegen)`.

| Strategy | Products | How |
|----------|----------|-----|
| `_chiara_invoice` | invoice_pdf | LLM extracts fields, emits a `generate_invoice.py` script that calls `InvoiceTemplate`. No PDF is rendered; the amount comes from the request, not the approved price |
| `_chiara_chatbot` | chatbot_app | No LLM call; `ChatbotTemplate(...).render()` with a provider picked from Gianni's stack |
| `_chiara_landing` | 3 landing tiers | LLM fills 7 tokens in `templates/web/landing_page_base.html`; many other `{{ }}` tokens stay unreplaced; all three price tiers give the same output |
| `_chiara_llm_codegen` | everything else | Smart tier, max 8192 tokens, single file. Parses `SKILLS:` / `FILE:` headers by line; fences or a missing blank line put the whole raw text in the file |

The skills listed in CLAUDE.md (`langchain-rag` etc.) are never loaded. `deliverable_path` is never written to disk in
headless mode. A QA retry does not feed the QA issues back: Chiara never reads `qa_result`, so a retry is a blind regeneration.

### 4. Stacy QA (`nodes.py:382-418`)

One fast-tier LLM call over `technical_spec` and only the first 2000 characters of the deliverable. `qa_passed` defaults
to False. `validate_advisory_output()` is NOT called by the pipeline (it exists in `scripts/learning_loop.py` and one
test). An exception leaves `qa_passed` False, which loops back to Chiara; after 3 attempts the worker reports
"QA non superata dopo N tentativi" (`studio_runner.py:171-175`).

### Risk panel (`nodes.py:261-378`)

Three real nodes: `technical_auditor`, `compliance_agent`, `reputation_guardian`. Each is one LLM call returning a
`risk_score` 1-5 over the first 1000-2000 characters; an exception becomes score 1 (fails open).
**Financial Controller and Operational Monitor are not nodes** (docs and `.claude/agents` only). There is no
`P x impact x blast_radius` formula and no 2σ test: `risk_aggregator` takes a plain mean, passes below 3.5, and the "2σ"
wording is cosmetic. A 5/1/1 run averages 2.3 and passes. Chiara resets `risk_reports` to `[]` on retry, but with an add
reducer that does not clear the list, so earlier attempts pile into the average.

### 5. Marco - finance (`nodes.py:422-450`)

Uses `approved_price` if present (so "0.00" means free), else the catalogue price; a null price sets `escalate_to_luigi`.
The "invoice" is a dict (`INV-YYYYMMDD-<8hex>`, product, price, date, client, status). No PDF, no cost or margin
calculation. The edge to Francesca is unconditional (`graph.py:134`), so a blocked run still reaches her in the CLI;
in the worker `run_job` rejects missing prices up front.

### 6. Francesca - delivery

- **Full** (`nodes.py:594-663`, CLI and Streamlit): next audit ID, writes `deliverables/<date>_<NNN>_<slug>/`, writes the
  audit log (every agent hardcoded `success`), `git add/commit/push` to the current branch (no PR or merge), runs
  `post_delivery_update.py`, sends Gmail SMTP email if credentials exist.
- **Headless** (`studio_runner.headless_deliver`, :87-102, used by the worker): returns `status="ready"` and nothing else.
  No disk write, git, email, audit log or learning loop. So gateway jobs do not satisfy the STEP 4 checklist; recording
  is manual.

### Result and Luigi's card

`run_job` (:159-190) builds a `RunResult`: `ok` needs `finished`, `delivery.status == "ready"` and non-empty content
(files over 400,000 bytes fail). Fields: filename, content, product_type, price (approved), invoice_id, qa_passed,
`risk_score` (mean), `high_risk` (>= 3.5), skills, scrubbed `steps`. `pipeline_worker.py:104-121` sets `awaiting_review`
or `failed`; `notify_result` (`gateway/notify.py:267-291`) sends the file with the Invia/Scarta keyboard. The caption shows
job ID, request (200 chars), product and price, QA pass/fail, risk, file name and size, customer chat ID. QA issues, risk
findings and the invoice are not shown.

### Open problems found (not fixed)

1. Stacy's prompt omits 6 catalogue products.
2. Chiara retries without QA feedback.
3. `risk_reports` accumulates across retries; averaging hides a single critical score.
4. Financial Controller and Operational Monitor are not implemented; the risk formula and 2σ are not either.
5. Invoice product delivers a `.py` file with an amount that ignores Luigi's price.
6. Landing page tiers are not differentiated and leave tokens unreplaced.
7. `validate_advisory_output` is never used by the pipeline; QA sees only 2000 characters.
8. Node failures in Stacy, Gianni and Chiara do not stop the run.
9. Marco has no margin calculation and no PDF invoice.
10. Headless delivery writes no audit log or deliverable folder.

Not verified: `post_delivery_update.py` internals, `gateway/admin.py` send-to-customer logic, and whether the template
files render correctly.

## Known quirk

`gateway/bot_telegram.py` still holds an older polling-mode `handle_message` with different behaviour (it says "Luigi
needs to approve" on any submit error and always replies "being processed"). The live webhook uses only its
`_normalize` helper.

## Related

- `deliverables/2026-10-09_036_approval-pipeline-worker/README.md` - operations guide
- `docs/plans/luigi-approval-notifications.md` - plan and phase status
- [02 Agents](02_agents.md) - roster
