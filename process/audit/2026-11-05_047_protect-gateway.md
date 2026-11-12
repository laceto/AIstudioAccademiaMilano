---
request_id: "047"
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
      "Proteggi gateway" (dopo 046: /submit pubblico senza autenticazione) -> sicurezza del
      gateway, tooling interno, 0.00 (internal).
    duration_sec: 0
    status: ok
  - name: Gianni
    role: technical_scoper
    action: >
      Superficie: POST /submit apriva job a chiunque; GET /status/{id} restituiva testo, chat_id,
      user_id e IP a chi conosceva l'id. La pagina pubblica / chiamava entrambi dal browser, quindi
      una chiave nella pagina sarebbe stata pubblica. Luigi ha scelto: bottoni "Order" -> link al bot
      Telegram. Chiave X-API-Key su /submit e /status, fail-closed (503) se non configurata, apertura
      solo esplicita in locale (GATEWAY_ALLOW_OPEN_SUBMIT=1, ignorata se c'è una chiave).
    duration_sec: 0
    status: ok
  - name: Chiara
    role: implementer
    action: >
      Test prima (19 + 4 deploy + 1 smoke), poi gateway/auth.py (compare_digest, minimo 32 caratteri,
      placeholder rifiutati), dipendenze FastAPI su /submit e /status (rate limit prima della chiave),
      pagina senza JS di ordine e con link t.me/TELEGRAM_BOT_USERNAME (validato), deploy:
      resolve_secret generico, GATEWAY_API_KEY in Secret Manager e sul servizio, TELEGRAM_BOT_USERNAME
      tra le env; smoke client e workflow con la chiave (locale: chiave usa e getta mascherata;
      deployed: secret di repository).
    duration_sec: 0
    status: ok
  - name: Stacy QA
    role: qa
    action: >
      Suite: stessi 17 fallimenti di main (dipendenze mancanti nel container: numpy, fpdf2, langchain),
      24 test in più passano. Giro reale con uvicorn: con chiave 7/7, senza chiave 401, senza chiave
      configurata 503 e nessun job scritto; pagina con 14 link t.me e nessun fetch. Non deployato.
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
  risk_score: 2
  lessons:
    - agent: Gianni
      cue: "When adding authentication to a gateway endpoint"
      lesson: "First grep the served HTML for fetch() calls to that endpoint: a browser page cannot hold a secret, so decide with Luigi what replaces it before locking the endpoint."
      evidence: "047: the showcase page at / called /submit and /status from the browser on every product card."
      confidence: high
---

Protezione del gateway con chiave. Guida: `deliverables/2026-11-05_047_protect-gateway/README.md`.
