# Mind Dashboard — Daily AI Briefing

Turn a day of raw, messy thoughts into a structured, objective briefing:
TL;DR, metric table, categorized log, one specific insight, and tomorrow's
top 3. Markdown and/or HTML output, one file per day.

**Request 020 · 2026-05-26 · `mind_dashboard_journal` · €9.90**

## How it works

```
raw journal text  ──►  Claude (claude-opus-4-7)  ──►  JSON schema  ──►  Markdown / HTML
   (one .txt or                strict system                              YYYY-MM-DD_Briefing.md
    stdin pipe)                prompt, no prose                           YYYY-MM-DD_Briefing.html
```

The model is constrained to return a single JSON object matching the
schema in `prompts.py`. `templates.py` renders it deterministically, so
the layout never drifts and the LLM cannot leak free-form text past the
JSON boundary.

## Install

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
```

## Usage

```bash
# Markdown briefing for today from a file
python mind_dashboard.py --input today.txt

# HTML and Markdown into a folder, with a custom date
python mind_dashboard.py -i today.txt -f both -o briefings/ --date 2026-05-26

# Pipe from anywhere (e.g. transcribed audio via whisper-cli)
whisper-cli today.m4a --output-txt - | python mind_dashboard.py -f html

# Offline stub for testing the pipeline without burning tokens
python mind_dashboard.py -i sample/journal.txt --dry-run
```

## Output

Strict 5-section layout, every day:

- ⚡ **The TL;DR** — 2 sentences, witty, concrete
- 📊 **Metric Extraction** — 4–7 row markdown table
- 🏷️ **Categorized Log** — Wins · Tasks Completed · Anxieties / Backlog
- 💡 **The AI Insight** — one observation that ties two patterns together
- 🌱 **Tomorrow's Top 3** — ranked by impact on clearing the backlog

See `sample/2026-05-26_Briefing.md` and `sample/2026-05-26_Briefing.html`
for a worked example built from `sample/journal.txt`.

## Files

| File | Purpose |
|---|---|
| `mind_dashboard.py` | CLI entry point |
| `prompts.py` | System prompt + JSON schema contract |
| `templates.py` | Markdown / HTML renderers + schema validator |
| `requirements.txt` | `anthropic` |
| `sample/journal.txt` | Example raw input |
| `sample/2026-05-26_Briefing.{md,html}` | Example output |

## Cost note

One day's briefing ≈ 500–800 input tokens + 600 output tokens against
`claude-opus-4-7`. Swap `--model claude-haiku-4-5-20251001` for a ~10×
cheaper run if you process a backlog of journals.

## Security

- API key from env only — never written to disk, never logged
- No telemetry, no network calls beyond the Anthropic endpoint
- Input journal is never stored by the script; the briefing is written
  locally to the path you choose
