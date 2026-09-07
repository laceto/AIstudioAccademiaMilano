"""
Telegram channel doctor — AI Studio Accademia Milano

Answers "are the Telegram channels working?" without guessing. For every
configured bot token it asks Telegram itself:

  getMe          — is the token valid, and which bot is it?
  getWebhookInfo — is this bot in webhook mode or polling mode, are updates
                   piling up, did Telegram record a delivery error?

and then checks the combination against how this repo is wired:

  TELEGRAM_BOT_TOKEN      → pipeline bot, consumed by `gateway.bot_telegram`
                            via run_polling() (getUpdates). A webhook set on
                            this bot silently starves the poller: Telegram
                            refuses getUpdates with 409 while a webhook lives.
  TELEGRAM_RAG_BOT_TOKEN  → RAG bot, answered by scripts/rag/api_server.py
                            at POST /webhook/telegram. Needs a webhook.

Usage:
    python scripts/check_telegram.py
    python scripts/check_telegram.py --expect-webhook pipeline   # gateway.api deploy

Exit code 0 = healthy, 1 = at least one ERROR. Tokens are never printed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.telegram.org"

# Same .env loading convention as gateway/bot_telegram.py
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
if _ENV_FILE.exists():
    for _line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

# role -> (env var, what consumes its updates, does it need a webhook?)
BOTS = {
    "pipeline": ("TELEGRAM_BOT_TOKEN", "gateway.bot_telegram (polling)", False),
    "rag": ("TELEGRAM_RAG_BOT_TOKEN", "scripts.rag.api_server /webhook/telegram", True),
}


def _call(token: str, method: str) -> dict:
    """Call a Telegram Bot API method. Never raises — returns {'ok': False, ...}."""
    try:
        with urllib.request.urlopen(f"{API}/bot{token}/{method}", timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            return json.loads(exc.read().decode("utf-8"))
        except Exception:
            return {"ok": False, "description": f"HTTP {exc.code}"}
    except Exception as exc:
        return {"ok": False, "description": f"{type(exc).__name__}: {exc}"}


def _bot_id(token: str) -> str:
    """Public numeric prefix of a bot token — safe to print, unlike the secret half."""
    return token.split(":", 1)[0] if ":" in token else "?"


def _ts(epoch) -> str:
    if not epoch:
        return "—"
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def check(role: str, expect_webhook: set[str], errors: list[str], warnings: list[str]) -> None:
    env_var, consumer, wants_webhook = BOTS[role]
    if role in expect_webhook:
        wants_webhook = True
    token = os.environ.get(env_var, "").strip()

    print(f"\n── {role} bot  ({env_var})")
    print(f"   consumed by: {consumer}")

    if not token or token.startswith("your-"):
        print("   token:       MISSING")
        errors.append(f"{env_var} is not set — the {role} bot cannot run at all.")
        return

    me = _call(token, "getMe")
    if not me.get("ok"):
        print(f"   token:       INVALID — {me.get('description', 'unknown error')}")
        errors.append(f"{env_var} rejected by Telegram: {me.get('description')}")
        return

    username = me["result"].get("username", "?")
    print(f"   bot:         @{username}  (id {_bot_id(token)})")

    info = _call(token, "getWebhookInfo")
    if not info.get("ok"):
        errors.append(f"{role}: getWebhookInfo failed — {info.get('description')}")
        return

    r = info["result"]
    url = r.get("url") or ""
    pending = r.get("pending_update_count", 0)
    last_err = r.get("last_error_message")

    print(f"   mode:        {'webhook → ' + url if url else 'polling (no webhook)'}")
    print(f"   pending:     {pending} update(s)")
    if last_err:
        print(f"   last error:  {last_err}  ({_ts(r.get('last_error_date'))})")

    if wants_webhook and not url:
        errors.append(
            f"{role}: no webhook registered, but its consumer only answers over a "
            f"webhook. Run scripts/rag/register_telegram_webhook.py."
        )
    if not wants_webhook and url:
        errors.append(
            f"{role}: a webhook is registered ({url}), so Telegram will refuse "
            f"getUpdates with 409 and {consumer} receives nothing. Either delete the "
            f"webhook (deleteWebhook) to restore polling, or deploy gateway.api and "
            f"re-run with --expect-webhook {role}."
        )
    if last_err:
        errors.append(f"{role}: Telegram's last delivery attempt failed — {last_err}")
    if pending > 0:
        warnings.append(
            f"{role}: {pending} update(s) queued at Telegram — nothing is consuming "
            f"them. Users are messaging a bot that cannot answer."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--expect-webhook",
        action="append",
        default=[],
        choices=sorted(BOTS),
        help="Treat this bot as webhook-mode (e.g. the pipeline bot when gateway.api is deployed).",
    )
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []

    print("Telegram channel check")
    for role in BOTS:
        check(role, set(args.expect_webhook), errors, warnings)

    # The regression that took the pipeline bot down on 2026-05-29: one token, two owners.
    pipeline_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    rag_token = os.environ.get("TELEGRAM_RAG_BOT_TOKEN", "").strip()
    if pipeline_token and pipeline_token == rag_token:
        errors.append(
            "TELEGRAM_BOT_TOKEN and TELEGRAM_RAG_BOT_TOKEN hold the SAME token. "
            "One bot cannot serve both the pipeline and the RAG API — whichever "
            "registers a webhook last silently wins and the other goes dead."
        )

    print()
    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")

    if errors:
        print(f"\n{len(errors)} error(s) — Telegram channels are NOT healthy.")
        return 1
    print("\nAll Telegram channels healthy." + (f" ({len(warnings)} warning(s))" if warnings else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
