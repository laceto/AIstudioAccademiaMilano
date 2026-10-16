---
request_id: "042"
date: "2026-10-16"
intent: drive_semantic_router
product_type: unknown_product
outcome: partial
price: null
invoice_id: "—"
agents_invoked:
  - name: Stacy
    role: intent_classifier
    action: >
      Semantic routing of Google Drive files + Azure deploy. Not in the STEP 1 table (closest:
      rag_knowledge_base for the embeddings/vectorstore part) -> unknown_product: null, pending Luigi.
      OAuth dependency flagged: full Drive scope, refresh token.
    duration_sec: 0
    status: ok
  - name: Gianni
    role: technical_scoper
    action: >
      FastAPI + sentence-transformers (MiniLM, CPU) + persistent ChromaDB (cosine), Drive API v3,
      APScheduler, App Service F1 + Key Vault references. OCR delegated to Drive (copy as Google Doc)
      to keep Tesseract out of the image. Flagged F1 limits: no Always On (scheduler sleeps),
      60 CPU-min/day, 1 GB RAM; English-only model on Italian documents.
    duration_sec: 0
    status: ok
  - name: Chiara
    role: implementer
    action: >
      driverouter/{requirements.txt, classifier.py, main.py, Dockerfile, deploy_azure.sh}, tests first
      against a fake embedder and fake Drive; DRY_RUN on by default; unsure files stay in the inbox.
    duration_sec: 0
    status: ok
  - name: Stacy QA
    role: qa
    action: >
      27 offline tests pass (real ChromaDB). Deploy script: bash -n + --dry-run, secrets masked.
      Not run: real model, docker build, real Drive, Azure (pytorch index and Hugging Face blocked
      by the build container's network).
    duration_sec: 0
    status: ok
  - name: Marco
    role: finance
    action: "unknown_product -> price null, no invoice. Proposal to Luigi: 29.90 (in line with rag_knowledge_base)."
    duration_sec: 0
    status: blocked
skills_used: []
learning_flags:
  new_skills: []
  new_mcp: []
  risk_score: 3
---

Outcome is partial: code and offline tests only. Risk 3: the service moves and renames files on a real
Drive with the full `drive` scope and exposes a public endpoint. Mitigations: DRY_RUN=true by default
(also in the deploy script), API key on `/sync-documents` failing closed, secrets only via Key Vault
references, below-threshold files never move. Open: price approval, Google OAuth client + refresh token,
image build, a DRY_RUN pass on the real inbox to tune MIN_SIMILARITY, external cron because F1 sleeps.
