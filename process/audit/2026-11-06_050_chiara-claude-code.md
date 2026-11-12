---
request_id: "050"
date: "2026-11-06"
intent: internal_tooling
product_type: internal
outcome: success
price: "0.00"
invoice_id: "—"
agents_invoked:
  - name: Stacy
    role: intent_classifier
    action: >
      "Build the Claude Code engine for Chiara" -> nuovo motore di build dentro la pipeline LangGraph,
      tooling interno, 0.00. Gate agentico: /agentic-router -> langgraph-fundamentals, deep-agents-core.
    duration_sec: 0
    status: ok
  - name: Gianni
    role: technical_scoper
    action: >
      CLI `claude -p` in subprocess invece dell'Agent SDK Python, per controllare l'ambiente del processo
      (l'SDK unisce os.environ). Contratto invariato: deliverable_content resta una stringa (bundle di
      testo con marcatori, non zip) perché QA, Firestore e sendDocument portano testo. Spento di default
      (CHIARA_ENGINE), solo prodotti di codice, fallback alla strategia esistente su ogni errore.
      Isolamento: env pulito, utente `builder`, tool limitati, --bare, budget e timeout.
    duration_sec: 0
    status: ok
  - name: Chiara
    role: implementer
    action: >
      Test prima (38 + 6 su immagine/deploy), poi chiara_claude_code.py (prompt con blocco cliente
      recintato e feedback QA, flag CLI, env pulito, cambio utente, raccolta file senza symlink, test
      rieseguiti senza chiavi, bundle con riepilogo in testa), aggancio in chiara_implement (v1 e v2),
      scripts/unpack_bundle.py, Dockerfile con ARG CHIARA_CLAUDE_CODE (Node, CLI 2.1.318, builder),
      substitution in cloudbuild.worker.yaml, CHIARA_* in worker_env_vars, deploy che accende la build arg.
    duration_sec: 0
    status: ok
  - name: Stacy QA
    role: qa
    action: >
      Suite completa: 1356 passati sul branch contro 1312 su main, stessi 14 fallimenti su entrambi
      (indice RAG assente, logging di api_server), nessuno nuovo. CLI vera 2.1.318 con chiave finta:
      flag accettati, JSON con is_error/result/total_cost_usd, fallback "Invalid API key". Cambio utente
      vero: CLI avviata come builder; builder non legge /proc/<pid>/environ del worker. Non provati:
      build con un modello vero, build Docker, Cloud Run.
    duration_sec: 0
    status: ok
  - name: Marco
    role: finance
    action: >
      Internal tooling: 0.00, no invoice. Nota: una build costa fino a CHIARA_CLAUDE_CODE_BUDGET_USD
      (default 2.00 $) contro prodotti da 9.90-29.90 €; il costo è nel trace ma Marco non lo legge ancora.
    duration_sec: 0
    status: ok
skills_used: [langgraph-fundamentals, deep-agents-core]
learning_flags:
  new_skills: []
  new_mcp: []
  risk_score: 2
  risk_note: >
    2 per il codice mergiato (spento di default, nessun cambiamento finché non si accende). Accenderlo su
    Cloud Run porta il rischio a 3+: il codice scritto da Claude Code gira nel worker, che ha rete e il
    metadata server con il service account che legge Firestore. Decisione di Luigi (vedi guida).
  lessons:
    - agent: Chiara
      cue: "When a pipeline step runs agent-written or customer-influenced code inside a service that holds secrets"
      lesson: "Run it as a separate unprivileged user with a clean env, not just a clean env: a same-user process can read the parent's secrets from /proc/<pid>/environ."
      evidence: "050: as root, cat /proc/<worker pid>/environ showed a test secret; as user builder it returned Permission denied."
      confidence: high
    - agent: Gianni
      cue: "When code builds the command line for an external CLI (claude, gcloud, ...)"
      lesson: "Run the real CLI once with a dummy credential to check every flag parses and the output shape matches what the code reads; --help may not list every flag."
      evidence: "050: claude 2.1.318 with sk-ant-dummy accepted all flags and returned {is_error: true, result: 'Invalid API key', total_cost_usd: 0}; --max-turns is not in its --help, so the engine uses --max-budget-usd and a timeout instead."
      confidence: high
    - agent: Chiara
      cue: "When running the repo's test suite in the cloud container"
      lesson: "The pytest on PATH is a uv tool without the repo's packages: pip install -r gateway/requirements.txt -r gateway/requirements.worker.txt pytest, then python -m pytest."
      evidence: "050: /root/.local/bin/pytest failed collection with ModuleNotFoundError: httpx; python -m pytest after installing the requirements collected 1372 tests."
      confidence: medium
---

Motore Claude Code per Chiara. Guida: `deliverables/2026-11-06_050_chiara-claude-code/README.md`.
