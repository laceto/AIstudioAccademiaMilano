"""Google credentials for one account. Headless first: the agent never opens a browser.

Order: inline token JSON in the env var named by options.token_env (Cloud Run secret), then
the token file in options.token_file. `python -m mailagent auth <account>` creates the file
once, interactively, from options.credentials_file. Tokens are never logged.
"""

from __future__ import annotations

import json
import os
from typing import Any

from ..config import AccountConfig

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
]


class AuthError(RuntimeError):
    pass


def _token_file(cfg: AccountConfig) -> str:
    return cfg.options.get("token_file", f"credentials/mailagent_{cfg.id}_token.json")


def load_credentials(cfg: AccountConfig) -> Any:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    env = cfg.options.get("token_env")
    if env and os.environ.get(env):
        creds = Credentials.from_authorized_user_info(json.loads(os.environ[env]), SCOPES)
    elif os.path.exists(_token_file(cfg)):
        creds = Credentials.from_authorized_user_file(_token_file(cfg), SCOPES)
    else:
        raise AuthError(f"[{cfg.id}] no token: set {env or 'options.token_env'} or run `python -m mailagent auth {cfg.id}`")
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as exc:  # noqa: BLE001
            raise AuthError(f"[{cfg.id}] token refresh failed ({type(exc).__name__}); re-run `auth {cfg.id}`") from exc
    return creds


def interactive_auth(cfg: AccountConfig) -> str:
    from google_auth_oauthlib.flow import InstalledAppFlow

    secrets = cfg.options.get("credentials_file", "credentials/google_credentials.json")
    creds = InstalledAppFlow.from_client_secrets_file(secrets, SCOPES).run_local_server(port=0)
    path = _token_file(cfg)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    return path


def build_service(cfg: AccountConfig, api: str, version: str) -> Any:
    from googleapiclient.discovery import build

    return build(api, version, credentials=load_credentials(cfg), cache_discovery=False)
