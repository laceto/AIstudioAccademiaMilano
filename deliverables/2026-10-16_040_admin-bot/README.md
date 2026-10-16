# 040 — Bot di amministrazione separato

Il codice sta in `gateway/` (`notify.py`, `admin_telegram.py`, `api.py`), `scripts/deploy_cloudrun.sh` e
`scripts/check_telegram.py`. Test: `tests/test_gateway_admin_bot.py`, `tests/test_telegram_health.py`.
Audit: `process/audit/2026-10-16_040_admin-bot.md`.

## Il problema

Con un solo bot, tu eri cliente e amministratore nella stessa chat: le tue richieste di prova e le schede di
approvazione (Approva / Gratis / Imposta prezzo / Rifiuta), gli avvisi e i risultati da rivedere arrivavano
insieme.

## Cosa cambia

| | Bot clienti (`TELEGRAM_BOT_TOKEN`) | Bot admin (`TELEGRAM_ADMIN_BOT_TOKEN`) |
|---|---|---|
| Chi ci parla | clienti, **e anche tu** per le prove | solo tu |
| Cosa ricevi | solo le risposte che riceverebbe un cliente | schede, avvisi, risultati da rivedere, comandi |
| Webhook | `/webhook/telegram` | `/webhook/telegram-admin` |
| Poteri admin | **nessuno** (le tue richieste sono richieste normali) | tutti, solo per il tuo ID |

Quello che deve arrivare al cliente (esito della decisione, file consegnato con "Invia al cliente") parte
sempre dal **bot clienti**: il cliente non ha mai avviato il bot admin.

Senza `TELEGRAM_ADMIN_BOT_TOKEN` tutto funziona come prima, con un solo bot.

## Come attivarlo

1. In Telegram, @BotFather → `/newbot`: crea un terzo bot (token diverso dagli altri due).
2. Scrivi il token in `.env` come `TELEGRAM_ADMIN_BOT_TOKEN`.
3. Apri il nuovo bot e premi **Start** (un bot non può scrivere a chi non l'ha mai avviato).
4. `bash scripts/deploy_cloudrun.sh --dry-run`, poi senza `--dry-run`: salva il segreto, lo dà a gateway e
   worker, registra il webhook del bot admin con lo stesso `TELEGRAM_WEBHOOK_SECRET`.
5. `python scripts/check_telegram.py` deve dire "All Telegram channels healthy".
6. Prova: scrivi una richiesta al bot clienti; la scheda deve comparire nel bot admin.

`NOTIFY_TELEGRAM_CHAT_IDS` resta il tuo ID numerico (in una chat privata, l'ID chat è il tuo ID utente).

## Limiti noti

- Le schede già inviate dal vecchio bot hanno bottoni che ora vengono ignorati: usa `/pending` sul bot admin.
- Lo stack locale (`run_local_stack.py`) usa il polling e non gestisce i bottoni, né prima né adesso.
- Mancano al momento: nessuna prova su Telegram reale (solo test con bot finti e dry-run del deploy).
