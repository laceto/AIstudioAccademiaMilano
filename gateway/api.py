"""
gateway/api.py — Pablo (Platform Engineer)

FastAPI application exposing the Input Gateway to the public internet.

Endpoints:
  POST /submit              Accept a pipeline request (JSON)
  GET  /status/{id}         Poll job status
  POST /webhook/whatsapp    Twilio WhatsApp webhook (Carlos, HMAC-validated)
  POST /webhook/telegram    Telegram webhook (registered after Cloud Run deploy)
  GET  /health              Liveness probe

Run locally:
  uvicorn gateway.api:app --reload --port 8080

Environment variables:
  GATEWAY_QUEUE_DIR     Queue directory path (default: gateway/queue)
  ANTHROPIC_API_KEY     Claude API key for the queue worker
  OPENAI_API_KEY        OpenAI API key (fallback for queue worker)
  TELEGRAM_BOT_TOKEN    Required for Telegram webhook mode
"""

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

# Load .env from repo root — setdefault so Cloud Run env vars always win
_env_file = Path(__file__).resolve().parent.parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, field_validator

from config.brand import b
from gateway.bot_whatsapp import router as whatsapp_router
from gateway.middleware import check_rate_limit
from gateway.pipeline_adapter import PipelineAdapter
from gateway.showcase import ShowcaseCard, load_cards

_queue_dir = os.environ.get("GATEWAY_QUEUE_DIR", "gateway/queue")
_adapter = PipelineAdapter(queue_dir=_queue_dir)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from gateway.worker import QueueWorker
    worker = QueueWorker(queue_dir=_queue_dir)
    task = asyncio.create_task(worker.run())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    pass


app = FastAPI(title=b("studio.name") + " Input Gateway", version="1.0.0", lifespan=lifespan)
app.include_router(whatsapp_router)


# ── Request / response models ────────────────────────────────────────────────

class SubmitRequest(BaseModel):
    text: str
    channel: str = "api"
    metadata: dict = {}

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("text must not be empty")
        if len(v) > 4000:
            raise ValueError("text exceeds 4000 characters")
        return v

    @field_validator("channel")
    @classmethod
    def channel_valid(cls, v: str) -> str:
        allowed = {"api", "streamlit", "telegram", "whatsapp"}
        if v not in allowed:
            raise ValueError(f"channel must be one of {allowed}")
        return v


# ── Endpoints ────────────────────────────────────────────────────────────────

