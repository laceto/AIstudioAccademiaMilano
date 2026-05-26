# The Family Archivist — Weekly Storyteller

A single-file HTML app for retirees who want to leave a digital heirloom
of stories for children and grandchildren. They talk or type a memory;
the Archivist returns a polished Markdown narrative and a clean JSON
metadata file — one keepsake per session, designed to be repeated weekly.

**Request 022 · 2026-05-26 · `family_archivist` · €14.90**

## What you get

Per session, two files ready to keep, print, or upload to a family
archive:

- `story_archive.md` — the polished narrative with:
  - An evocative classic title
  - The story itself (fillers and stutters removed, the storyteller's
    voice and phrasing preserved)
  - 🌍 *In Those Days* — historical context from that exact year
  - 💡 *The Takeaway* — the 1–2 sentence wisdom embedded in the story
  - The photograph (optional) embedded inline in the preview
- `memory_metadata.json` — a clean schema for any digital archive:
  ```json
  {
    "schema_version": "1.0",
    "archived_at": "2026-05-26T...",
    "title": "...", "year": "1974", "location": "...",
    "storyteller": "...", "subject": "...",
    "tags": ["decade:1970s", "year:1974", ...],
    "composition_mode": "local | anthropic | openai",
    ...
  }
  ```

## How it works

```
voice  ──►  Web Speech API  ──►  textarea  ──►  Compose
                                                   │
                                       ┌───────────┴───────────┐
                                       ▼                       ▼
                                 Local mode             AI mode (Claude / GPT)
                                 (deterministic         (richer narrative,
                                  polish + canned        real historical lookup)
                                  decade context)
                                       │                       │
                                       └───────────┬───────────┘
                                                   ▼
                                 story_archive.md  +  memory_metadata.json
```

## Two modes

### Local mode (default)
Runs entirely in the browser. Strips verbal fillers (`um`, `uh`, `you
know`, repeated stutters), normalises capitalisation and spacing, splits
sentences into paragraphs, and emits a canned-but-real historical
snippet for the decade you specify. No API key, no internet calls.

Good for: privacy-first capture, no-API-key setup, demo use, situations
where the family just wants the story cleaned up.

### AI mode (Claude or OpenAI)
Paste an API key. The Archivist sends the raw memory plus your optional
details to the chosen model with a strict JSON contract. The model
returns a richer narrative (still preserving the storyteller's voice)
and looks up authentic historical context for the year and place.

Keys stay in the browser — they're only sent to the chosen provider's
endpoint, never to any AI Studio service.

- **Claude**: `claude-sonnet-4-6`, direct browser access enabled
- **OpenAI**: `gpt-4o` with `response_format: json_object`

## Running it

Open `index.html` in any modern browser (Chrome, Edge, Safari).

For voice input the browser will ask for microphone access; allow it
and speak naturally.

To deploy: copy the single file anywhere static — GitHub Pages, Netlify,
or just open it from disk.

## Why this fits a retiree

1. **Low friction, high meaning** — talk naturally, get a printable
   keepsake.
2. **Repeatable weekly** — twenty stories in five months becomes a
   physical book.
3. **Two-mode design** — no API key needed to start (local mode is
   genuinely useful), but the AI mode unlocks richer history when ready.
4. **Built for sharing** — Markdown drops cleanly into a family group
   chat, a Notion archive, a digital family tree, or a printed PDF.

## Sample output

See `sample/` for a real keepsake generated from a 1974 Fiat road-trip
memory:

- `sample/raw_input.txt` — the unedited dictation
- `sample/story_archive.md` — the polished keepsake
- `sample/memory_metadata.json` — the metadata file

## Files

```
deliverables/2026-05-26_022_family-archivist/
├── index.html                     # The entire app
├── README.md                      # This file
└── sample/
    ├── raw_input.txt
    ├── story_archive.md
    └── memory_metadata.json
```

## Follow-ups (not in scope)

- ZIP download bundling both files plus the original photo
- "Family book" mode: take a folder of metadata JSONs and produce a
  bound PDF index
- Whisper API integration for higher-quality transcription in non-English
  dialects where the Web Speech API is weak
- Tag-driven family tree linking once `memory_metadata.json` files
  accumulate
