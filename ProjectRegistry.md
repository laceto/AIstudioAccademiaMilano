# Project Registry

> Purpose: Central registry of all AI Studio deliverable projects and internal systems.
> Owner Agent: Stacy (Intake) → Francesca (Delivery)
> Status: active

## Convention

New projects are created as standalone GitHub repos and linked as submodules in `projects/`.
See [`project-setup-rules.md`](project-setup-rules.md) for the full protocol.

## Deliverables Registry

| Project | Location | Owner Agent | Status | Date |
|---|---|---|---|---|
| 001 — Forno di Marta Website | `deliverables/2026-05-23_001_bakery-website/` | Chiara | active | 2026-05-23 |
| 002 — PDF Email Sender | `deliverables/2026-05-23_002_pdf-email/` | Chiara | active | 2026-05-23 |
| 003 — Invoice PDF Email | `deliverables/2026-05-23_003_invoice-pdf-email/` | Marco + Chiara | active | 2026-05-23 |
| 004 — AI Startup Street Monetization | `deliverables/2026-05-23_004_ai_startup_street_monetization.md` | Marco | active | 2026-05-23 |
| 005 — Chatbot Template | `deliverables/2026-05-23_005_chatbot/` | Chiara | active | 2026-05-23 |
| 007 — Calendar Sync | `deliverables/2026-05-23_007_calendar-sync/` | Chiara | active | 2026-05-23 |
| 008 — Algo Trading Bot (SMA Crossover) | `deliverables/2026-05-23_008_algo-trading/` | Chiara + Marco | active | 2026-05-23 |
| GitHub Research Department | `deliverables/github-research/` + `agents/research/` | Research Team | active | 2026-05-23 |
| RAG System | `deliverables/rag/` | Chiara | active | 2026-05-23 |

## Internal Systems Registry

| System | Location | Owner Agent | Status | Date |
|---|---|---|---|---|
| 6-Agent Pipeline | `agents/` | All agents | active | 2026-05-23 |
| AI Risk Management Team | `agents/risk/` | Luigi (oversight) | active | 2026-05-23 |
| GitHub Research Team | `agents/research/` | Research Team | active | 2026-05-23 |
| Learning Loop | `scripts/learning_loop.py` | Stacy QA | active | 2026-05-23 |
| Credential Manager | `scripts/credential_manager.py` | Compliance Agent | active | 2026-05-23 |
| Intent Registry | `process/intent_registry.yaml` | Gianni | active | 2026-05-23 |

## Submodule Projects

No standalone submodule projects registered yet.
See [`projects/README.md`](projects/README.md) for the submodule protocol.

## Notes

- All deliverables and internal systems live in the monorepo (pre-date the submodule convention).
- All new deliverable projects must follow the submodule protocol: create a repo named `AIstudio_Project_<timestamp>`, link via `git submodule add`, and register here.
