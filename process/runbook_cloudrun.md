# Runbook — Deploying the Telegram Channels to Google Cloud Run

**Why Cloud Run:** the always-free tier is 2M requests, 180,000 vCPU-seconds and
360,000 GiB-seconds per month in select US regions, never expiring, commercial use
allowed. At studio volume (tens of messages a day) that is a rounding error — this
genuinely costs €0 in hosting.

**What it is not:** free to *run*. Every classification and every RAG answer is a paid
OpenAI/Anthropic call. That bill follows you to any host.

---

## The one thing Cloud Run changes about the code

Cloud Run **scales to zero** and freezes the container the moment a response is sent.
`gateway/api.py` used to start the QueueWorker as a background asyncio task — on Cloud Run
that loop stops the instant the webhook returns. The user would get "Job ID: …" and never
hear back. That is exactly the half-broken behaviour already visible in the
2026-05 Telegram screenshots.

Fixed by `GATEWAY_SYNC_REPLY=1`, which makes the webhook classify **inside the request**
and send the real answer before returning:

| `GATEWAY_SYNC_REPLY` | Behaviour | Use for |
|---|---|---|
| unset / `0` | ack now, background worker replies later | laptop, always-on VM, Railway |
| `1` | classify inline, single complete reply | **Cloud Run**, any scale-to-zero host |

The RAG API needed no change — `scripts/rag/api_server.py:/webhook/telegram` already
produces its answer inside the request.

---

## Architecture on Cloud Run

Two services, both webhook-driven, both scaling to zero:

```
Telegram ──POST──► gateway (gateway/Dockerfile)      GATEWAY_SYNC_REPLY=1
                     └─ classify inline ──► sendMessage

Telegram ──POST──► rag-api (scripts/rag/Dockerfile)  FAISS index baked into image
                     └─ answer inline ──► sendMessage
```

No polling, so **nothing runs between messages** — which is precisely why it's free.

---

## Step 1 — Project and prerequisites

Cloud Run's free tier still requires a billing account attached; you are simply not
charged while inside the limits.

```bash
gcloud auth login
gcloud projects create aistudio-milano --name="AI Studio Milano"
gcloud config set project aistudio-milano
# then attach billing in the Console: Billing → Link a billing account

gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
                       artifactregistry.googleapis.com secretmanager.googleapis.com

gcloud artifacts repositories create aistudio \
  --repository-format=docker --location=us-central1
```

> **Region matters.** The always-free allowance applies to select US regions —
> `us-central1` is the safe default. Deploying to `europe-west*` is closer to Milan but
> may fall outside the free tier; confirm against Google's current list before switching.

---

## Step 2 — Secrets

Do not pass tokens with `--set-env-vars`; they end up readable in the service description.

```bash
for S in TELEGRAM_BOT_TOKEN TELEGRAM_RAG_BOT_TOKEN OPENAI_API_KEY ANTHROPIC_API_KEY; do
  printf '%s' "$(grep "^$S=" .env | cut -d= -f2-)" | \
    gcloud secrets create "$S" --data-file=- 2>/dev/null || \
  printf '%s' "$(grep "^$S=" .env | cut -d= -f2-)" | \
    gcloud secrets versions add "$S" --data-file=-
done
```

Grant the runtime service account read access:

```bash
PROJECT_NUMBER=$(gcloud projects describe "$(gcloud config get-value project)" --format='value(projectNumber)')
for S in TELEGRAM_BOT_TOKEN TELEGRAM_RAG_BOT_TOKEN OPENAI_API_KEY ANTHROPIC_API_KEY; do
  gcloud secrets add-iam-policy-binding "$S" \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role=roles/secretmanager.secretAccessor
done
```

---

## Step 3 — Build both images

The repo has two Dockerfiles, so the build config names the right one explicitly —
the same trap that would otherwise bring the gateway back up running the RAG API.

```bash
REGION=us-central1
PROJECT=$(gcloud config get-value project)
REPO=$REGION-docker.pkg.dev/$PROJECT/aistudio

gcloud builds submit --config deploy/cloudbuild.gateway.yaml \
  --substitutions _IMAGE=$REPO/gateway

gcloud builds submit --config deploy/cloudbuild.ragapi.yaml \
  --substitutions _IMAGE=$REPO/rag-api
```

