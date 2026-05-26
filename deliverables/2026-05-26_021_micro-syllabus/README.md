# Micro-Syllabus & Flashcard Generator

Give it an intimidating learning goal and the minutes you have per day,
get back a 7-day action plan plus an Anki-importable flashcard deck.
Two files, one folder, ready to go.

**Request 021 · 2026-05-26 · `micro_syllabus_flashcards` · €14.90**

## How it works

```
GOAL  +  MINUTES/DAY  ──►  OpenAI (gpt-4o, JSON mode)  ──►  schema-validated payload
                                                                       │
                                          ┌────────────────────────────┴────────────┐
                                          ▼                                         ▼
                                   syllabus.md                              flashcards.csv
                                   7 days × {core, drill, why}              10 RFC-4180-quoted rows,
                                                                            Anki-importable as-is
```

The LLM is constrained to OpenAI's `json_object` response format and a
strict schema documented in `prompts.py`. The renderer enforces:

- exactly 7 days, numbered 1..7
- exactly 10 flashcards, all fields non-empty
- CSV per RFC 4180 (every field quoted, internal `"` doubled)

If the model returns anything malformed, `renderers.validate()` raises
before any file is written.

## Install

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...
```

## Usage

```bash
# Quick start
python micro_syllabus.py --goal "Understand the basics of Docker" --minutes 15

# Pick your own output folder
python micro_syllabus.py -g "Master macro tracking" -m 30 --out plans/macros

# Different goals, different budgets
python micro_syllabus.py -g "Learn conversational Spanish medical terms" -m 20
python micro_syllabus.py -g "Build a morning mobility routine" -m 10

# Offline pipeline test (no API key needed)
python micro_syllabus.py -g "Quantum computing basics" -m 15 --dry-run
```

## Output

Each run produces a folder with two files:

```
<output-dir>/
├── syllabus.md       # 7-day roadmap, sized to your daily time budget
└── flashcards.csv    # 10 conceptual cards, ready for Anki import
```

A worked example (Docker, 15 min/day) lives in
`sample/understand-the-basics-of-docker/`.

## Importing into Anki

1. Anki → File → Import
2. Pick `flashcards.csv`
3. Field separator: **Comma**
4. Field 1 → Front, Field 2 → Back
5. Pick (or create) a deck, then Import

The CSV has no header row, which is what Anki's `.csv` importer expects
by default — no extra configuration needed.

## Files

| File | Purpose |
|---|---|
| `micro_syllabus.py` | CLI entry point |
| `prompts.py` | System prompt + JSON contract |
| `renderers.py` | Validator + Markdown / CSV renderers |
| `requirements.txt` | `openai` |
| `sample/understand-the-basics-of-docker/` | Worked example output |

## Cost note

One generation ≈ 400 input tokens + 1.5–2.5k output tokens against
`gpt-4o`. Swap `--model gpt-4o-mini` for ~15× cheaper runs if you're
generating syllabi at volume.

## Security

- API key from env only — never read from disk, never logged
- No telemetry beyond the OpenAI endpoint
- Goal text is sent to OpenAI exactly once per run; nothing is persisted
  by the script other than the two output files you asked for
