"""FastAPI service of the causali bot: one webhook, one allowed person, save only after the Salva button.

Env: TELEGRAM_CAUSALI_BOT_TOKEN, TELEGRAM_CAUSALI_WEBHOOK_SECRET, CAUSALI_ALLOWED_CHAT_ID, GOOGLE_CLOUD_PROJECT.
No secret / token / allowed id configured -> the webhook answers 503 (fail closed). The text of the
messages is never logged.
"""
import hmac
import logging
import os
from dataclasses import replace
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Request

from bankanalyst.amounts import fmt_eur
from causalibot.categories import category_names, guess_category
from causalibot.parser import BANKS, ParseError, parse_message
from causalibot.store import Causale, FirestoreStore

log = logging.getLogger("causalibot")
ROME = ZoneInfo("Europe/Rome")

HELP = (
    "Scrivi un movimento in una riga:\n"
    "  250 credem pulizie Valeria\n"
    "  ieri 40 ing parrucchiere\n"
    "  15/11 +120 credem rimborso Marco\n\n"
    f"La banca va sempre scritta ({' / '.join(BANKS)}): non c'è una banca di default. "
    "Uscita di default; + o 'entrata' la rendono entrata. Data: oggi (default), ieri, gg/mm, gg/mm/aaaa.\n\n"
    "Comandi: /ultime (ultime 10), /annulla (toglie l'ultima, entro 10 minuti), /help.\n"
    "Le foto delle ricevute arriveranno più avanti."
)


def _card(c: Causale) -> str:
    sign = "-" if c.amount < 0 else "+"
    return (f"{c.day:%d/%m/%Y} · {c.bank.capitalize()} · {sign}{fmt_eur(abs(c.amount))} €\n{c.causale}\n"
            f"Categoria: {c.category or 'da scegliere'}")


def _card_keyboard(key: str) -> list:
    return [[{"text": "Salva", "callback_data": f"s:{key}"},
             {"text": "Categoria ▸", "callback_data": f"c:{key}"},
             {"text": "Annulla", "callback_data": f"x:{key}"}]]


def _category_keyboard(key: str, names: list[str]) -> list:
    buttons = [{"text": n, "callback_data": f"k:{key}:{i}"} for i, n in enumerate(names)]
    return [buttons[i:i + 2] for i in range(0, len(buttons), 2)]


class HttpTelegram:
    """Minimal Bot API client over httpx; the token never reaches a log line."""

    def __init__(self, token: str):
        self._base = f"https://api.telegram.org/bot{token}"

    async def _call(self, method: str, payload: dict) -> dict:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{self._base}/{method}", json=payload)
        r.raise_for_status()
        return r.json().get("result") or {}

    async def send_message(self, chat_id, text, keyboard=None):
        payload = {"chat_id": chat_id, "text": text}
        if keyboard:
            payload["reply_markup"] = {"inline_keyboard": keyboard}
        return await self._call("sendMessage", payload)

    async def edit_message(self, chat_id, message_id, text, keyboard=None):
        payload = {"chat_id": chat_id, "message_id": message_id, "text": text,
                   "reply_markup": {"inline_keyboard": keyboard or []}}
        await self._call("editMessageText", payload)

    async def answer_callback(self, callback_id, text=""):
        await self._call("answerCallbackQuery", {"callback_query_id": callback_id, "text": text})


