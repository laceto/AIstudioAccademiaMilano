"""Privacy notice (informativa privacy, GDPR art. 13 style) shown to customers of the Telegram bot.

    start_message()  short welcome + a paragraph pointing to /privacy (plain text, no parse_mode)
    privacy_text()   the full notice sent on /privacy

Both are plain text on purpose: no Markdown, so nothing in them (an e-mail address, an underscore
in a handle) can break the message. This is information, not a consent gate: nothing here asks the
customer to accept anything, and the bot works the same whether or not they read it.

Every statement below was checked against the code, not written from memory:

    what is stored        gateway/pipeline_adapter.py (text, user_id, chat_id), gateway/worker.py
                          (classification), jobstore.py (the whole job, including `result`)
    who sees it           gateway/notify.py: notify_review sends the request text and chat id to
                          NOTIFY_EMAILS (Gmail SMTP) and to Luigi on Telegram; notify_result sends
                          the finished file to Luigi, who decides whether it reaches the customer
    retention of jobs     gateway/retention.py: retention_days(), never a literal here
    retention of logs     gateway/convlog.py: every message in and out, cut at convlog.MAX_CHARS,
                          lives in Cloud Logging (default bucket retention: 30 days)
    processors            docs/cloud-run-setup.md and deliverables/2026-10-09_036_*: Cloud Run and
                          Firestore in europe-west8, Cloud Tasks in europe-west6 (it carries only the
                          job id), OpenAI, Telegram, Gmail

TODO(Luigi): this is not legal advice. Only the owner can confirm, before the notice is relied upon:
  1. The controller's legal identity (name or company name, VAT number / tax code, registered
     address). The text names the studio brand and Milan only.
  2. The contact address: set PRIVACY_CONTACT (e-mail or @handle). Unset, the text says honestly
     that there is no dedicated address and tells the customer to write in the bot chat.
  3. The legal-basis wording (art. 6(1)(b) GDPR, "handling the request the customer asked for").
  4. Transfers outside the EU: OpenAI, Telegram and Google may process data outside the EEA. The
     text says so in general terms; the safeguards (adequacy decision, standard clauses) need a
     legal check and the wording may need to name them.
     Open item: safeguards wording to be confirmed with a professional.
  5. Whether Anthropic should be named: gateway/worker.py classifies with Anthropic when
     ANTHROPIC_API_KEY is set. The notice names OpenAI only, because that is what is deployed.
  6. LOG_RETENTION_DAYS below is Google's default for the _Default bucket; if the bucket retention
     is changed in the console, change the constant.
  7. Automatic refusal of illegal requests (gateway/safety.py, gateway/worker.py): confirm with a
     professional (a) the legitimate-interest balancing for sending the owner the category and the
     per-chat counter of refused requests (art. 6(1)(f)), (b) the art. 22 assessment of an
     automatic refusal and whether the RIESAMINA route is enough, (c) whether suspected crime is
     ever to be reported to the authorities (today nothing is reported).
"""

from __future__ import annotations

import os

from config.brand import b
from gateway.convlog import MAX_CHARS
from gateway.retention import refused_retention_days, retention_days

# Default retention of the Cloud Logging _Default bucket. Not readable from the code: if the
# bucket is reconfigured, update this number.
LOG_RETENTION_DAYS = 30


def _contact_line() -> str:
    contact = os.environ.get("PRIVACY_CONTACT", "").strip()
    if contact:
        return f"Per esercitare i tuoi diritti scrivi a: {contact}"
    return (
        "Per esercitare i tuoi diritti scrivi qui, in questa chat: la richiesta arriva "
        "direttamente a me. Al momento non c'è un indirizzo e-mail dedicato alla privacy."
    )


def start_message() -> str:
    """Welcome text for /start: the usual greeting and examples, plus a short privacy paragraph."""
    return (
        "Benvenuto in " + b("studio.name") + "!\n\n"
        "Dimmi cosa ti serve e lo costruiamo per te.\n\n"
        "Esempi:\n"
        "• Ho bisogno di un sito per il mio ristorante\n"
        "• Crea una fattura PDF da 500€\n"
        "• Voglio un chatbot per il mio sito\n\n"
        "Per domande sulla knowledge base: /ask <domanda>\n"
        "Scrivi la tua richiesta e penso io al resto.\n\n"
        "Privacy: per rispondere conserviamo i messaggi che scrivi e il tuo ID Telegram; "
        "ogni richiesta viene letta dal titolare. Come li trattiamo, per quanto "
        "tempo e quali sono i tuoi diritti: /privacy"
    )


