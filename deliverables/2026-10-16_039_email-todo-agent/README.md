# Email to-do agent (delivery 039)

Scans each configured mailbox N times a day, turns emails into to-dos, and turns emails that state a
date/time into **calendar proposals**. Nothing is written to a calendar until you approve it.

Code: `mailagent/` · Tests: `tests/test_mailagent.py` · Accounts: `config/mailagent_accounts.yaml`
Plan and Hotmail to-do list: `docs/plans/mailagent-hotmail-todo.md`

## Use

```
python -m mailagent auth gmail-luigi          # once per account (opens a browser)
python -m mailagent scan --dry-run            # extract and print, write nothing
python -m mailagent scan                      # real scan, all enabled accounts
python -m mailagent todos                     # open to-dos
python -m mailagent proposals                 # pending calendar proposals
python -m mailagent approve gmail-luigi:<msg>:e   # create the event
python -m mailagent schedule                  # which hours to fire each account
```

## Add an account
Add a block to `config/mailagent_accounts.yaml` (no code for a known provider type). A new provider type
is one module with `@register_mail("kind")` / `@register_calendar("kind")`.

## State
Built and tested offline: core, Gmail, Google Calendar, CLI. **Not yet run against a real mailbox**, no
Firestore store, no Telegram digest, not deployed. See the to-do list for the order.

Auth: where tokens and keys live, scopes, first sign-in: `docs/mailagent-auth.md`.

## Filing rules
Per account in `config/mailagent_accounts.yaml`: `rules: [{subject_contains|sender_contains, label, archive}]`. A matching mail gets the Gmail label, leaves the inbox (unless `archive: false`) and never reaches the model. `scan --dry-run` only reports what it would file.

One-time sweep of mail already in the inbox: `python -m mailagent sweep --dry-run`, then `python -m mailagent sweep` (uses the same rules; every candidate is re-checked against the rule before filing).

## Tidy (delivery 042)
Newsletters, notifications and promotions filed by header, no model, also on Cloud Run: `python -m mailagent tidy --dry-run`. See `deliverables/2026-10-16_042_mailagent-cloudrun/README.md`.
