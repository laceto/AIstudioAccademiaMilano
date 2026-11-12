"""Cloud Run service: POST /process tidies every account with `tidy.enabled` (header heuristics, no model).

Private: deployed with --no-allow-unauthenticated, so only Cloud Scheduler's service account (OIDC, run.invoker)
gets in; there is no app-level auth on purpose. Stateless: filed mail leaves the inbox, nothing is stored.

MAILAGENT_DRY_RUN (default 1) caps every run: while it is on, nothing in the mailbox changes, whatever the
request body says. Turn it off (0) after reading a dry run's decisions in Cloud Logging.
"""

from __future__ import annotations

import logging
import os
from dataclasses import asdict

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .config import load_accounts
from .jsonlog import setup_logging
from .pipeline import TidyReport, tidy_account
from .providers import build_mail

setup_logging()
log = logging.getLogger("mailagent.tidy")
app = FastAPI(title="mailagent tidy", docs_url=None, redoc_url=None)


class ProcessRequest(BaseModel):
    account: str | None = None
    dry_run: bool = False  # can only make a run safer, never override MAILAGENT_DRY_RUN=1


def _env_dry_run() -> bool:
    return os.environ.get("MAILAGENT_DRY_RUN", "1").strip().lower() not in ("0", "false", "no")


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.post("/process")
def process(req: ProcessRequest | None = None) -> JSONResponse:
    req = req or ProcessRequest()
    dry_run = _env_dry_run() or req.dry_run
    accounts = [a for a in load_accounts(os.environ.get("MAILAGENT_ACCOUNTS", "config/mailagent_accounts.yaml"))
                if a.tidy.get("enabled")]
    if req.account:
        accounts = [a for a in accounts if a.id == req.account]
        if not accounts:
            raise HTTPException(404, f"no tidy-enabled account {req.account!r}")
    out = []
    for cfg in accounts:
        try:
            rep = tidy_account(cfg, build_mail(cfg), dry_run=dry_run)
        except Exception as exc:  # account-level failure (revoked token, API outage): report, go on
            rep = TidyReport(cfg.id, errors=[f"{type(exc).__name__}: {exc}"])
        fields = {"account": rep.account_id, "dry_run": dry_run, "examined": rep.examined, "kept": rep.kept,
                  "filed": rep.filed, "errors": rep.errors}
        log.log(logging.ERROR if rep.errors else logging.INFO, "tidy %s", rep.account_id, extra={"fields": fields})
        for d in rep.decisions if dry_run else []:  # a dry run is for reading: one line per decision
            log.info("would file %s -> %s", d["id"], d["label"], extra={"fields": {"account": rep.account_id, **d}})
        out.append({"account": rep.account_id, **{k: v for k, v in asdict(rep).items() if k not in ("account_id", "decisions")}})
    status = 500 if any(a["errors"] for a in out) else 200  # non-2xx shows as a failed run in Cloud Scheduler
    return JSONResponse({"dry_run": dry_run, "accounts": out}, status_code=status)
