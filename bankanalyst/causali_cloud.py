"""Causali collected by the Telegram bot (Firestore database `causali`), read at the start of every run.

Read-only. When the cloud cannot be reached (offline, expired credentials) the run does not stop: it returns
a warning that the CLI prints and the Controlli sheet shows, and goes on with the local causali.
"""
from bankanalyst.classify import Note


def fetch_notes(project: str | None = None, store=None) -> tuple[list[Note], str | None]:
    """(notes, warning): every causale in the cloud as a Note, or ([], why) if the cloud does not answer."""
    try:
        if store is None:
            from causalibot.store import FirestoreStore
            store = FirestoreStore(project=project)
        causali = store.all()
    except Exception as e:  # any failure is a warning: the analysis must not depend on the network
        why = " ".join(f"{type(e).__name__}: {e}".split())[:120]
        return [], f"causali cloud non raggiungibili ({why}): uso solo quelle del file locale"
    return [Note(day=c.day, bank=c.bank, amount=c.amount, causale=c.causale, category=c.category or None)
            for c in causali], None


def merge_notes(local: list[Note], cloud: list[Note]) -> list[Note]:
    """Local first, then the cloud ones that are not already there (same day, bank, amount and text)."""
    seen = {(n.day, n.bank, n.amount, n.causale) for n in local}
    out = list(local)
    for n in cloud:
        key = (n.day, n.bank, n.amount, n.causale)
        if key not in seen:
            seen.add(key)
            out.append(n)
    return out
