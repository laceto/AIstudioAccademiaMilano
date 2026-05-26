# The Niccolò Chronicles

A monthly chronicle generator for parents of small children. You drop
voice notes, photos and quick texts into a private WhatsApp chat
("🐣 Niccolò's Time Capsule") whenever something happens. Once a month
you export the chat and feed it to this CLI. Out comes a single,
beautifully structured Markdown file — bind 12 of them and you have a
yearly book.

**Request 024 · 2026-05-26 · `niccolo_chronicles` · €14.90**

## What you get

One file per month named `Niccolo_Age_5_Month_May.md` containing the
four sections from the spec:

1. **📜 The Quote Board ("Niccolò Says")** — every voice note or
   discussion as a verbatim script-style quote. The child's exact
   five-year-old logic is preserved (no grammar fixes, no
   "translation").
2. **🎨 The Art & Creation Catalog** — one entry per photo of a
   drawing, lego build or worksheet, with a 1-2 sentence AI artistic
   review noting medium and one specific developmental observation.
3. **📈 The Development & Habit Tracker** — three lists (milestones,
   challenges, observed habits) and a categorised habit table
   covering Sleep / Food / Friendship / Independence / Language /
   Motor / Emotion / Other.
4. **✉️ A Letter to Future Niccolò** — one warm paragraph addressed
   to the child, capturing the emotional theme of the month from the
   parent's voice.

A real example is committed at
`sample/may-2026-niccolo/Niccolo_Age_5_Month_May.md` — open it to
see the exact layout before you run anything.

## How it works

```
WhatsApp .txt export ──► parsers.parse_chat() ──► [ChatEntry, ...]
                                  │
                                  ▼              (filter_month: keep only May 2026)
                          [ChatEntry, ...]
                                  │
                                  ▼
                       OpenAI gpt-4o (JSON mode)
                                  │
                                  ▼
                       schema-validated payload
                                  │
                                  ▼
                Niccolo_Age_5_Month_May.md  (validated + rendered)
```

The LLM is constrained to OpenAI's `json_object` response format and
a strict schema documented in `prompts.py`. The renderer enforces:

- four sections are always present, in the spec's exact order
- every quote, art entry and habit observation is a non-empty string
- habit categories are restricted to a fixed allowed set
- the letter to future Niccolò is at least one real paragraph
  (≥ 200 chars) and contains no stray Markdown characters (`*`,
  `_`, `#`, backticks) — so it always renders as flowing prose

If the model returns anything malformed, `renderers.validate()` raises
*before* any file is written. No half-written keepsakes.

## The collection workflow (no behaviour change required)

1. Create a private WhatsApp chat with yourself (or with your partner)
   called something like `🐣 Niccolò's Time Capsule`.
2. **Quotes:** hold the mic for 15 seconds and repeat what your child
   just said. Or just type it.
3. **Art & worksheets:** snap a photo, drop it in, type a 2-3-word
   caption ("Giant dinosaur, look at the teeth"). The caption is what
   the AI uses to title and review the piece.
4. **Milestones & tantrums:** type a 5-word message. Don't edit.
   ("Rode bike without training wheels.")
5. End of month: WhatsApp → chat options → **Export chat** → "Without
   media" if you only want the text, "With media" if you want the
   photos archived too.
6. Run this CLI on the resulting `.txt`.

## Install

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...
```

## Usage

```bash
# From a native WhatsApp .txt export
python chronicles.py \
  --chat path/to/chat-export.txt \
  --name Niccolò \
  --age 5 \
  --month 2026-05 \
  --out chronicles/may

# From a CSV (third-party converter)
python chronicles.py \
  --chat path/to/chat-export.csv \
  --name Niccolò --age 5 --month 2026-05

# Try it without an API key — renders a deterministic sample
python chronicles.py --dry-run --name Niccolò --age 5 --month 2026-05
```

Default output folder: `./<name>_<month>/Niccolo_Age_5_Month_<Month>.md`.

The CLI parses the entire export but only the messages from the
requested month are sent to the LLM, so you can keep exporting the
full rolling chat without re-paying for old months.

## Sample output

`sample/may-2026-niccolo/` contains a complete real run:

- `raw_export.txt` — the kind of WhatsApp export the parser eats
  (25 messages, mix of quotes, photo attachments, milestones and
  voice notes).
- `Niccolo_Age_5_Month_May.md` — the rendered chronicle. This is
  byte-for-byte what `python chronicles.py --dry-run --name Niccolò
  --age 5 --month 2026-05` produces. The structure is identical to
  what the live OpenAI mode emits; only the prose is a stub.

## Privacy

This is meant for a private chat with yourself or with one trusted
co-parent. The export sits on your machine. The only outbound call is
to OpenAI when you run a live (non `--dry-run`) generation, and only
the *text* messages from the requested month are sent — never the
attachment files. If you want photo content analysed by the model
(vision mode) that's a deliberate follow-up, not the default.

## Testing

```bash
python -m pytest tests/ -v
```

30 tests covering the parser (WhatsApp `.txt` + CSV, multi-line
messages, attachment extraction, year normalisation, month filtering),
the validator (12 negative cases for malformed payloads), and the
renderer.

## Files

```
deliverables/2026-05-26_024_niccolo-chronicles/
├── chronicles.py              # CLI entrypoint
├── parsers.py                 # WhatsApp / CSV → ChatEntry
├── prompts.py                 # System prompt + JSON contract
├── renderers.py               # Validator + Markdown renderer
├── requirements.txt           # openai
├── README.md                  # This file
├── tests/
│   └── test_chronicles.py     # 30 tests, all pass
└── sample/
    └── may-2026-niccolo/
        ├── raw_export.txt
        └── Niccolo_Age_5_Month_May.md
```

## Follow-ups (not in scope)

- `--vision` flag to ship the actual image files to a vision model
  so the artistic review is based on the drawing, not just the
  caption. Requires uploading photos to OpenAI — gated behind an
  explicit opt-in flag for privacy.
- Six-month or yearly aggregator (`chronicle_year.py`) that takes 12
  monthly files and stitches them into a single coffee-table-book
  Markdown / PDF.
- Cron-driven "first of every month" run that fetches the previous
  month from a WhatsApp Business export endpoint and emails the
  chronicle.
- Sibling support: `--name "Niccolò,Sofia"` to emit two parallel
  chronicles from one shared chat.
- An audio transcription step for cases where the parent only sent a
  voice note (no typed transcript) — whisper-1 on each `PTT-*.opus`.