The RAG image is the slow one — faiss-cpu and the langchain stack. Give it the full
30-minute timeout the config already sets.

---

## Step 4 — Deploy

```bash
gcloud run deploy gateway \
  --image $REPO/gateway --region $REGION \
  --allow-unauthenticated --memory 512Mi --timeout 120 \
  --set-env-vars GATEWAY_SYNC_REPLY=1,GATEWAY_QUEUE_DIR=/tmp/queue \
  --set-secrets TELEGRAM_BOT_TOKEN=TELEGRAM_BOT_TOKEN:latest,ANTHROPIC_API_KEY=ANTHROPIC_API_KEY:latest,OPENAI_API_KEY=OPENAI_API_KEY:latest

gcloud run deploy rag-api \
  --image $REPO/rag-api --region $REGION \
  --allow-unauthenticated --memory 2Gi --cpu 2 --timeout 300 --cpu-boost \
  --set-secrets TELEGRAM_RAG_BOT_TOKEN=TELEGRAM_RAG_BOT_TOKEN:latest,OPENAI_API_KEY=OPENAI_API_KEY:latest
```

`--allow-unauthenticated` is required: Telegram's servers call these URLs and cannot
authenticate. `--cpu-boost` on the RAG service shortens the cold start that loads FAISS.

Wire the gateway's `/ask` proxy to the RAG service:

```bash
RAG_URL=$(gcloud run services describe rag-api --region $REGION --format='value(status.url)')
gcloud run services update gateway --region $REGION --set-env-vars RAG_API_URL=$RAG_URL
```

---

## Step 5 — Register the webhooks

Two bots, two services, **two different tokens** — mixing them is what broke the channel
in the first place.

```bash
GW_URL=$(gcloud run services describe gateway --region $REGION --format='value(status.url)')

# pipeline bot → gateway
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook?url=$GW_URL/webhook/telegram&drop_pending_updates=true"

# RAG bot → rag-api  (the script refuses if the two tokens match)
TELEGRAM_RAG_BOT_TOKEN=... RAILWAY_URL=$RAG_URL python scripts/rag/register_telegram_webhook.py
```

Verify:

```bash
python scripts/check_telegram.py --expect-webhook pipeline
```

Both bots should now report webhook mode, pointing at their own service, 0 pending, no
last error.

---

## Step 6 — Test

Message the pipeline bot: `Ho bisogno di una landing page per il mio ristorante`.
You should get **one** message containing the product and €9.90 — not a Job ID followed
by silence. If you get the Job ID form, `GATEWAY_SYNC_REPLY` did not reach the container.

```bash
gcloud run services logs read gateway --region $REGION --limit 50
```

---

## Known trade-offs

**Cold starts.** After idle, the first message pays container startup. The gateway is
quick; the RAG service loads FAISS and the langchain stack and can take tens of seconds.
Telegram retries a webhook it considers timed out, which can produce a duplicate answer.
`--cpu-boost` helps. `--min-instances=1` removes it entirely but leaves an instance
running — that is billable and drops you out of the free tier.

**Job history is ephemeral.** Cloud Run's filesystem is per-instance and in-memory;
`GATEWAY_QUEUE_DIR=/tmp/queue` disappears with the instance. Sync mode completes each job
within its request so nothing is lost mid-flight, but `GET /status/{job_id}` will 404 once
the instance is gone. Persisting history needs Firestore or Cloud SQL — not built.

**No polling.** The polling bots (`gateway/bot_telegram.py`, `gateway/rag_bot_telegram.py`)
are for the laptop setup and play no part here. Running one against a bot whose webhook is
registered gets a 409 and silence.

**Streamlit form and WhatsApp** can be deployed to Cloud Run too — both are HTTP — but
neither is covered by this runbook.

---

## Rolling back to the laptop

Delete the webhooks and start the local stack — the two setups are mutually exclusive per
bot, never run both:

```bash
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/deleteWebhook?drop_pending_updates=true"
curl "https://api.telegram.org/bot$TELEGRAM_RAG_BOT_TOKEN/deleteWebhook?drop_pending_updates=true"
python scripts/run_local_stack.py
```

See `process/runbook_local_telegram_stack.md`.
