# Agent Creation Rules

## Context
You are creating a new AI staff agent profile or expanding an existing one.

## Profile Template
Follow the pattern in `agents/langchain_stacy.md` exactly. Every agent profile must include:
- **Name** and persona
- **Role** (Italian title + English descriptor)
- **Owns** — domains and deliverables
- **Stack** — tools, frameworks, LLM model
- **Personality** — communication style, biases, defaults
- **Integration points** — which agents they coordinate with

## Existing Staff (do not duplicate)
| Agent | Role |
|---|---|
| Luigi | Il Fondatore — visionary, strategy |
| Stacy | Braccio Destro — LangChain executor |
| Gianni | Il Tecnico — infra & hardware |
| Chiara | La Designer — UX/UI, branding |
| Francesca | La Venditrice — sales, community |
| Marco | Il Banchiere — finance |

If the requested capability fits an existing agent, extend their profile rather than creating a new one.

## Placement
Save new profiles in `agents/`. Update `agents/README.md` to reflect the full roster.

## When Done
→ Profile committed to `agents/`  
→ `agents/README.md` updated  
→ LOAD: `docs-rules.md` if additional documentation is needed
