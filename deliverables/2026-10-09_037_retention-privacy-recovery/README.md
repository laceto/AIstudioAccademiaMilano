# 037 — Retention dei dati, informativa privacy e recupero dei job bloccati

Il codice sta in `gateway/` e `scripts/`; questa cartella è il punto d'ingresso per capire come funziona e come si gestisce.
Audit: `process/audit/2026-10-09_037_retention-privacy-recovery.md`. Precedente: `deliverables/2026-10-09_036_approval-pipeline-worker/`.
Operazioni e deploy: `docs/cloud-run-setup.md`.

## Cosa fa

1. **Conservazione**: ogni job ha `expire_at` (creazione + 90 giorni). Firestore lo cancella da solo (TTL sul campo `jobs.expire_at`). Il numero dei giorni vive in un solo posto.
2. **Protezione**: il database Firestore ha la protezione dalla cancellazione attiva.
3. **Recupero**: un job in `running` da oltre 1200 s (worker caduto) viene messo in `failed`, mai rilanciato da solo (costerebbe chiamate OpenAI). Luigi riceve un avviso una volta, con il bottone Riprova.
4. **Informativa**: `/start` mostra un avviso breve, `/privacy` l'informativa completa in italiano.

## Dove sta il codice

| Parte | File |
|-------|------|
| Giorni di conservazione (`JOB_RETENTION_DAYS`, default 90) | `gateway/retention.py` |
| `expire_at` scritto come timestamp e riletto come stringa ISO; `all_jobs()` | `gateway/jobstore.py` (`_to_storage`, `_from_storage`) |
| TTL e protezione dalla cancellazione, nello script di deploy | `scripts/cloudrun_lib.sh` (`ensure_firestore_ttl`, `ensure_delete_protection`), `scripts/deploy_cloudrun.sh` |
| Recupero dei job vecchi (`sweep_stale`, `finish_run`) | `gateway/recovery.py` |
| Endpoint `POST /sweep` sul worker privato | `gateway/pipeline_worker.py` |
| Comando `/sweep`, job in corso in `/pending` | `gateway/admin_telegram.py` |
| Testi dell'informativa (`/start`, `/privacy`) | `gateway/privacy.py` |
| Backfill dei job esistenti | `scripts/backfill_job_expiry.py` |
| Come rispondere a una richiesta di accesso o cancellazione | `process/runbook_privacy_requests.md` |

## Come si usa

- **Backfill** (una volta, già applicato il 2026-10-09 da Luigi): `python scripts/backfill_job_expiry.py` fa solo una prova e stampa cosa cambierebbe; `python scripts/backfill_job_expiry.py --apply` scrive. I job finiti ricevono creazione + retention; quelli ancora aperti ricevono adesso + retention, così non vengono cancellati.
- **Sweep**: lo lancia Cloud Scheduler (job `sweep-stuck-jobs`, ogni 10 minuti, regione `europe-west6`, OIDC come `pipeline-tasks`). A mano: `/sweep` su Telegram, solo dall'account di Luigi. Il worker risponde 403 a chi non è autenticato.
- **Job fallito dallo sweep**: Luigi preme Riprova (o `/run <id>`). Un risultato tardivo del worker originale viene accettato solo se il job è stato fallito dallo sweep e `started_at` coincide.
- **Richiesta di accesso o cancellazione**: segui `process/runbook_privacy_requests.md`.
- **Deploy**: `scripts/deploy_cloudrun.sh` imposta TTL, protezione e job Scheduler; se `describe` o la località dello Scheduler falliscono avvisa e va avanti.

## Impostazioni (`.env`, copiate dallo script di deploy)

`JOB_RETENTION_DAYS` (default 90, valori da 1 a 3650), `PIPELINE_STALE_SECONDS` (default 1200), `PRIVACY_CONTACT` (email o @handle, opzionale: senza, l'informativa lo dice con onestà).

## Stato verificato il 2026-10-09 (progetto `aistudio-milano`)

Protezione `DELETE_PROTECTION_ENABLED`; TTL su `jobs.expire_at` `ACTIVE`; job Scheduler ENABLED, chiamate alle 15:10, 15:20 e 15:30 UTC con HTTP 200; i 10 job esistenti hanno `expire_at` a 89 giorni, nessuno scaduto. Il deploy del gateway con l'informativa è stato lanciato da Luigi con il testo generico del titolare; il testo live è da confermare.

## Costi e limiti

- Nessun costo nuovo di rilievo: Cloud Scheduler (un job), Firestore TTL e Cloud Run restano nel free tier a questi volumi.
- Il registro di Cloud Logging dura 30 giorni (bucket predefinito) e le singole righe non si possono cancellare; il recupero point-in-time di Firestore è disattivato.
- "90 giorni" è vero solo ora che il TTL è attivo e il backfill è stato eseguito. Un job ancora non finito al giorno 90 viene cancellato.
- Il risultato tardivo scartato dopo Riprova viene solo scritto nel log.
- La soglia di 1200 s potrebbe richiedere una taratura.
- Il controllo dello stato prima del passaggio a `failed` riduce ma non elimina del tutto la corsa tra sweep e Riprova.

## Da fare per Luigi

Identità del titolare (nome o società, indirizzo, P.IVA/codice fiscale) e `PRIVACY_CONTACT`; confermare con un professionista la formula sulle garanzie per i trasferimenti; decidere il limite di età; accettare i DPA di Google Cloud e OpenAI; confermare il testo live dell'informativa. `/cancella` e il rifiuto delle richieste fraudolente sono il passo successivo (consegna separata).

## Prove

`pytest tests/test_gateway_*.py tests/test_deploy_cloudrun_lib.py` più i test di retention, recovery e privacy. Suite completa: 818 passati su main, 13 fallimenti preesistenti.
