# mailagent: where the authentication lives

No secret is in the repo. Everything below is on Luigi's machine (or in Cloud Run secrets later).

| What | Where | Used for |
|------|-------|----------|
| Google OAuth **client** (Desktop app) | `C:/Users/l_ace/.credentials/google/credentials.json` (also `.env` -> `GOOGLE_CREDENTIALS_JSON`) | identifies the app to Google; needed once per account to sign in |
| Google **token** for the agent, per account | `C:/Users/l_ace/.credentials/google/mailagent_<account-id>_token.json` (created by `auth`, owner-only) | what the scan uses every time; refreshes itself |
| Same token as an env var (Cloud Run) | env var named in `options.token_env`, e.g. `MAILAGENT_GMAIL_LUIGI_TOKEN`, holding the token JSON | headless runs; takes priority over the file |
| OpenAI key | `.env` -> `OPENAI_API_KEY` (loaded by the CLI) | the model that reads each email |

The paths are set per account in `config/mailagent_accounts.yaml` (`options.token_file`, `options.credentials_file`).
The existing `GOOGLE_TOKEN_JSON` file (`google_token.json`) is not reused: it was made for other scopes, and the agent needs
Gmail read-only plus Calendar events, so it gets its own token file.

## Scopes requested
`gmail.readonly`, `calendar.events`, `calendar.readonly`. The agent cannot send, delete or label mail.

## First sign-in (once per account)
1. In Google Cloud Console, for the project that owns the client above, enable the **Gmail API** and the **Google Calendar API**.
2. If the OAuth consent screen is in *Testing*, add the Gmail address as a test user (tokens then expire after 7 days; publish the app to avoid that).
3. Run `python -m mailagent auth gmail-luigi`. A browser opens; approve. The token file appears at the path above.
4. Check: `python -m mailagent scan --dry-run`.

If a token stops working, the scan reports `[gmail-luigi] token refresh failed ... re-run auth` for that account only; re-run step 3.

## Adding another account
Add a block to `config/mailagent_accounts.yaml` with its own `id` and `token_file` (same `credentials_file` is fine), then run `auth <id>`.
Hotmail/Outlook uses a different client (Azure app) and token cache: see `docs/plans/mailagent-hotmail-todo.md`.

Secrets rule (CLAUDE.md): tokens are never committed or logged. `.gitignore` also covers `credentials/mailagent_*_token.json` and `data/mailagent/`.