def _render_showcase(cards: list[ShowcaseCard]) -> str:
    """Inline HTML gallery — no Jinja2 dependency for a single-page render."""
    studio_name = b("studio.name")
    tagline = b("studio.tagline")

    # Live tools — cards that have a deployed URL get a dedicated "Try it" banner
    live_cards = [c for c in cards if c.live_url]
    live_html = ""
    if live_cards:
        items = "\n".join(
            f"""<a class="tool-chip" href="{c.live_url}" target="_blank" rel="noopener">
  <span class="tool-name">{c.title}</span>
  <span class="tool-price">€{c.price_eur:.2f}</span>
  <span class="tool-arrow">↗</span>
</a>"""
            for c in live_cards
        )
        live_html = f"""
    <h2>Live tools</h2>
    <div class="tools-row">
{items}
    </div>"""

    def _card(c: ShowcaseCard) -> str:
        open_btn = (
            f'<a class="btn-open" href="{c.live_url}" target="_blank" rel="noopener">Open app ↗</a>'
            if c.live_url
            else ""
        )
        return f"""<article class="card" data-product="{c.product_type}">
  <header>
    <h3>{c.title}</h3>
    <span class="price">€{c.price_eur:.2f}</span>
  </header>
  <p class="meta">#{c.request_id} · delivered {c.date}</p>
  <div class="card-actions">
    {open_btn}
    <form onsubmit="return submitIntent(event)">
      <button type="submit">Order this</button>
    </form>
  </div>
  <div class="status" hidden>
    <p class="state"></p>
    <p class="job-id"></p>
    <p class="details"></p>
    <button type="button" class="close">Dismiss</button>
  </div>
</article>"""

    card_html = "\n".join(_card(c) for c in cards)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{studio_name}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root {{ color-scheme: light dark; --fg: #1a1a1a; --muted: #666; --accent: #c83e2c; --bg: #fafaf7; --card: #fff; --border: #e5e3dd; }}
    @media (prefers-color-scheme: dark) {{ :root {{ --fg: #f0ede5; --muted: #999; --bg: #161410; --card: #1f1d18; --border: #2c2a24; }} }}
    * {{ box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif; margin: 0; background: var(--bg); color: var(--fg); line-height: 1.5; }}
    header.hero {{ padding: 4rem 2rem 2rem; max-width: 1100px; margin: 0 auto; }}
    header.hero h1 {{ font-size: clamp(2rem, 5vw, 3rem); margin: 0 0 0.5rem; }}
    header.hero p {{ color: var(--muted); font-size: 1.15rem; margin: 0; max-width: 38rem; }}
    main {{ max-width: 1100px; margin: 0 auto; padding: 1rem 2rem 4rem; }}
    h2 {{ font-size: 1.1rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); margin: 2rem 0 1rem; font-weight: 600; }}
    .grid {{ display: grid; gap: 1rem; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); }}
    .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 1.25rem; display: flex; flex-direction: column; gap: 0.75rem; }}
    .card header {{ display: flex; justify-content: space-between; align-items: baseline; gap: 0.5rem; }}
    .card h3 {{ font-size: 1.1rem; margin: 0; }}
    .price {{ color: var(--accent); font-weight: 600; font-variant-numeric: tabular-nums; white-space: nowrap; }}
    .meta {{ color: var(--muted); font-size: 0.85rem; margin: 0; }}
    .card-actions {{ display: flex; gap: 0.5rem; margin-top: auto; flex-wrap: wrap; }}
    .card-actions form {{ flex: 1; min-width: 0; }}
    .card button {{ width: 100%; background: var(--fg); color: var(--bg); border: 0; border-radius: 8px; padding: 0.6rem 1rem; font-weight: 600; cursor: pointer; font: inherit; }}
    .card button:hover {{ background: var(--accent); color: #fff; }}
    .card button:disabled {{ opacity: 0.6; cursor: wait; }}
    .btn-open {{ display: flex; align-items: center; justify-content: center; gap: 0.25rem; background: transparent; color: var(--accent); border: 1.5px solid var(--accent); border-radius: 8px; padding: 0.6rem 1rem; font-weight: 600; font-size: 0.9rem; text-decoration: none; white-space: nowrap; }}
    .btn-open:hover {{ background: var(--accent); color: #fff; }}
    .tools-row {{ display: flex; flex-wrap: wrap; gap: 0.75rem; margin-bottom: 0.5rem; }}
    .tool-chip {{ display: flex; align-items: center; gap: 0.6rem; background: var(--card); border: 1.5px solid var(--accent); border-radius: 999px; padding: 0.45rem 1rem; text-decoration: none; color: var(--fg); font-weight: 500; transition: background 0.15s; }}
    .tool-chip:hover {{ background: var(--accent); color: #fff; }}
    .tool-name {{ font-size: 0.95rem; }}
    .tool-price {{ font-size: 0.8rem; color: var(--accent); font-variant-numeric: tabular-nums; }}
    .tool-chip:hover .tool-price {{ color: rgba(255,255,255,0.8); }}
    .tool-arrow {{ font-size: 1rem; }}
    .status {{ display: flex; flex-direction: column; gap: 0.4rem; margin-top: auto; padding: 0.75rem; border: 1px solid var(--border); border-radius: 8px; background: rgba(127,127,127,0.06); }}
    .status p {{ margin: 0; font-size: 0.85rem; }}
    .status .state {{ font-weight: 600; color: var(--accent); text-transform: uppercase; letter-spacing: 0.05em; font-size: 0.75rem; }}
    .status .job-id {{ color: var(--muted); font-family: ui-monospace, "SF Mono", Menlo, monospace; word-break: break-all; }}
    .status .details {{ color: var(--fg); }}
    .status button.close {{ align-self: flex-end; background: transparent; color: var(--muted); padding: 0.25rem 0.5rem; font-size: 0.8rem; font-weight: 500; }}
    .status button.close:hover {{ background: transparent; color: var(--accent); }}
    footer {{ max-width: 1100px; margin: 0 auto; padding: 2rem; color: var(--muted); font-size: 0.85rem; }}
  </style>
</head>
<body>
  <header class="hero">
    <h1>{studio_name}</h1>
    <p>{tagline}</p>
  </header>
  <main>
{live_html}
    <h2>Catalogue · {len(cards)} delivered products</h2>
    <div class="grid">
{card_html}
    </div>
  </main>
  <footer>Every card is a real delivery — the catalogue is built from <code>process/audit/</code> at request time. · <a href="/trading" style="color:inherit">Trading Dashboard</a></footer>
  <script>
    const POLL_MS = 2000;
    const MAX_POLLS = 30; // ~60s ceiling

    function showStatus(card, parts) {{
      const form = card.querySelector("form");
      const status = card.querySelector(".status");
      form.hidden = true;
      status.hidden = false;
      if (parts.state !== undefined) status.querySelector(".state").textContent = parts.state;
      if (parts.jobId !== undefined) status.querySelector(".job-id").textContent = parts.jobId ? "Job ID: " + parts.jobId : "";
      if (parts.details !== undefined) status.querySelector(".details").textContent = parts.details;
    }}

    function resetCard(card) {{
      const form = card.querySelector("form");
      const status = card.querySelector(".status");
      const btn = form.querySelector("button");
      status.hidden = true; form.hidden = false;
      btn.disabled = false; btn.textContent = "Order this";
    }}

    async function pollUntilSettled(card, jobId) {{
      for (let i = 0; i < MAX_POLLS; i++) {{
        await new Promise(r => setTimeout(r, POLL_MS));
        let res;
        try {{ res = await fetch("/status/" + encodeURIComponent(jobId)); }}
        catch (e) {{ continue; }}
        if (!res.ok) continue;
        const job = await res.json();
        const s = job.status || "pending";
        if (s === "pending" || s === "processing") {{
          showStatus(card, {{ state: s, details: "Stacy is reading your request…" }});
          continue;
        }}
        const cls = job.classification || {{}};
        const intent = cls.intent || "—";
        const conf = cls.confidence !== undefined ? Math.round(cls.confidence * 100) + "%" : "—";
        let details = job.result || "";
        if (cls.summary) details = "Intent: " + intent + " · confidence " + conf + (cls.summary ? ". " + cls.summary : "");
        showStatus(card, {{ state: s, details: details }});
        return;
      }}
      showStatus(card, {{ state: "timeout", details: "Still working — save the Job ID and check back later." }});
    }}

    async function submitIntent(event) {{
      event.preventDefault();
      const card = event.target.closest(".card");
      const productType = card.dataset.product;
      const btn = event.target.querySelector("button");
      btn.disabled = true; btn.textContent = "Sending…";
      let data;
      try {{
        const res = await fetch("/submit", {{
          method: "POST", headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ text: "I would like to order: " + productType, channel: "api", metadata: {{ source: "showcase", product_type: productType }} }})
        }});
        data = await res.json();
        if (!res.ok) {{
          showStatus(card, {{ state: "error", jobId: "", details: data.detail || "Submit failed" }});
          return false;
        }}
      }} catch (e) {{
        showStatus(card, {{ state: "error", jobId: "", details: "Network error — please retry." }});
        return false;
      }}
      const jobId = data.job_id || "";
      showStatus(card, {{ state: "queued", jobId: jobId, details: "Waiting for Stacy to classify your request…" }});
      pollUntilSettled(card, jobId);
      return false;
    }}

    document.addEventListener("click", (e) => {{
      if (e.target.matches(".status button.close")) resetCard(e.target.closest(".card"));
    }});
  </script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def showcase():
    return _render_showcase(load_cards())


@app.get("/api/showcase")
async def showcase_json():
    return {
        "count": len(cards := load_cards()),
        "cards": [c.__dict__ for c in cards],
    }


@app.get("/trading", response_class=HTMLResponse)
async def trading_page():
    """Dedicated landing page for the Trading Agent Team Dashboard (deliverable 025)."""
    import os
    studio_name = b("studio.name")
    dashboard_url = os.environ.get("ALGO_TRADING_URL", "#")
    api_url = os.environ.get("TRADING_API_URL", "#")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Trading Agent Team · {studio_name}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root {{ color-scheme: light dark; --fg: #1a1a1a; --muted: #666; --accent: #c83e2c; --bg: #fafaf7; --card: #fff; --border: #e5e3dd; }}
    @media (prefers-color-scheme: dark) {{ :root {{ --fg: #f0ede5; --muted: #999; --bg: #161410; --card: #1f1d18; --border: #2c2a24; }} }}
    * {{ box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif; margin: 0; background: var(--bg); color: var(--fg); line-height: 1.6; }}
    nav {{ max-width: 1100px; margin: 0 auto; padding: 1.5rem 2rem; font-size: 0.9rem; }}
    nav a {{ color: var(--muted); text-decoration: none; }}
    nav a:hover {{ color: var(--accent); }}
    .hero {{ max-width: 1100px; margin: 0 auto; padding: 2rem 2rem 1rem; }}
    .hero h1 {{ font-size: clamp(2rem, 5vw, 3rem); margin: 0 0 0.5rem; }}
    .hero p {{ color: var(--muted); font-size: 1.1rem; max-width: 42rem; margin: 0 0 2rem; }}
    .cta-row {{ display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 0.5rem; }}
    .btn {{ display: inline-flex; align-items: center; gap: 0.4rem; padding: 0.7rem 1.4rem; border-radius: 8px; font-weight: 600; text-decoration: none; font-size: 1rem; }}
    .btn-primary {{ background: var(--fg); color: var(--bg); }}
    .btn-primary:hover {{ background: var(--accent); color: #fff; }}
    .btn-secondary {{ background: transparent; color: var(--fg); border: 1.5px solid var(--border); }}
    .btn-secondary:hover {{ border-color: var(--accent); color: var(--accent); }}
    .disclaimer {{ font-size: 0.8rem; color: var(--muted); margin-bottom: 3rem; }}
    main {{ max-width: 1100px; margin: 0 auto; padding: 0 2rem 4rem; }}
    h2 {{ font-size: 1.05rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); margin: 2.5rem 0 1rem; font-weight: 600; }}
    .agents {{ display: grid; gap: 1rem; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); }}
    .agent {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 1.25rem; }}
    .agent h3 {{ margin: 0 0 0.35rem; font-size: 1.05rem; }}
    .agent p {{ margin: 0; color: var(--muted); font-size: 0.88rem; }}
    .badge {{ display: inline-block; background: rgba(200,62,44,0.1); color: var(--accent); border-radius: 4px; padding: 0.1rem 0.4rem; font-size: 0.75rem; font-weight: 600; margin-bottom: 0.4rem; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
    th {{ text-align: left; padding: 0.5rem 0.75rem; border-bottom: 2px solid var(--border); color: var(--muted); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }}
    td {{ padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--border); }}
    td:first-child {{ font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 0.85rem; color: var(--accent); }}
    footer {{ max-width: 1100px; margin: 0 auto; padding: 2rem; color: var(--muted); font-size: 0.85rem; }}
    footer a {{ color: inherit; }}
  </style>
</head>
<body>
  <nav><a href="/">← {studio_name}</a></nav>
  <div class="hero">
    <h1>📊 Trading Agent Team</h1>
    <p>Four autonomous agents covering US and Italian markets — SMA crossover signals,
    real-time Alpaca paper execution, and deep analysis via the techa LangGraph Orchestrator.</p>
    <div class="cta-row">
      <a class="btn btn-primary" href="{dashboard_url}" target="_blank" rel="noopener">Open Dashboard ↗</a>
      <a class="btn btn-secondary" href="{api_url}/docs" target="_blank" rel="noopener">API Docs ↗</a>
      <a class="btn btn-secondary" href="/">Order a custom version</a>
    </div>
    <p class="disclaimer">⚠️ Paper trading only · Alpaca paper mode · Not financial advice · €24.90</p>
  </div>
  <main>
    <h2>Agent roster</h2>
    <div class="agents">
      <div class="agent">
        <span class="badge">🇺🇸 Alpaca</span>
        <h3>Agent Alpha</h3>
        <p>AAPL · MSFT · GOOGL<br>SMA 20/50 — large-cap momentum</p>
      </div>
      <div class="agent">
        <span class="badge">🇺🇸 Alpaca</span>
        <h3>Agent Beta</h3>
        <p>NVDA · AMD · TSLA<br>SMA 10/30 — semiconductor &amp; EV fast trend</p>
      </div>
      <div class="agent">
        <span class="badge">🇺🇸 Alpaca</span>
        <h3>Agent Gamma</h3>
        <p>AMZN · META<br>SMA 15/40 — internet mega-cap slow trend</p>
      </div>
      <div class="agent">
        <span class="badge">🌍 yfinance</span>
        <h3>Agent Delta</h3>
        <p>ENI.MI · A2A.MI · PST.MI<br>SMA 20/60 — Italian blue-chips · analysis only</p>
      </div>
    </div>

    <h2>REST API</h2>
    <table>
      <thead><tr><th>Method</th><th>Path</th><th>Description</th></tr></thead>
      <tbody>
        <tr><td>GET</td><td>/health</td><td>Liveness + state summary</td></tr>
        <tr><td>GET</td><td>/api/agents</td><td>All agent statuses</td></tr>
        <tr><td>GET</td><td>/api/agents/{{name}}</td><td>Single agent detail + config</td></tr>
        <tr><td>GET</td><td>/api/signals</td><td>All signals — filter by ?signal=buy or ?source=yfinance</td></tr>
        <tr><td>GET</td><td>/api/portfolio</td><td>Alpaca paper portfolio snapshot</td></tr>
        <tr><td>GET</td><td>/api/positions</td><td>Open positions</td></tr>
        <tr><td>POST</td><td>/api/run</td><td>Trigger strategy run — body: {{agent, dry_run}}</td></tr>
        <tr><td>GET</td><td>/api/analyses</td><td>List cached techa Orchestrator reports</td></tr>
        <tr><td>GET</td><td>/api/analysis/{{symbol}}</td><td>techa deep analysis — ?refresh=true to force re-run</td></tr>
      </tbody>
    </table>

    <h2>Auth</h2>
    <p style="color:var(--muted);font-size:0.9rem">Pass <code>X-API-Key: &lt;TRADING_API_KEY&gt;</code> header. Leave <code>TRADING_API_KEY</code> unset to run open.</p>

    <h2>Stack</h2>
    <p style="color:var(--muted);font-size:0.9rem">
      Streamlit · FastAPI · Alpaca paper · yfinance · SMA/RSI · techa (TA-Lib + LangGraph + GPT-4o) ·
      Shared JSON state store · Dockerfile (HF Spaces / Cloud Run compatible)
    </p>
  </main>
  <footer>Deliverable 025 · {studio_name} · <a href="/">Back to catalogue</a></footer>
</body>
</html>"""


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/submit", status_code=status.HTTP_202_ACCEPTED)
async def submit(request: Request, body: SubmitRequest):
    ip = request.client.host if request.client else "unknown"

    if not check_rate_limit(ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded — try again in 60 seconds")

    result = _adapter.submit(
        text=body.text,
        channel=body.channel,
        metadata={**body.metadata, "ip": ip},
    )

    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["result"])

    return result


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    job = _adapter.get_status(job_id)
    if job["status"] == "not_found":
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")
    return job


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    """Telegram update webhook — receives updates from Telegram servers."""
    from telegram import Bot
    from gateway.bot_telegram import _normalize

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise HTTPException(status_code=503, detail="TELEGRAM_BOT_TOKEN not configured")

    try:
        data = await request.json()
    except Exception:
        return {"ok": True}

    message = data.get("message") or data.get("edited_message")
    if not message:
        return {"ok": True}

    text = message.get("text", "").strip()
    chat_id = message.get("chat", {}).get("id")
    user_id = message.get("from", {}).get("id", "anonymous")

    if not text or not chat_id:
        return {"ok": True}

    bot = Bot(token=token)

    if text.startswith("/start"):
        await bot.send_message(
            chat_id=chat_id,
            text=(
                "Benvenuto in " + b("studio.name") + "!\n\n"
                "Dimmi cosa ti serve e lo costruiamo per te.\n\n"
                "Esempi:\n"
                "• Ho bisogno di un sito per il mio ristorante\n"
                "• Crea una fattura PDF da 500€\n"
                "• Voglio un chatbot per il mio sito\n\n"
                "Scrivi la tua richiesta e penso io al resto."
            ),
        )
        return {"ok": True}

    normalized = _normalize(text)
    if not normalized:
        await bot.send_message(chat_id=chat_id, text="Invia un messaggio di testo con la tua richiesta.")
        return {"ok": True}

    result = _adapter.submit(
        text=normalized,
        channel="telegram",
        metadata={"user_id": user_id, "chat_id": chat_id},
    )

    if result["status"] == "error":
        await bot.send_message(
            chat_id=chat_id,
            text="Non riesco a elaborare questa richiesta. Prova con una diversa.",
        )
    else:
        await bot.send_message(
            chat_id=chat_id,
            text=f"Ricevuto! La tua richiesta è in elaborazione.\n\nJob ID: `{result['job_id']}`",
            parse_mode="Markdown",
        )

    return {"ok": True}
