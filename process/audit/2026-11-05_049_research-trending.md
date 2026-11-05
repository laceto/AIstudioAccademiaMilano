---
request_id: "049"
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
      "La pipeline che scopre le repository su GitHub cerca anche quelle in trending." -> estensione
      dello Scout del team di ricerca, tooling interno, 0.00.
    duration_sec: 0
    status: ok
  - name: Gianni
    role: technical_scoper
    action: >
      Nessuna API per il trending: lettura di github.com/trending (HTML, stdlib re), filtro AI a
      parole intere, arricchimento via REST /repos per topic e date; dentro search_all_topics così
      CLI, digest settimanale e alert giornaliero lo ereditano; best effort, mai bloccante.
    duration_sec: 0
    status: ok
  - name: Chiara
    role: implementer
    action: >
      Test prima (22), poi trending.py, campi trending_stars/trending_since su Repo, bucket
      "trending" e marcatura dei topic hit, growth = max(storico, ritmo nel periodo), sezione
      "Trending on GitHub" nel report, campi nel digest e nota nella riga di Gianni, --trending e
      --trending-language nella CLI, trending daily nell'alert.
    duration_sec: 0
    status: ok
  - name: Stacy QA
    role: qa
    action: >
      Test research (trending, digest, pipeline v2) verdi; suite completa: stessi 17 fallimenti di
      main (dipendenze mancanti nel container), nessuno nuovo. Pagina vera non provata: github.com
      dà 403 dal proxy del container.
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
      cue: "When a feature reads a github.com HTML page (not api.github.com) from the cloud container"
      lesson: "Expect 403 from the container proxy; write the tests on a saved HTML fixture and say in the guide that the live page was not tried."
      evidence: "049: curl https://github.com/trending?since=weekly returned 403 from the container."
      confidence: medium
---

GitHub trending nello Scout del team di ricerca. Guida: `deliverables/2026-11-05_049_research-trending/README.md`.
