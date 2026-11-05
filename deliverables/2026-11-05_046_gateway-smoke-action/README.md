# 046 — Smoke test del gateway (GitHub Action)

Simula una nuova richiesta di progetto, la manda all'Input Gateway e controlla che venga
accettata, salvata e classificata.

- Workflow: `.github/workflows/gateway-smoke.yml`
- Script: `scripts/gateway_smoke.py` (solo libreria standard, gira anche a mano)
- Test: `tests/test_gateway_smoke.py`

## I due livelli

| Job | Quando parte | Cosa prova |
|-----|--------------|------------|
| `local` | ogni push/PR che tocca `gateway/**`, oppure a mano | gateway avviato nel runner (job su file, worker acceso, niente Telegram né e-mail): `submit` → worker → `needs_review` |
| `deployed` | solo a mano (`target: deployed` o `both`) | gateway vero su Cloud Run: `health`, `submit`, `status` |

Il job `deployed` non aspetta la classificazione: su Cloud Run (`GATEWAY_SYNC_REPLY=1`)
i job arrivati da `/submit` restano `queued`, perché solo il webhook Telegram classifica
subito. Ogni giro lascia quindi un job vero in Firestore, con `user_id`
`smoke-test-github-actions`, che scade come gli altri (`JOB_RETENTION_DAYS`).

## Controlli

1. `health` — `GET /health` risponde `ok`
2. `rejects_bad_channel` — un canale inesistente viene rifiutato (422)
3. `submit` — la richiesta simulata torna con `job_id` e `queued` (202)
4. `status` — `GET /status/{job_id}` restituisce lo stesso job e lo stesso testo
5. `classified` — solo in locale: entro 60 s il job passa a `needs_review`
6. `unknown_job_404` — un job inesistente dà 404

Il riepilogo finisce nella pagina del run (Summary).

## Come lanciarlo

Da GitHub: Actions → **Gateway smoke test** → Run workflow.

- `target`: `local`, `deployed` o `both`
- `request`: testo della richiesta (vuoto = pasticceria di esempio)
- `use_llm`: in locale classifica con il modello vero; serve il secret `ANTHROPIC_API_KEY`

URL del gateway deployato: variabile di repository `GATEWAY_URL`; se manca,
`https://gateway-947977086404.europe-west8.run.app`.

A mano:

```bash
GATEWAY_QUEUE_DIR=$(mktemp -d) JOB_STORE=file uvicorn gateway.api:app --port 8080 &
python scripts/gateway_smoke.py --url http://127.0.0.1:8080 --wait 60
```

## Limiti

- Il job `deployed` non è ancora stato provato: dal container di sviluppo `run.app` non è raggiungibile.
- `/submit` sul gateway pubblico non chiede autenticazione: chiunque può creare job (c'è solo il limite di 10 richieste al minuto per IP).