def create_app(store=None, telegram=None, secret: str | None = None, allowed_chat_id: int | None = None,
               now=None) -> FastAPI:
    secret = os.environ.get("TELEGRAM_CAUSALI_WEBHOOK_SECRET", "") if secret is None else secret
    if allowed_chat_id is None:
        raw = os.environ.get("CAUSALI_ALLOWED_CHAT_ID", "").strip()
        allowed_chat_id = int(raw) if raw.lstrip("-").isdigit() else None
    token = os.environ.get("TELEGRAM_CAUSALI_BOT_TOKEN", "").strip()
    clock = now or (lambda: datetime.now(timezone.utc))
    holder = {"store": store, "tg": telegram}

    def get_store():
        if holder["store"] is None:
            holder["store"] = FirestoreStore(project=os.environ.get("GOOGLE_CLOUD_PROJECT") or None)
        return holder["store"]

    def get_tg():
        if holder["tg"] is None:
            holder["tg"] = HttpTelegram(token)
        return holder["tg"]

    app = FastAPI(title="causali-bot", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    async def on_message(m: dict) -> None:
        chat = m["chat"]["id"]
        tg, db = get_tg(), get_store()
        text = (m.get("text") or "").strip()
        if not text:
            await tg.send_message(chat, "Per ora leggo solo testo: le foto delle ricevute arriveranno più avanti.")
            return
        cmd = text.split()[0].split("@")[0].lower()
        if cmd in ("/start", "/help"):
            await tg.send_message(chat, HELP)
        elif cmd == "/ultime":
            rows = db.recent(10)
            body = "\n".join(f"{c.day:%d/%m} {c.bank} {fmt_eur(c.amount)} € {c.causale}" for c in rows)
            await tg.send_message(chat, body or "Nessuna causale salvata.")
        elif cmd == "/annulla":
            gone = db.delete_last(now=clock())
            await tg.send_message(chat, f"Tolta: {gone.causale} ({fmt_eur(gone.amount)} €)." if gone
                                  else "Niente da annullare (solo l'ultima, entro 10 minuti).")
        else:
            try:
                p = parse_message(text, today=clock().astimezone(ROME).date())
            except ParseError as e:
                await tg.send_message(chat, f"Non ho capito: {e}.\n\n{HELP}")
                return
            c = Causale(day=p.day, bank=p.bank, amount=p.amount, causale=p.causale,
                        category=guess_category(p.causale, p.bank, p.amount, p.day))
            key = db.put_draft(c, created=clock())
            await tg.send_message(chat, _card(c), _card_keyboard(key))

    async def on_callback(cb: dict) -> None:
        tg, db = get_tg(), get_store()
        chat, mid = cb["message"]["chat"]["id"], cb["message"]["message_id"]
        await tg.answer_callback(cb["id"])
        action, _, rest = (cb.get("data") or "").partition(":")
        key, _, idx = rest.partition(":")
        if action == "s":
            c = db.pop_draft(key)
            if c is None:
                await tg.edit_message(chat, mid, "Già salvata o scaduta.")
                return
            db.add(c, created=clock())
            await tg.edit_message(chat, mid, _card(c) + "\n✓ Salvata")
        elif action == "x":
            db.pop_draft(key)
            await tg.edit_message(chat, mid, "Annullata.")
        elif action in ("c", "k"):
            c = db.peek_draft(key)
            if c is None:
                await tg.edit_message(chat, mid, "Scaduta: riscrivila.")
                return
            names = category_names()
            if action == "c":
                await tg.edit_message(chat, mid, _card(c) + "\nScegli la categoria:", _category_keyboard(key, names))
                return
            if idx.isdigit() and int(idx) < len(names):
                c = replace(c, category=names[int(idx)])
                db.update_draft(key, c)
            await tg.edit_message(chat, mid, _card(c), _card_keyboard(key))

    @app.post("/webhook/telegram-causali")
    async def webhook(request: Request):
        if not (secret and token_ok() and allowed_chat_id is not None):
            raise HTTPException(status_code=503, detail="causali bot not configured")
        supplied = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not hmac.compare_digest(supplied.encode(), secret.encode()):
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            data = await request.json()
        except Exception:
            return {"ok": True}
        cb = data.get("callback_query")
        m = data.get("message") or data.get("edited_message")
        sender = (cb or m or {}).get("from", {}).get("id")
        chat = ((cb or {}).get("message") or m or {}).get("chat", {}).get("id")
        if sender != allowed_chat_id or chat != allowed_chat_id:  # a stranger gets no answer and no log of the text
            return {"ok": True}
        try:
            await (on_callback(cb) if cb else on_message(m))
        except Exception:  # never echo the message; Telegram retries on a 5xx
            log.exception("causali update failed")
            raise HTTPException(status_code=500, detail="error")
        return {"ok": True}

    def token_ok() -> bool:
        return bool(token) or holder["tg"] is not None

    return app


app = create_app()
