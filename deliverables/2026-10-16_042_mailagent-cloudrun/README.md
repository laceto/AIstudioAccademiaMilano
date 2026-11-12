# Gmail tidy on Cloud Run (delivery 042)

Extends the email agent (`mailagent/`, delivery 039) with a **tidy** mode that runs on Cloud Run: newsletters,
service notifications and promotions get a Gmail label and leave the inbox. Header rules, no model.

| File | What |
|--|--|
| `mailagent/classifier.py` | the decision: protect list → explicit rules → Gmail Promotions → `List-Unsubscribe`/`List-Id`/`Precedence: bulk` → `no-reply@`/`notifications@`/`Auto-Submitted` |
| `mailagent/pipeline.py` `tidy_account` | groups decisions by label, one `batchModify` (≤1000 ids) each; a failing batch does not stop the others |
| `mailagent/providers/gmail.py` | `tidy_candidates` (headers only), `modify_many` (label, archive, mark read); every call retries 429/5xx with backoff (`num_retries=5`) |
| `mailagent/server.py` | FastAPI `POST /process`, `GET /healthz`; private service, JSON logs for Cloud Logging |
| `mailagent/Dockerfile`, `mailagent/requirements.txt`, `deploy/cloudbuild.mailagent.yaml` | image |
| `scripts/deploy_mailagent.sh` | APIs, service accounts, token → Secret Manager, build, deploy, invoker IAM, Scheduler (hourly) |
| `process/runbook_mailagent_cloudrun.md` | deploy, go live, rules, failures, undo |
| `tests/test_mailagent_tidy.py` | 22 offline tests |

## Safe by default
- `MAILAGENT_DRY_RUN=1` is the default in the image and in the deploy script: the first runs only log what they
  would file. A request body can make a run safer (`{"dry_run": true}`), never the opposite.
- Never touched: starred mail, mail younger than 60 minutes (2FA codes, reset links), senders in `protect:`.
- No delete, no send, no body read. Undo = move the label's mail back to the inbox.

## Use
```
python -m mailagent tidy --dry-run           # locally: every decision with its reason
bash scripts/deploy_mailagent.sh --dry-run   # print the gcloud commands
bash scripts/deploy_mailagent.sh             # deploy, dry run on
bash scripts/deploy_mailagent.sh --skip-build --live   # really file mail
```

## Choices vs the original brief
- **Scheduler, not Pub/Sub `watch`**: for newsletters an hourly pass is enough; `watch` needs renewing every
  7 days, a topic, a push subscription and history-id bookkeeping. Can come later on the same `/process` logic.
- **OAuth user token, not domain-wide delegation**: a personal @gmail.com account has no Workspace domain.
- **uvicorn alone, Python 3.12-slim**: same as the repo's other Cloud Run images; one request at a time.
- The to-do scan (`scan`, needs the model and a store) is **not** on Cloud Run yet: it needs `FirestoreStore` (G2).

## State
Tested offline (fake Gmail) and as a server in a clean venv with only the image's files (`/healthz`, `/process`
returning 500 + JSON log without a token). **Not deployed, no real Docker build** (no Docker daemon in the
session), **not run against the real mailbox**.
