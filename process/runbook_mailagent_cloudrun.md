# Runbook: Gmail tidy service on Cloud Run (mailagent)

What it does: every hour Cloud Scheduler calls `POST /process` on the private `mailagent` service.
It reads recent inbox mail (headers only), and files newsletters, service notifications and promotions
into Gmail labels with one `batchModify` per label. No model, nothing stored, nothing deleted or sent.

## First deploy (dry run: nothing in the mailbox changes)

1. Token, once, on your laptop: `python -m mailagent auth gmail-luigi` (see `docs/mailagent-auth.md`).
   The OAuth consent screen must be **In production**, not *Testing*: in Testing the refresh token dies after
   7 days and the service stops with `AuthError`.
2. Check locally what it would do: `python -m mailagent tidy --dry-run`. Every line shows label, reason,
   sender, subject. Add any sender you never want touched to `protect:` in `config/mailagent_accounts.yaml`.
3. `bash scripts/deploy_mailagent.sh --dry-run` (prints the commands), then `bash scripts/deploy_mailagent.sh`.
   On Windows: Git Bash; the token is read from `~/.credentials/google/mailagent_gmail-luigi_token.json`
   (`TOKEN_FILE=...` to change it).
4. `gcloud scheduler jobs run mailagent-tidy --location europe-west6`, then read the decisions:
   `gcloud logging read 'resource.labels.service_name="mailagent"' --limit 50 --format='value(jsonPayload)'`

## Go live

`bash scripts/deploy_mailagent.sh --skip-build --live` sets `MAILAGENT_DRY_RUN=0`. From the next hour mail is
filed. Back to dry run: run it again without `--live`.

## Change rules

Edit `config/mailagent_accounts.yaml` (`tidy`, `protect`, `rules`), commit, `bash scripts/deploy_mailagent.sh`
(the file is baked into the image, so a rebuild is needed).

## When something breaks

| Symptom | Cause | Fix |
|--|--|--|
| Scheduler run red, log `AuthError ... token refresh failed` | refresh token revoked or expired (Testing mode, password change) | `python -m mailagent auth gmail-luigi`, then `bash scripts/deploy_mailagent.sh --skip-build` (new secret version) |
| `token lacks scope(s)` | token made with fewer scopes | same as above |
| `HttpError 429` in log | Gmail quota; the client already retried 5 times with backoff | nothing: the mail stays in the inbox and is retried next hour |
| A mail you wanted was archived | heuristic matched (e.g. a bank alert from `no-reply@`) | find it under its label, add the sender to `protect:`, redeploy |

## Undo

Everything filed is under its label (`Newsletter`, `Notifiche`, `Promozioni`): select all there → *Move to Inbox*.
Stop the service: `gcloud scheduler jobs pause mailagent-tidy --location europe-west6`.

## Cost

One instance at most, scale to zero, ~24 short requests a day: inside the Cloud Run free tier. Cloud Scheduler is
free for 3 jobs per billing account (this is the second, after `sweep-stuck-jobs`). One secret, one version.
