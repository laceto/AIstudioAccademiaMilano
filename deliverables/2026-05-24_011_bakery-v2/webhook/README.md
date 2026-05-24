# Bakery Order Webhook

Flask shim around `templates/web/order_webhook.py` (the reusable order handler extracted by the V2 Team).

## Local run

```bash
pip install -r requirements.txt
export MARTA_NOTIFY_EMAIL=marta@example.com
export GOOGLE_CALENDAR_ID=marta@group.calendar.google.com
python main.py
# POST http://localhost:8080/api/order
```

## Deploy to Cloud Run (reuses skill from request 010)

```bash
gcloud run deploy bakery-order-api \
  --source . \
  --region europe-west1 \
  --set-env-vars MARTA_NOTIFY_EMAIL=marta@example.com \
  --set-env-vars GOOGLE_CALENDAR_ID=marta@group.calendar.google.com \
  --set-secrets GMAIL_OAUTH_TOKEN_PATH=gmail-token:latest
```

## Tests

```bash
pytest tests/test_iss011_order_webhook.py -v
```

The reusable handler in `templates/web/order_webhook.py` accepts injectable `send_email_fn` and `create_calendar_event_fn`, so unit tests never touch the network.
