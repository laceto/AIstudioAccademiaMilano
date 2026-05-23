# Projects — Submodule Directory

> Purpose: Holds Git submodule pointers for standalone deliverable project repos.
> Owner Agent: Francesca (Delivery)
> Status: active

## Convention

Each deliverable project that warrants its own repo is registered here as a Git submodule
and tracked in [`ProjectRegistry.md`](../ProjectRegistry.md).

## Add a New Project

```bash
# 1. Create the GitHub repo (name: AIstudio_Project_<timestamp>)
# 2. Add as submodule
git submodule add <repo-url> projects/<project-name>
# 3. Register in ProjectRegistry.md
# 4. Scaffold docs per docs-rules.md
```

## Naming

Repos must be named: `AIstudio_Project_<timestamp>` (e.g., `AIstudio_Project_20260524`)

## Current Submodules

No submodules registered yet.
Monorepo deliverables (001–007) pre-date this convention and live in `deliverables/`.
