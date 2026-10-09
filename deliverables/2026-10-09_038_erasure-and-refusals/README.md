# 038 — Cancellazione su richiesta e rifiuto delle richieste fraudolente

Il codice sta in `gateway/`. Audit: `process/audit/2026-10-09_038_erasure-and-refusals.md`.
Operazioni: `docs/cloud-run-setup.md` (tabella dei comandi e sezione 1f), `process/runbook_privacy_requests.md`.

## Cancellare i dati di un cliente (`/cancella`)

Solo dal tuo account Telegram.

| Comando | Cosa fa |
|---------|---------|
| `/cancella <job_id>` | mostra una scheda per quel job |
| `/cancella chat <chat_id>` | mostra una scheda con tutti i job di quella chat |

La scheda riporta numero di job, stati e date, **mai il testo del cliente**, con **Conferma** e **Annulla**.
Solo Conferma cancella. Regole:
- i job in `running` o `delivering` non si cancellano (aspetta o usa `/sweep`);
- si cancella esattamente quanto mostrato: se i job della chat sono cambiati dopo la scheda, non si cancella
  nulla e ne arriva una nuova;
- se una cancellazione fallisce a metà, quello cancellato resta registrato e ti viene detto cosa ripetere;
- ogni cancellazione scrive un record nella raccolta `erasures` (ora, chi, tipo, quanti, ID casuali dei job:
  **senza** ID di chat né testo); non ha scadenza, perché serve a dimostrare di aver cancellato.

Il bot ti ricorda cosa **non** può fare: le copie nella tua casella email, i messaggi e i file nella tua chat con
il bot, e le righe di Cloud Logging (scadono da sole dopo 30 giorni).

## Rifiutare le richieste chiaramente illegali

Una richiesta come "ricetta medica falsa" non va più in coda per la tua approvazione: viene rifiutata.

1. **Filtro a frasi** (`gateway/safety.py`): gira prima del modello, funziona senza chiave API. Rifiuta solo ciò
   che è inequivocabile (documenti o ricette falsi, phishing, ransomware, keylogger, clonazione di carte) e lascia
   passare formulazioni educative o difensive ("come riconoscere…", "simulato per formare…") se stanno nella
   stessa frase.
2. **Il modello** può rifiutare a sua volta (`refuse`), con istruzioni prudenti.
3. Il cliente riceve un rifiuto breve e neutro, senza categoria. Può rispondere **RIESAMINA**: questo non crea un
   job, avvisa te (con il bottone **Riesamina**) e decidi tu.
4. A te arriva un avviso (solo Telegram, niente email) con la categoria ("possibile …", automatica e non
   verificata), l'inizio del testo e il numero di richieste rifiutate di quella chat.
5. **Riesamina** (bottone o `/riesamina <job_id>`) riporta il job in revisione normale: stesse schede di
   approvazione, solo su Telegram, conservazione normale.
6. Le richieste rifiutate si conservano **30 giorni** (`JOB_REFUSED_RETENTION_DAYS`), le altre 90.

Estendere o correggere l'elenco: `gateway/safety.py` (frasi e parole "educative"); i casi che non devono mai essere
rifiutati stanno in `MUST_NOT_REFUSE` nei test.

Limiti noti: parafrasi, errori di battitura, altre lingue e richieste spezzate in più messaggi passano il filtro;
non prende "certificato di malattia falso" né "forge a doctor's signature". Un rifiuto sbagliato si corregge con
Riesamina.

## Altro in questa consegna
- `/privacy` esce in più messaggi (fino a 3.500 caratteri ciascuno), così non rischia più il limite di Telegram.
- Learning loop: una skill diventa hook solo se esiste `scripts/preload_<skill>.py`; comando portabile; niente
  `risk_score` finto. Nessun hook promosso per `breakdown`, `agentic-router` ecc.

## Impostazioni nuove
`JOB_REFUSED_RETENTION_DAYS` (default 30), `ERASURES_COLLECTION` (default `erasures`), `ERASURE_DIR` (solo backend a file).

## Prove
`pytest tests/test_gateway_erasure.py tests/test_gateway_safety.py tests/test_gateway_refusal.py tests/test_gateway_refusal_review.py tests/test_gateway_privacy.py tests/test_learning_loop_hook_promotion.py tests/test_gateway_jobstore.py`
