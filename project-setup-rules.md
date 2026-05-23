# Project Setup Rules

## Context
You are spinning up a new deliverable project repo.

## Repository Convention
1. Name: `AIstudio_Project_<timestamp>` (e.g., `AIstudio_Project_20260523`)
2. Create the repo on GitHub
3. Add it as a Git submodule in this central repo
4. Register it in `ProjectRegistry.md` (create the file if it doesn't exist yet)

## ProjectRegistry.md Entry Format
```
| Project | Repo | Owner Agent | Status | Date |
|---|---|---|---|---|
| <name> | <github-url> | <agent> | active/archived | <date> |
```

## Submodule Command
```
git submodule add <repo-url> projects/<project-name>
```

## When Done
→ Repo created and linked as submodule  
→ `ProjectRegistry.md` updated  
→ LOAD: `docs-rules.md` to scaffold the project's initial documentation
