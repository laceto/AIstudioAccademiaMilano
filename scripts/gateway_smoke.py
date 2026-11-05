"""scripts/gateway_smoke.py — 046: smoke test of the Input Gateway.

Simulates a new project request the way a customer would send it through the API
channel, then checks that the gateway accepts it, stores it and (optionally) that
the worker classifies it.

Checks, in order (stops at the first one that makes the rest meaningless):
  health              GET  /health -> 200 {"status": "ok"}
  rejects_missing_key POST /submit without X-API-Key -> 401 (047)
  rejects_bad_channel POST /submit with channel "fax" -> 422
  submit              POST /submit with the simulated request -> 202 + job_id
  status              GET  /status/{job_id} -> 200, same job, same text
  classified          (only with --wait > 0) polls until the job leaves queued/processing;
                      passes only on an expected final status (default: needs_review)
  unknown_job_404     GET  /status/<unknown> -> 404

Standard library only, so it runs on a bare runner.

Usage:
  GATEWAY_API_KEY=... python scripts/gateway_smoke.py --url http://127.0.0.1:8080 --wait 60
  GATEWAY_API_KEY=... python scripts/gateway_smoke.py --url https://gateway-...run.app   # deployed: no --wait

The key is read from the GATEWAY_API_KEY environment variable, never from the command
line (it would end up in shell history and in CI logs).

On a deployed gateway with GATEWAY_SYNC_REPLY=1 nothing classifies jobs sent to
/submit, so --wait would always time out there. The job stays `queued` and expires
like any other (JOB_RETENTION_DAYS). It is marked with user_id SMOKE_USER_ID.

Exit code: 0 when every check passes, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Callable

SMOKE_USER_ID = "smoke-test-github-actions"

DEFAULT_REQUEST = (
    "[SMOKE TEST] Buongiorno, ho una piccola pasticceria in zona Città Studi a Milano. "
    "Vorrei una landing page semplice con orari, indirizzo, tre foto dei dolci "
    "e un pulsante per scriverci su WhatsApp. Budget contenuto."
)

# Final statuses the worker can reach. needs_review is the normal one: every request
# waits for Luigi, catalogue product or not.
FINAL_OK = {"needs_review"}
PENDING = {"queued", "processing"}

# (method, path, json body or None, key=True) -> (http status, parsed json or {})
# key=False: send the request without X-API-Key.
Transport = Callable[..., "tuple[int, dict]"]


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


def http_transport(base_url: str, api_key: str = "", timeout: float = 20.0) -> Transport:
    """Every call sends X-API-Key, except the ones run_smoke makes with key=False."""
    base = base_url.rstrip("/")

    def call(method: str, path: str, body: dict | None = None, key: bool = True) -> tuple[int, dict]:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(base + path, data=data, method=method)
        req.add_header("User-Agent", "aistudio-gateway-smoke/1.0")
        if key and api_key:
            req.add_header("X-API-Key", api_key)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                status, raw = r.status, r.read()
        except urllib.error.HTTPError as e:
            status, raw = e.code, e.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            return 0, {"error": type(e).__name__}
        try:
            return status, json.loads(raw or b"{}")
        except ValueError:
            return status, {}

    return call


def run_smoke(
    call: Transport,
    request_text: str = DEFAULT_REQUEST,
    wait_seconds: float = 0,
    poll_seconds: float = 2.0,
    expect: set[str] | None = None,
) -> tuple[list[Check], str | None]:
    expect = expect or FINAL_OK
    checks: list[Check] = []

    code, data = call("GET", "/health", None)
    checks.append(Check("health", code == 200 and data.get("status") == "ok", f"HTTP {code}"))
    if not checks[-1].ok:
        return checks, None

    code, _ = call("POST", "/submit", {"text": "smoke"}, key=False)
    checks.append(Check("rejects_missing_key", code == 401, f"HTTP {code} (atteso 401)"))

    code, _ = call("POST", "/submit", {"text": "smoke", "channel": "fax"})
    checks.append(Check("rejects_bad_channel", code == 422, f"HTTP {code} (atteso 422)"))

    code, data = call("POST", "/submit", {
        "text": request_text,
        "channel": "api",
        "metadata": {"user_id": SMOKE_USER_ID, "smoke_run": uuid.uuid4().hex[:8]},
    })
    job_id = data.get("job_id") if isinstance(data, dict) else None
    ok = code == 202 and bool(job_id) and data.get("status") == "queued"
    checks.append(Check("submit", ok, f"HTTP {code}, job_id={job_id}, status={data.get('status')}"))
    if not ok:
        return checks, None

    code, job = call("GET", f"/status/{job_id}", None)
    ok = code == 200 and job.get("job_id") == job_id and job.get("text") == request_text.strip()
    checks.append(Check("status", ok, f"HTTP {code}, status={job.get('status')}"))

    if wait_seconds > 0 and ok:
        deadline = time.monotonic() + wait_seconds
        state = job.get("status")
        while state in PENDING and time.monotonic() < deadline:
            time.sleep(poll_seconds)
            code, job = call("GET", f"/status/{job_id}", None)
            state = job.get("status") if code == 200 else f"HTTP {code}"
        product = (job.get("classification") or {}).get("product_type")
        if state in PENDING:
            detail = f"ancora {state} dopo {wait_seconds:g}s"
        elif state in expect:
            detail = f"status={state}, product_type={product}"
        else:
            detail = f"status={state} (atteso {'/'.join(sorted(expect))}): {str(job.get('result'))[:120]}"
        checks.append(Check("classified", state in expect, detail))

    code, _ = call("GET", "/status/smoke0notfound", None)
    checks.append(Check("unknown_job_404", code == 404, f"HTTP {code} (atteso 404)"))

    return checks, job_id


def summary_markdown(url: str, checks: list[Check], job_id: str | None) -> str:
    passed = all(c.ok for c in checks)
    lines = [
        f"## Gateway smoke test — {'OK' if passed else 'FALLITO'}",
        "",
        f"Gateway: `{url}` · job: `{job_id or '—'}`",
        "",
        "| Controllo | Esito | Dettaglio |",
        "|---|---|---|",
    ]
    for c in checks:
        lines.append(f"| {c.name} | {'ok' if c.ok else 'FALLITO'} | {c.detail} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Smoke test dell'Input Gateway")
    p.add_argument("--url", required=True, help="URL base del gateway")
    p.add_argument("--text", default=DEFAULT_REQUEST, help="testo della richiesta simulata")
    p.add_argument("--wait", type=float, default=0, help="secondi di attesa della classificazione (0 = non aspettare)")
    p.add_argument("--expect", default="needs_review", help="stati finali accettati, separati da virgola")
    a = p.parse_args(argv)

    api_key = os.environ.get("GATEWAY_API_KEY", "").strip()
    if not api_key:
        print("GATEWAY_API_KEY non impostata: /submit e /status risponderanno 401 o 503", file=sys.stderr)
    checks, job_id = run_smoke(
        http_transport(a.url, api_key), a.text, wait_seconds=a.wait,
        expect={s.strip() for s in a.expect.split(",") if s.strip()},
    )
    for c in checks:
        print(f"[{'ok' if c.ok else 'FAIL'}] {c.name}: {c.detail}")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(summary_markdown(a.url, checks, job_id))

    return 0 if checks and all(c.ok for c in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
