# Deliverable 009 — LinkedIn Post Generator from GitHub Activity

> Purpose: Reads recent commits and releases from any GitHub repo and generates a ready-to-publish LinkedIn post in Luigi's voice using Claude.
> Owner Agent: Chiara (Implementation)
> Status: active

## Credentials Required

| Credential | Required | Where to get it |
|---|---|---|
| `ANTHROPIC_API_KEY` | **Yes** — generates the post | [console.anthropic.com](https://console.anthropic.com) → API Keys |
| `GITHUB_TOKEN` | Recommended (optional) | [github.com/settings/tokens](https://github.com/settings/tokens) — scope: `public_repo` |

- Without `ANTHROPIC_API_KEY`: the tool cannot run.
- Without `GITHUB_TOKEN`: works, but limited to 60 API requests/hour (fine for occasional use).

---

## Setup

### 1. Set credentials

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export GITHUB_TOKEN=ghp_...        # optional
```

### 2. Install

```bash
pip install -r requirements.txt
```

---

## Run

### Basic
```bash
python main.py --repo laceto/hello-world
```

### Copy to clipboard
```bash
python main.py --repo laceto/hello-world --copy
```

### Custom lookback window
```bash
python main.py --repo laceto/hello-world --days 60
```

### Save to a specific file
```bash
python main.py --repo laceto/aistudioaccademiamilano --output post_today.txt
```

### Pass credentials explicitly (no env vars)
```bash
python main.py --repo laceto/hello-world --api-key sk-ant-... --token ghp_...
```

---

## Output

- Post saved to `linkedin_post.txt` (or `--output` path)
- Post printed to terminal
- Optional clipboard copy with `--copy`

---

## Luigi's Voice — Post Structure

| Part | Example |
|---|---|
| Hook | "I just shipped X." |
| What it does | Plain English, 2-4 sentences |
| Why it matters | 2-3 honest sentences |
| Insight | One real observation about building with AI |
| Hashtags | 3-5 relevant tags |

Target length: 150-250 words.
Never: "excited to announce", "leverage", "ecosystem", "game-changer".

---

## Works on any public GitHub repo

```bash
python main.py --repo microsoft/vscode --days 7
python main.py --repo huggingface/transformers --days 14
python main.py --repo laceto/hello-world
```

The tool uses the GitHub REST API directly — no MCP or OAuth needed for public repos.
