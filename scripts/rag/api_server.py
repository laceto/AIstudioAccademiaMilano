"""
api_server.py — RAG HTTP API
FastAPI server that exposes the repo RAG pipeline over HTTP.

Endpoints:
    GET  /health         — liveness check
    POST /chat           — blocking JSON {answer, sources, queries}
    POST /chat/stream    — Server-Sent Events: meta → tokens → done

Start:
    python -m scripts.rag.api_server
    uvicorn scripts.rag.api_server:app --host 0.0.0.0 --port 8000 --reload

Embed:
    <iframe src="deliverables/rag/chat_widget.html" ...></iframe>
    The widget connects to http://localhost:8000 by default.
"""

import base64 as _base64
import hashlib as _hashlib
import hmac as _hmac
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import httpx as _httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException
from fastapi import Request as _Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.brand import b, fmt
from scripts.rag.retrieve_repo import (
    CHAT_MODEL,
    K_BM25,
    K_SEMANTIC,
    QUERY_STRATEGY,
    WEIGHTS_SPARSE,
    _get_resources,
    retrieve_for_queries,
    translate_query,
)
from kitai.retriever import (
    create_BM25retriever_from_docs,
    create_hybrid_retriever,
    create_retriever,
    reorder_docs,
)

load_dotenv()

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    fmt(b("agent_personas.rag_expert_prompt")) + "\n"
    "Use the following repo excerpts to answer the question precisely.\n"
    "If the context does not contain enough information, say so.\n\n"
)


# ── Lifespan: pre-warm RAG resources on startup ───────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Pre-warming RAG resources ...")
    _get_resources()
    log.info("RAG resources ready.")
    yield


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="AI Studio RAG API", version="1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request schema ────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    query: str
    strategy: str = QUERY_STRATEGY
    k_semantic: int = K_SEMANTIC
    k_bm25: int = K_BM25
    weights_sparse: float = WEIGHTS_SPARSE


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_retriever(res: dict, k_semantic: int, k_bm25: int, weights_sparse: float):
    bm25   = create_BM25retriever_from_docs(docs=res["corpus"], k=k_bm25)
    vector = create_retriever(res["vs"], search_type="similarity", search_kwargs={"k": k_semantic})
    return create_hybrid_retriever(
        sparse_retriever=bm25,
        semantic_retriever=vector,
        weights_sparse=weights_sparse,
    )


def _to_sources(docs) -> list[dict]:
    return [
        {
            "path":    doc.metadata.get("path", ""),
            "chunk":   doc.metadata.get("chunk_index", 0),
            "snippet": doc.page_content[:200].replace("\n", " "),
        }
        for doc in docs
    ]


def _sync_rag_answer(query: str) -> str:
    res     = _get_resources()
    hybrid  = _build_retriever(res, K_SEMANTIC, K_BM25, WEIGHTS_SPARSE)
    queries = translate_query(res["chat_model"], query, QUERY_STRATEGY)
    merged  = retrieve_for_queries(queries, hybrid)
    ordered = reorder_docs(merged)
    context = "\n\n".join(doc.page_content for doc in ordered)
    prompt  = SYSTEM_PROMPT + f"Context:\n{context}\n\nQuestion: {query}"
    resp = res["openai_client"].chat.completions.create(
        model=CHAT_MODEL,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
        stream=False,
    )
    return resp.choices[0].message.content.strip()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat(req: ChatRequest):
    """Blocking JSON response — use for programmatic calls."""
    from scripts.rag.retrieve_repo import ask
    return ask(
        req.query,
        strategy=req.strategy,
        k_semantic=req.k_semantic,
        k_bm25=req.k_bm25,
        weights_sparse=req.weights_sparse,
    )


@app.post("/chat/sync")
def chat_sync(req: ChatRequest):
    """Sync JSON response (~2s) — used by gateway bots for real-time Q&A."""
    return {"answer": _sync_rag_answer(req.query)}


@app.post("/chat/stream")
def chat_stream(req: ChatRequest):
    """SSE stream — use for the chat widget.

    Event sequence:
        data: {"type": "meta",  "queries": [...], "sources": [...]}
        data: {"type": "token", "content": "..."}  (repeated)
        data: {"type": "done"}
    """
    def generate():
        res    = _get_resources()
        hybrid = _build_retriever(res, req.k_semantic, req.k_bm25, req.weights_sparse)

        queries = translate_query(res["chat_model"], req.query, req.strategy)
        merged  = retrieve_for_queries(queries, hybrid)
        ordered = reorder_docs(merged)

        yield f"data: {json.dumps({'type': 'meta', 'queries': queries, 'sources': _to_sources(ordered)})}\n\n"

        context = "\n\n".join(doc.page_content for doc in ordered)
        prompt  = SYSTEM_PROMPT + f"Context:\n{context}\n\nQuestion: {req.query}"

        # SSE streaming requires token-by-token delivery — batch API cannot be used here.
        stream = res["openai_client"].chat.completions.create(
            model=CHAT_MODEL,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield f"data: {json.dumps({'type': 'token', 'content': delta})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/webhook/telegram")
async def webhook_telegram(request: _Request):
    token   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    body    = await request.json()
    msg     = body.get("message", {})
    text    = (msg.get("text") or "").strip()
    chat_id = msg.get("chat", {}).get("id")
    if not text or not chat_id:
        return {}
    answer = _sync_rag_answer(text)
    if token:
        async with _httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": answer},
            )
    else:
        log.warning("/webhook/telegram: TELEGRAM_BOT_TOKEN unset — reply suppressed")
    return {}


@app.post("/webhook/whatsapp", response_class=PlainTextResponse)
async def webhook_whatsapp(
    request: _Request,
    Body: str = Form(default=""),
    From: str = Form(default=""),
):
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    if auth_token:
        sig       = request.headers.get("X-Twilio-Signature", "")
        form_data = await request.form()
        sorted_p  = "".join(f"{k}{v}" for k, v in sorted(form_data.items()))
        canonical = str(request.url) + sorted_p
        expected  = _base64.b64encode(
                        _hmac.new(auth_token.encode(), canonical.encode(), _hashlib.sha1).digest()
                    ).decode()
        if not _hmac.compare_digest(expected, sig):
            raise HTTPException(status_code=403, detail="Invalid Twilio signature")
    else:
        log.warning("/webhook/whatsapp: TWILIO_AUTH_TOKEN unset — signature check skipped (dev)")

    incoming = Body.strip()
    if not incoming or not From:
        return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'

    answer = _sync_rag_answer(incoming)

    sid     = os.environ.get("TWILIO_ACCOUNT_SID", "")
    wa_from = os.environ.get("TWILIO_WHATSAPP_FROM", "")
    if sid and auth_token and wa_from:
        async with _httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                auth=(sid, auth_token),
                data={"From": wa_from, "To": From, "Body": answer},
            )
    else:
        log.warning("/webhook/whatsapp: Twilio creds incomplete — reply suppressed")

    return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("scripts.rag.api_server:app", host="0.0.0.0", port=8000, reload=False)
