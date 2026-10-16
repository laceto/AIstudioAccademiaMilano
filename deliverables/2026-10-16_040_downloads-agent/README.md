# Downloads agent (D040)

LangGraph agent that keeps the `data/Download` folder of this repo tidy. It never deletes anything.
The folder holds personal files, so `data/Download/` is git-ignored; change it with `--root`.

```
START -> plan -> (nothing to move? END) -> [pause: human approval] -> execute -> END
```

- **plan** scans the top level of `data/Download` only (subfolders are never touched) and groups files by
  extension into `Documents`, `Images`, `Video`, `Audio`, `Archives`, `Installers`.
  It skips partial downloads (`.crdownload`, `.part`, ...), files modified in the last 10 minutes,
  unknown extensions and `desktop.ini`.
- **execute** runs only after `decision == "approved"` (graph compiled with `interrupt_before=["execute"]`).
  Name clashes become `name (1).ext`; nothing is overwritten. Every run is written to `journal.jsonl`.
- State (SQLite checkpoints, pending plan, journal) lives in `%LOCALAPPDATA%\downloads_agent`.
- The sort itself is deterministic (no LLM). Summaries are an add-on, see below.

## Summaries

`plan` adds a one-sentence summary of what each readable document is about (pdf, docx, txt, md, csv,
xls, xlsx), using a **local** Ollama model (`gemma2:2b` by default), so file text never leaves the PC.
Images, installers, archives and video get a type note only; their content is not read.

- The model sees only the first ~3000 characters of a file, and treats them as untrusted data. It has no
  tools and never influences what is moved.
- Summaries show under each file in `plan` / `show`, and in a local report:
  `%LOCALAPPDATA%\downloads_agent\summary.html` (HTML-escaped, loads nothing from the network).
- Results are cached by path, size and modification time, so reruns only summarize new or changed files.
- If Ollama is not running the plan still works; summaries say so.
- A small model gives short, generic summaries and can be wrong (it described an xlsx of HbA1c data as
  "a list of data, likely medical"). Use `--model` with a bigger pulled model for better results.
- About 7 seconds per document on this PC; the first full run of ~70 documents takes around 10 minutes.
  Use `--max-summaries N` to spread it over several runs.

## Use

```
pip install langgraph langgraph-checkpoint-sqlite ollama pypdf python-docx openpyxl xlrd
python -m downloads_agent plan      # build a plan and pause (safe to schedule)
python -m downloads_agent show      # print the pending plan
python -m downloads_agent approve   # move the files
python -m downloads_agent reject    # discard the plan
python -m downloads_agent undo      # move the last run's files back
```

Options: `--root`, `--state-dir`, `--min-age-minutes`, `--no-summary`, `--model`, `--max-summaries`.

## Schedule (Windows Task Scheduler)

Scheduling only runs `plan`, so the worst case is a plan waiting for you. Not installed automatically;
run it yourself (replace the repo path):

```
schtasks /Create /SC DAILY /ST 09:00 /TN "DownloadsAgentPlan" /TR "cmd /c cd /d C:\Users\l_ace\Desktop\projects\AIstudioAccademiaMilano && python -m downloads_agent plan >> %LOCALAPPDATA%\downloads_agent\plan.log 2>&1"
```

Remove with `schtasks /Delete /TN DownloadsAgentPlan /F`. Read `plan.log` or run `show`, then `approve`.

## Not built

- No notification when a plan is waiting (the log file is the only signal).
- Empty category folders stay after `undo`.
- Nothing has been approved on `data/Download` yet; only plans were built (read-only).
- Scanned PDFs without a text layer get "no extractable text" (no OCR); files over 50 MB are not read.
- Image descriptions would need a vision model, which is not installed.
