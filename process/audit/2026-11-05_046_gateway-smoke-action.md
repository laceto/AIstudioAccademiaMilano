---
request_id: "046"
date: "2026-11-05"
intent: internal_tooling
product_type: internal
outcome: success
price: "0.00"
invoice_id: "—"
agents_invoked:
  - name: Stacy
    role: intent_classifier
    action: >
      "Nuova azione GitHub: simulare una richiesta di progetto, inviarla al gateway e vedere
      se gira tutto" -> CI/tooling interno sul gateway, 0.00 (internal). Non LangGraph.
    duration_sec: 0
    status: ok
  - name: Gianni
    role: technical_scoper
    action: >
      Letti gateway/api.py, pipeline_adapter.py, worker.py. Su Cloud Run GATEWAY_SYNC_REPLY=1:
      /submit mette in coda ma nessuno classifica (solo il webhook Telegram classifica inline),
      quindi due livelli: locale nel runner (submit -> worker -> needs_review) e deployed
      (health, submit, status) solo manuale, perché lascia un job vero in Firestore.
    duration_sec: 0
    status: ok
  - name: Chiara
    role: implementer
    action: >
      Test prima (7), poi scripts/gateway_smoke.py (solo stdlib, transport iniettabile,
      riepilogo in GITHUB_STEP_SUMMARY) e .github/workflows/gateway-smoke.yml (push/PR su
      gateway/**, workflow_dispatch con target local|deployed|both, testo e use_llm).
    duration_sec: 0
    status: ok
  - name: Stacy QA
    role: qa
    action: >
      28 test passano (7 nuovi + Pablo). Giro reale con uvicorn + worker senza chiavi:
      6/6 controlli ok, job -> needs_review. Nessun segreto nel codice; Telegram ed e-mail
      spenti nel job locale. Il job deployed non è stato provato: il proxy del container blocca run.app.
    duration_sec: 0
    status: ok
  - name: Marco
    role: finance
    action: "Internal tooling: 0.00, no invoice."
    duration_sec: 0
    status: ok
skills_used: []
learning_flags:
  new_skills: []
  new_mcp: []
  risk_score: 1
  lessons:
    - agent: Gianni
      cue: "When testing the deployed gateway through POST /submit"
      lesson: "Do not wait for classification: on Cloud Run (GATEWAY_SYNC_REPLY=1) only the Telegram webhook classifies inline; /submit jobs stay queued. Test classification on a gateway run inside the runner."
      evidence: "046: gateway/api.py lifespan skips the QueueWorker when GATEWAY_SYNC_REPLY is set; /submit only calls PipelineAdapter.submit."
      confidence: high
---

Smoke test del gateway come GitHub Action. Guida: `deliverables/2026-11-05_046_gateway-smoke-action/README.md`.
