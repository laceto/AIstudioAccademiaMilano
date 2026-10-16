# Email agent: Hotmail/Outlook and next steps

Status 2026-10-16: core + Gmail built (`mailagent/`, `tests/test_mailagent.py`). This file is the to-do list
for adding Hotmail and for the remaining gaps. Tick items as they land.

## How a new account plugs in

| You want | You do |
|----------|--------|
| Another Gmail address | Add a block to `config/mailagent_accounts.yaml`, run `python -m mailagent auth <id>`. No code. |
| Another Hotmail/Outlook address | Same, once the `outlook` provider below exists. |
| A new kind of provider (iCloud, IMAP, ...) | One module in `mailagent/providers/` with `@register_mail("kind")` (+ `@register_calendar`), one import line in `_load_builtin()`. The pipeline is untouched. |

## Hotmail / Outlook.com (Microsoft Graph, personal account)

### Luigi (only you can do these)
- [ ] H1. Register an app at entra.microsoft.com -> App registrations -> New. Supported account types: **"Personal Microsoft accounts only"** (or "any org + personal"). Redirect URI: none needed for device-code login; enable **Allow public client flows**.
- [ ] H2. API permissions (Microsoft Graph, *Delegated*): `Mail.Read`, `Calendars.ReadWrite`, `offline_access`, `User.Read`. No admin consent needed for personal accounts.
- [ ] H3. Copy the **Application (client) ID** into `.env` as `MSGRAPH_CLIENT_ID` (and the secret store for Cloud Run). No client secret: public client.

### Code (Claude)
- [ ] H4. Test first: `tests/test_mailagent_outlook.py` with a fake Graph HTTP layer (message JSON -> `Email`, `$filter=receivedDateTime ge ...`, paging via `@odata.nextLink`, HTML body -> text, 401 -> `AuthError`).
- [ ] H5. `mailagent/providers/ms_auth.py`: MSAL `PublicClientApplication`, authority `consumers`, device-code flow for `auth <id>`, serialized token cache (file locally, env/Secret Manager on Cloud Run), silent refresh.
- [ ] H6. `mailagent/providers/outlook.py`: `OutlookProvider.list_new` (GET `/me/mailFolders/inbox/messages`, `Prefer: outlook.body-content-type="text"`, `$top`, `$orderby=receivedDateTime desc`) registered with `@register_mail("outlook")`.
- [ ] H7. `OutlookCalendarProvider.create_event` / `find_conflicts` (POST `/me/events`, GET `/me/calendarView`) registered with `@register_calendar("outlook")`; reuse the proposal -> body mapping idea from `google_calendar.event_body`.
- [ ] H8. Uncomment the `hotmail-luigi` block in `config/mailagent_accounts.yaml`, `enabled: true`; add the import to `_load_builtin()`.
- [ ] H9. Live dry-run: `python -m mailagent scan --account hotmail-luigi --dry-run`, read the output, then a real scan.
- [ ] H10. Update `config/accounts_registry.yaml`, `credentials/registry.md`.

Notes: the same refresh-token expiry rules apply (personal-account refresh tokens last ~90 days of inactivity; a scan 4x/day keeps it alive). Mail content is untrusted input: the extractor already treats it as data.

## Remaining work on the Gmail/core side
- [x] G1. (2026-10-16, done: 36 emails read, 0 errors; added ignore rules and a no-invented-due-dates prompt. Event proposals not yet seen live: no email with a date/time in the sample.) **Live check on Gmail**: run `auth gmail-luigi` (needs `credentials/google_credentials.json` from Google Cloud Console, Desktop OAuth client, Gmail API + Calendar API enabled), then `scan --dry-run`; tune the extractor prompt on real mail.
- [ ] G2. `FirestoreStore` with the same methods as `JsonStore` (Cloud Run disk is ephemeral; reuse the `FIRESTORE_*` conventions in `gateway/jobstore.py`). Select with `MAILAGENT_STORE=file|firestore`.
- [ ] G3. Digest + approval over Telegram: after each scan send Luigi new to-dos and the pending event proposals with Approve/Reject buttons (pattern: `gateway/notify.py`, `gateway/admin_telegram.py`, his ID only). Until then approval is `python -m mailagent approve <id>`.
- [ ] G4. Conflict check before proposing (`find_conflicts`) and show it on the proposal card.
- [ ] G5. Cloud Run **job** (not service) + Cloud Scheduler: one cron per `scan_hours()` slot (`python -m mailagent schedule` prints them), tokens in Secret Manager, `Dockerfile.mailagent`, cloudbuild yaml, runbook.
- [ ] G6. Retention for stored to-dos (email subjects/senders are personal data): reuse `gateway/retention.py` idea, add expiry on done/rejected items.
- [ ] G7. Mark a to-do done / snooze (`python -m mailagent done <id>`). (Noise senders: `ignore_senders` / `ignore_subjects` per account already exist.)
