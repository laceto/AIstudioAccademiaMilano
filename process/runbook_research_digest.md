# Runbook — digest settimanale della ricerca GitHub (per Gianni, pipeline v2)

Una volta a settimana il worker della pipeline cerca su GitHub i progetti AI più attivi (Scout → Analyst → Curator, senza
LLM: costo zero oltre alle chiamate GitHub) e salva un digest breve: i primi 10 repo, una riga ciascuno. Con `PIPELINE_VERSION=v2`
Gianni ne legge i primi 5 quando scrive la specifica. Senza digest, o con un digest più vecchio di 14 giorni, Gianni lavora come prima.

Codice: `gateway/research_digest.py`, endpoint `POST /research/run` in `gateway/pipeline_worker.py`.

## Dove sta il digest

- `JOB_STORE=firestore` (Cloud Run): un solo documento `research/latest`. Il worker usa già Firestore per i job, nessun servizio nuovo.
- `JOB_STORE=file` (locale): `gateway/queue/research_digest.json` (o `RESEARCH_DIGEST_PATH`).
- Una run fallita o vuota **non** sovrascrive il digest precedente.

## Variabili sul worker

| Variabile | A cosa serve |
|-----------|--------------|
| `RESEARCH_GITHUB_TOKEN` (o `GITHUB_TOKEN`) | Senza, GitHub concede 60 richieste/ora e la ricerca può fermarsi: mettilo come secret |
| `PIPELINE_VERSION=v2` | Gianni legge il digest solo in v2 |

## Pianificazione (da fare a mano: questo repo non crea risorse cloud)

Stessa identità e stesso `run.invoker` di `/run` e `/sweep`. Esempio, una volta a settimana il lunedì alle 06:00:

```bash
gcloud scheduler jobs create http research-digest-weekly \
  --location "$SCHEDULER_LOCATION" \
  --schedule "0 6 * * 1" --time-zone "Europe/Rome" \
  --uri "$WORKER_URL/research/run" --http-method POST \
  --oidc-service-account-email "pipeline-tasks@$PROJECT.iam.gserviceaccount.com" \
  --oidc-token-audience "$WORKER_URL"
```

(`SCHEDULER_LOCATION` come in `docs/cloud-run-setup.md`; `deploy_cloudrun.sh` ha già `ensure_scheduler_job` se vuoi
aggiungerlo allo script.) Dopo un deploy del worker, per provarlo subito: `gcloud scheduler jobs run research-digest-weekly --location "$SCHEDULER_LOCATION"`.

## Se qualcosa non va

- Risposta `502 research run failed`: Cloud Scheduler la mostra come fallita; guarda i log del worker (`[research]`). Cause
  tipiche: limite di richieste GitHub (manca il token), GitHub non raggiungibile. Il digest vecchio resta valido fino a 14 giorni.
- Gianni non usa il digest: il suo messaggio nel trace finisce con `research=none` (vuoto, vecchio, rovinato) o `research=digest`.
- Il testo dei repo è scritto da sconosciuti: viene appiattito su una riga, tagliato a 100 caratteri e passato a Gianni in un
  blocco dichiarato non fidato. Non è una barriera assoluta: se un digest ti sembra strano, cancella il documento `research/latest`.
