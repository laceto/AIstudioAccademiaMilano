# Audit Log — Format Specification

Every completed user request produces one audit log file in this folder.

---

## File Naming

```
YYYY-MM-DD_NNN_slug.md
```

- `YYYY-MM-DD` — date of the request
- `NNN` — zero-padded sequential request number (001, 002, …)
- `slug` — 2-4 word kebab-case description of the task

**Examples:**
```
2026-05-23_001_bakery-website.md
2026-05-23_002_pdf-email.md
2026-05-24_003_logo-design.md
```

---

## Required Fields

```yaml
request_id:         # NNN
date:               # YYYY-MM-DD
time:               # HH:MM
input_type:         # text | voice | chat
raw_input:          # exact user text/transcript
intent:             # extracted intent label
product_type:       # website | pdf | email | image | report | …

agents_invoked:
  - name:           # agent name
    role:           # role in this request
    duration_sec:   # how long this agent took
    status:         # success | failed | skipped

skills_used:        # list of tools/libraries used
mcp_tools_used:     # list of MCP endpoints called
hooks_fired:        # list of hooks triggered

qa_result:          # pass | fail
qa_notes:           # any issues flagged

payment:
  amount:           # €X.XX
  method:           # card | qr | free
  receipt_id:       # REC-YYYYMMDD-NNN

delivery:
  method:           # url | email | print | download
  destination:      # URL or email address
  confirmed:        # true | false

total_duration_sec: # end-to-end time
outcome:            # success | partial | failed

learning_flags:     # what the learning loop should extract
  new_skills:       # skills seen for the first time
  new_mcp:          # MCP tools seen for the first time
  pattern_match:    # known pattern matched (or "none")
  risk_score:       # 1-5
```

---

## Retention Policy

- Audit logs are kept indefinitely in `process/audit/`
- Logs older than 90 days are compressed into monthly summary files
- PII (email addresses, payment details) is redacted after 30 days
