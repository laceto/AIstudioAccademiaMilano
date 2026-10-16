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
- No LLM: the sort is deterministic, so there is no API key and no cost.

## Use

```
pip install langgraph langgraph-checkpoint-sqlite
python -m downloads_agent plan      # build a plan and pause (safe to schedule)
python -m downloads_agent show      # print the pending plan
python -m downloads_agent approve   # move the files
python -m downloads_agent reject    # discard the plan
python -m downloads_agent undo      # move the last run's files back
```

Options: `--root`, `--state-dir`, `--min-age-minutes`.

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
- Nothing has been approved on `data/Download` yet; only a plan was built (read-only).