def privacy_text() -> str:
    """Full privacy notice for /privacy. Plain text, well under Telegram's 4096-character limit."""
    days = retention_days()
    return (
        "INFORMATIVA PRIVACY\n"
        "(art. 13 Regolamento UE 2016/679, GDPR)\n\n"
        "Titolare del trattamento\n"
        f"{b('studio.name')}, Milano.\n\n"
        "Quali dati conserviamo\n"
        "• il testo dei messaggi che mandi al bot e le nostre risposte;\n"
        "• il tuo ID Telegram e l'ID della chat (numeri assegnati da Telegram);\n"
        "• la classificazione della richiesta (tipo di prodotto, riassunto, prezzo proposto);\n"
        "• per le richieste approvate, il risultato generato (il file che ti consegniamo).\n"
        "Per favore non scrivere dati che non servono alla richiesta, in particolare dati "
        "sulla salute o altre categorie particolari.\n\n"
        "Perché\n"
        "Per capire la tua richiesta, preparare un preventivo, realizzarla e consegnartela "
        "(art. 6, par. 1, lett. b GDPR: esecuzione di ciò che ci chiedi).\n\n"
        "Chi li vede\n"
        "• La classificazione è automatica (intelligenza artificiale), ma ogni richiesta fuori "
        "catalogo la rivede il titolare di persona.\n"
        "• Per questa revisione il titolare riceve il testo della richiesta e l'ID della chat "
        "su Telegram e per e-mail, ai suoi indirizzi (tramite Gmail).\n"
        "• Il risultato generato passa dal titolare prima di arrivare a te.\n\n"
        "A chi si affida il trattamento (responsabili)\n"
        "• Google Cloud: Cloud Run (il bot) e Firestore (archivio delle richieste), a Milano "
        "(europe-west8); Cloud Logging (registro dei messaggi); Cloud Tasks (coda di lavoro, "
        "Zurigo, europe-west6) dove passa solo il codice della richiesta, non il testo.\n"
        "• OpenAI: classifica la richiesta e genera il risultato, quindi riceve il testo che "
        "scrivi.\n"
        "• Telegram: il canale su cui ci scrivi.\n"
        "• Gmail (Google): la copia per e-mail al titolare.\n"
        "Alcuni di questi fornitori possono trattare dati anche fuori dallo Spazio economico "
        "europeo.\n\n"
        "Per quanto tempo\n"
        f"• Le richieste (testo, classificazione, risultato) sono conservate circa {days} giorni "
        "dalla creazione e poi cancellate automaticamente; la cancellazione automatica può "
        "arrivare fino a un giorno dopo la scadenza.\n"
        f"• Le richieste rifiutate in automatico sono conservate {refused_retention_days()} giorni "
        "(se il titolare le riesamina, valgono i tempi normali).\n"
        f"• Ogni messaggio, tuo e del bot, finisce anche in Cloud Logging (fino a {MAX_CHARS} "
        f"caratteri per messaggio), dove di norma resta {LOG_RETENTION_DAYS} giorni.\n"
        "• Il file che il bot invia al titolare per la revisione resta nella chat Telegram del "
        "titolare finché lui non lo cancella; le copie per e-mail restano nella casella "
        "e-mail del titolare finché lui non le cancella.\n\n"
        "I tuoi diritti\n"
        "Puoi chiedere accesso ai tuoi dati, rettifica, cancellazione, limitazione del "
        "trattamento e opporti al trattamento. Se pensi che i tuoi dati siano trattati male "
        "puoi presentare reclamo al Garante per la protezione dei dati personali "
        "(garanteprivacy.it).\n"
        f"{_contact_line()}\n"
        "Per cancellare una richiesta indica il suo Job ID, se lo hai, oppure descrivila.\n"
        "• Le righe di conversazione in Cloud Logging non possono essere cancellate una per "
        f"una: scadono da sole dopo {LOG_RETENTION_DAYS} giorni.\n"
        "• OpenAI e Telegram conservano i dati secondo condizioni proprie; per la sua parte "
        "Telegram è titolare autonomo.\n\n"
        "Decisioni automatiche\n"
        "Il prezzo a catalogo è proposto da un listino fisso; ogni richiesta la approva o la "
        "rifiuta il titolare di persona prima che parta la lavorazione. A parte il "
        "rifiuto qui sotto, nessuna decisione con effetti giuridici nei tuoi confronti è "
        "presa solo dal software.\n"
        "Le richieste chiaramente illegali (per esempio documenti o ricette falsi, phishing, "
        "virus informatici) sono rifiutate in automatico da un controllo del software e "
        "dell'intelligenza artificiale. Il titolare riceve un avviso con l'inizio del testo, "
        "la categoria assegnata dal sistema (classificazione automatica, non verificata) e il "
        "numero di richieste rifiutate della tua chat, per prevenire abusi (interesse "
        "legittimo, art. 6, par. 1, lett. f GDPR); puoi opporti. Puoi chiedere l'intervento "
        "umano, esprimere la tua opinione e contestare il rifiuto rispondendo RIESAMINA in "
        "chat: il titolare decide di persona.\n\n"
        "Questa è solo un'informazione: non devi accettare nulla per usare il bot."
    )


# ── sending a notice that may not fit one Telegram message ───────────────────

# Telegram refuses messages over 4096 characters. The notice was 4064: adding the controller's
# details or one more digit in a retention figure would have broken /privacy. So it goes out in
# as many messages as it takes, each well under the limit, cut between paragraphs.
MESSAGE_LIMIT = 3500


def _cut(paragraph: str, limit: int) -> list[str]:
    """Cut one over-long paragraph at line breaks; a single over-long line is cut hard."""
    parts: list[str] = []
    current = ""
    for line in paragraph.split("\n"):
        while len(line) > limit:  # a line longer than a whole message: hard cut
            if current:
                parts.append(current)
                current = ""
            parts.append(line[:limit])
            line = line[limit:]
        candidate = line if not current else current + "\n" + line
        if len(candidate) <= limit:
            current = candidate
        else:
            parts.append(current)
            current = line
    if current:
        parts.append(current)
    return parts


def split_message(text: str, limit: int = MESSAGE_LIMIT) -> list[str]:
    """Split `text` into pieces of at most `limit` characters, between paragraphs where possible.

    Joining the pieces with a blank line gives the original text back (when no paragraph had to be cut).
    """
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    current = ""
    for paragraph in text.split("\n\n"):
        if len(paragraph) > limit:
            if current:
                parts.append(current)
                current = ""
            parts.extend(_cut(paragraph, limit))
            continue
        candidate = paragraph if not current else current + "\n\n" + paragraph
        if len(candidate) <= limit:
            current = candidate
        else:
            parts.append(current)
            current = paragraph
    if current:
        parts.append(current)
    return parts


def privacy_messages() -> list[str]:
    """The /privacy notice as the list of messages to send, in order."""
    return split_message(privacy_text())
