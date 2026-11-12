# 047 — Gateway protetto con chiave

## Cosa cambia

| Endpoint | Prima | Ora |
|----------|-------|-----|
| `POST /submit` | aperto a chiunque | serve l'header `X-API-Key` |
| `GET /status/{id}` | aperto: testo, chat_id, user_id e IP del cliente a chi conosceva l'id | serve `X-API-Key` |
| `/` (catalogo) | bottone "Order this" che chiamava `/submit` dal browser | bottone "Order on Telegram" che apre il bot clienti |
| `/health`, `/api/showcase`, `/trading` | pubblici | invariati |
| webhook Telegram e WhatsApp | secret token / firma Twilio | invariati |

Regole della chiave (`gateway/auth.py`):

- `GATEWAY_API_KEY` di almeno 32 caratteri; un valore più corto o il segnaposto di `.env.example` conta come "non configurata".
- Chiave non configurata → `/submit` e `/status` rispondono **503**: un deploy senza chiave resta chiuso, non aperto.
- Chiave sbagliata o assente → **401**, nessun job creato. Il limite di 10 richieste al minuto per IP scatta prima del controllo della chiave, quindi anche i tentativi di indovinarla sono limitati.
- Solo in locale: `GATEWAY_ALLOW_OPEN_SUBMIT=1` lascia passare senza chiave finché `GATEWAY_API_KEY` non è impostata. `.env` non entra nell'immagine Docker, quindi su Cloud Run non arriva.

## Cosa deve fare Luigi

1. In `.env`: `TELEGRAM_BOT_USERNAME=<username del bot clienti, senza @>`. Senza, il catalogo non mostra il bottone d'ordine.
2. `GATEWAY_API_KEY` in `.env`: lasciala vuota. Il deploy ne genera una e la tiene in Secret Manager.
3. Deploy: `scripts/deploy_cloudrun.sh --dry-run`, poi senza `--dry-run`.
4. Copia la chiave nel secret di repository GitHub `GATEWAY_API_KEY` (Settings → Secrets and variables → Actions), così il job `deployed` dello smoke test funziona:
   ```bash
   gcloud secrets versions access latest --secret=GATEWAY_API_KEY
   ```
5. Prova: Actions → **Gateway smoke test** → `target: deployed`. Deve dare `rejects_missing_key` = 401 e `submit` = 202.

Fino al deploy, il gateway su Cloud Run resta aperto come prima.

## Chiamare il gateway con la chiave

```bash
curl -X POST "$GATEWAY_URL/submit" \
  -H "X-API-Key: $GATEWAY_API_KEY" -H "Content-Type: application/json" \
  -d '{"text": "Vorrei una landing page", "channel": "api"}'
```

## Limiti

- Una sola chiave per tutti i client: per cambiarla, nuova versione in Secret Manager e nuovo deploy (e aggiorna il secret GitHub).
- Il bottone apre il bot e basta: il cliente scrive la richiesta lì e il prodotto scelto non viene passato al bot.
- Non ancora deployato né provato su Cloud Run.
