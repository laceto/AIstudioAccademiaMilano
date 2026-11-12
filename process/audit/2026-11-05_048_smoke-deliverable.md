---
request_id: "048"
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
      "Chiedi di fare uno script che crea una lista in Python tramite la gh action. Come controllo
      l'output dei deliverables?" -> estensione dello smoke test (046), tooling interno, 0.00.
    duration_sec: 0
    status: ok
  - name: Gianni
    role: technical_scoper
    action: >
      Oggi nessun deliverable esce dall'Action: in locale il job si ferma a needs_review, su Cloud Run
      i job di /submit restano queued. Soluzione: nel runner approvare con gateway.admin.decide e
      chiamare il worker vero (/run, in process), job store a file, Telegram spento; output come
      artifact + Summary. Solo a mano (costa LLM).
    duration_sec: 0
    status: ok
  - name: Chiara
    role: implementer
    action: >
      Test prima (6, pipeline finta), poi scripts/gateway_deliver.py (nome file reso sicuro, niente
      Firestore, result.json senza contenuto, steps.txt), job_id dallo smoke in GITHUB_OUTPUT,
      workflow: run_pipeline + pipeline_provider, upload-artifact "deliverable" 14 giorni.
    duration_sec: 0
    status: ok
  - name: Stacy QA
    role: qa
    action: >
      80 test gateway/worker passano. Giro reale senza chiave LLM: smoke ok, approvazione, worker,
      pipeline fino agli agenti, failed con errore "Missing credentials" in result.json. Non provato
      con una chiave vera.
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
    - agent: Chiara
      cue: "When running a repo script that imports gateway/ or other repo packages"
      lesson: "Run it as a module (python -m scripts.name) or with PYTHONPATH=.; python scripts/name.py fails with ModuleNotFoundError: gateway."
      evidence: "048: python scripts/gateway_deliver.py failed with ModuleNotFoundError: No module named 'gateway'; python -m scripts.gateway_deliver worked."
      confidence: high
---

Smoke test fino al deliverable. Guida: `deliverables/2026-11-05_048_smoke-deliverable/README.md`.
