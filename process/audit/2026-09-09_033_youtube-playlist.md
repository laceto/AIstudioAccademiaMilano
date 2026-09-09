---
request_id: "033"
date: "2026-09-09"
intent: youtube_playlist_creation
product_type: unknown_product
outcome: success
price: null
invoice_id: "—"
agents_invoked:
  - name: Stacy
    role: intent_classifier
    action: >
      Classified as youtube_playlist_creation — NOT in the STEP 1 table →
      unknown_product: null. OAuth dependency flagged (write scope, not an API key).
    duration_sec: 3
    status: ok
  - name: Gianni
    role: technical_scoper
    action: >
      YouTube Data API v3 + OAuth2 desktop flow, reusing D007's GOOGLE_CREDENTIALS_JSON
      convention. Identified quota (not rate limit) as the binding constraint.
    duration_sec: 10
    status: ok
  - name: Chiara
    role: implementer
    action: >
      youtube_playlist.py (parsing, quota maths, request bodies, API calls) + main.py CLI
      with --dry-run; 43 tests written before implementation
    duration_sec: 150
    status: ok
  - name: Stacy QA
    role: output_validator
    action: >
      QA passed — 43/43 tests green, no credentials in code, private-by-default,
      lazy imports keep the module testable without the Google libraries
    duration_sec: 8
    status: ok
  - name: Marco
    role: transaction_manager
    action: >
      BLOCKED — product_type unknown_product → price null. Escalated to Luigi.
      Proposed tier 14.90, aligned with calendar_integration (third-party API +
      OAuth integration of comparable scope). Not written to global_settings.json
      pending approval.
    duration_sec: 4
    status: blocked
skills_used:
  - google_oauth2_desktop_flow
  - youtube_data_api_v3
  - quota_budgeting
delivery:
  method: github
  destination: deliverables/2026-09-09_033_youtube-playlist/
  confirmed: true
qa_result: pass
payment:
  amount: null
  method: pending
  receipt_id: "—"
learning_flags:
  new_skills:
    - youtube_data_api_v3
    - quota_budgeting
  new_mcp: []
  risk_score: 2
  cost_overrun: false
  loss_development_flag: false
---

# D033 — YouTube Playlist Builder

## Pricing status — BLOCKED

`youtube_playlist_creation` is not in the STEP 1 intent table, so per CLAUDE.md this is
`unknown_product: null` and Marco blocks invoicing pending Luigi's approval.

**Proposed tier: 14.90**, matching `calendar_integration` — the closest comparable:
a third-party API integration behind an OAuth desktop flow, with a CLI and a reusable
library module. `config/global_settings.json` is deliberately **not** updated until
Luigi confirms.

## What was built

A library plus CLI that creates a YouTube playlist and fills it with videos via the
YouTube Data API v3.

- URL parsing for every common form (watch, youtu.be, shorts, embed, bare ID), with
  channel and playlist URLs rejected rather than guessed at
- Deduplication preserving first-seen order
- Quota accounting as a first-class concern
- Private by default
- Per-video failure isolation

## Design note — quota, not rate limits

The binding constraint is the daily quota, and it is tight enough to change the design.
`playlists.insert` costs 50 units, `playlistItems.insert` costs 50 **per video**, and a
default project gets 10,000 units/day. So `50 + 50N`, and **199 videos is the daily
ceiling**. There is no batch endpoint for playlist items.

That is small enough that discovering it mid-run is a real failure mode: you would end
up with a half-filled playlist and no record of what was missed. Hence `--dry-run`
pricing the run up front, an over-budget warning before anything is created, and a
mid-run stop that lists exactly which videos were not added.

## Testing

43 tests, all offline, written before the implementation per the repo's TDD rule. The
Google client libraries are imported lazily inside `get_service()` (D007's pattern), so
the module imports and every piece of logic is testable without them installed.

**Not verified:** no call has been made against the real YouTube API from this session —
that needs Luigi's Google OAuth consent, which is correctly outside what an agent
session should hold. The API contract is written from Google's documentation.

## Open follow-ups

- Populating a playlist from a `search.list` query (100 units/call — expensive; deferred
  deliberately)
- Wiring into `scripts/digital_presence_pipeline.py` if playlists become part of the
  weekly content cycle
