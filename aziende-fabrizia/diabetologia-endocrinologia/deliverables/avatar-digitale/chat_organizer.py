"""
Chat organizer — categorizza i messaggi per topic clinico/professionale
e genera digest giornaliero via GPT-4o.
Funziona sia su chat Telegram che su export WhatsApp (.txt).
"""
import json
import re
from datetime import datetime
from openai import OpenAI

# Categorie tassonomia medica/professionale
CATEGORIES = [
    "clinica_diabetologia",
    "clinica_endocrinologia",
    "ricerca_letteratura",
    "ecm_formazione",
    "casi_clinici",
    "linee_guida_protocolli",
    "organizzazione_lavoro",
    "notizie_sanita",
    "community_sociale",
    "altro",
]

_SYSTEM = (
    "Sei l'assistente della Dott.ssa Fabrizia Aceto, "
    "diabetologa ed endocrinologa. "
    "Analizza conversazioni di gruppi medici professionali. "
    "Rispondi sempre in italiano. Sii conciso e clinicamente preciso."
)


def parse_whatsapp_export(text: str) -> list[dict]:
    """
    Parsa un export WhatsApp (.txt) nel formato standard:
    [DD/MM/YYYY, HH:MM:SS] Mittente: Testo
    """
    pattern = re.compile(
        r"\[(\d{2}/\d{2}/\d{4}),\s(\d{2}:\d{2}(?::\d{2})?)\]\s([^:]+):\s(.+)"
    )
    messages = []
    for line in text.splitlines():
        m = pattern.match(line.strip())
        if m:
            date_str, time_str, sender, text_body = m.groups()
            try:
                dt = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M:%S")
            except ValueError:
                dt = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M")
            messages.append({
                "sender": sender.strip(),
                "text":   text_body.strip(),
                "date":   dt.isoformat(),
            })
    return messages


def categorize_messages(
    messages: list[dict],
    client: OpenAI,
    group_name: str = "",
) -> dict:
    """
    Chiede a GPT-4o di categorizzare un batch di messaggi.
    Restituisce dict con categoria → lista messaggi + highlights.
    """
    if not messages:
        return {}

    sample = messages[:60]  # max 60 messaggi per batch
    corpus = "\n".join(
        f"[{m['sender']}]: {m['text'][:200]}" for m in sample
    )

    prompt = f"""Gruppo: "{group_name}"
Messaggi (ultimi {len(sample)} su {len(messages)} totali):

{corpus}

Classifica questa conversazione e rispondi SOLO con JSON:
{{
    "topic_principale": "una delle categorie: {', '.join(CATEGORIES)}",
    "argomenti_trattati": ["argomento 1", "argomento 2", "argomento 3"],
    "messaggi_rilevanti": [
        {{"sender": "...", "text": "citazione breve", "motivo": "perché è rilevante"}}
    ],
    "azioni_richieste": ["azione 1 se presente"],
    "priorita": "alta | media | bassa",
    "sintesi": "2-3 frasi su cosa è successo nel gruppo"
}}"""

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=600,
    )
    try:
        result = json.loads(resp.choices[0].message.content)
        result["group_name"]   = group_name
        result["total_messages"] = len(messages)
        result["analyzed_at"]  = datetime.now().isoformat()
        return result
    except Exception:
        return {"group_name": group_name, "error": "parsing fallito"}


def generate_daily_digest(
    categorized_groups: list[dict],
    client: OpenAI,
    date_str: str = "",
) -> str:
    """
    Genera il digest giornaliero di tutte le community di Fabrizia.
    Output: Markdown formattato pronto per Google Drive.
    """
    if not date_str:
        date_str = datetime.now().strftime("%d %B %Y")

    groups_summary = "\n\n".join([
        f"**{g.get('group_name', 'Gruppo')}** [{g.get('topic_principale', '?')}] "
        f"— priorità {g.get('priorita', '?')}\n"
        f"Sintesi: {g.get('sintesi', '')}\n"
        f"Argomenti: {', '.join(g.get('argomenti_trattati', []))}\n"
        f"Azioni: {'; '.join(g.get('azioni_richieste', [])) or 'nessuna'}"
        for g in categorized_groups if "error" not in g
    ])

    prompt = f"""Sei l'assistente personale della Dott.ssa Fabrizia Aceto.
Data: {date_str}

Attività nelle sue community professionali oggi:
{groups_summary}

Scrivi un **digest giornaliero** in Markdown strutturato così:

# Digest Community — {date_str}

## 🔴 Priorità Alta
(solo i gruppi con priorità alta e azioni richieste)

## 📋 Aggiornamenti Clinici
(novità cliniche, linee guida, casi interessanti)

## 🎓 Formazione & Ricerca
(ECM, articoli, congressi)

## 💬 Community & Network
(aggiornamenti sociali/organizzativi minori)

## ✅ To-Do di Fabrizia
(lista azioni concrete emerse dalla giornata)

---
*Generato automaticamente dall'Avatar Digitale di Fabrizia — {date_str}*
*Strumento di supporto — non sostituisce la valutazione clinica.*"""

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": prompt},
        ],
        temperature=0.2,
        max_tokens=1500,
    )
    return resp.choices[0].message.content
