"""
Avatar Persona della Dott.ssa Fabrizia Aceto.
Genera risposte, post LinkedIn, commenti medici nel suo stile professionale.
"""
from openai import OpenAI
from datetime import datetime

DISCLAIMER = (
    "\n\n---\n*Bozza generata dall'Avatar Digitale — "
    "revisione e approvazione della Dott.ssa Fabrizia Aceto richiesta prima dell'invio.*"
)

# Profilo identità di Fabrizia — da arricchire nel tempo
FABRIZIA_PROFILE = """
Nome: Dott.ssa Fabrizia Aceto
Specializzazione: Diabetologia ed Endocrinologia
Approccio: medico moderno che integra tecnologia e clinica
Stile comunicativo: professionale ma accessibile, empatico, basato sull'evidenza
Valori: personalizzazione della cura, tecnologia al servizio del paziente, aggiornamento continuo
Interessi clinici: CGM, terapie GLP-1, endocrinologia riproduttiva, PCOS, tiroide
Partecipazione attiva in: SID, AME, SIE, gruppi Telegram medici italiani
Lingua: italiano (preferita), inglese per letteratura scientifica
Tono: autorevole ma non cattedratico, colloquiale con i colleghi, rassicurante con i pazienti
"""

_SYSTEM = f"""Sei l'avatar digitale della Dott.ssa Fabrizia Aceto.
Scrivi ESATTAMENTE come lei, nel suo stile.

Profilo:
{FABRIZIA_PROFILE}

Regole:
- Scrivi in prima persona ("Nella mia esperienza...", "Ho osservato che...")
- Usa terminologia medica precisa ma comprensibile
- Cita l'evidenza quando rilevante (es. "Come riportato in uno studio recente su Diabetes Care...")
- Non fare affermazioni terapeutiche definitive senza qualifiche appropriate
- Ogni output medico include: "Per qualsiasi decisione clinica, si raccomanda valutazione specialistica"
- Lunghezza adatta al contesto (tweet=breve, LinkedIn=medio, risposta gruppo=conversazionale)
"""


def draft_community_reply(
    original_message: str,
    group_context: str,
    client: OpenAI,
    style: str = "collegiale",
) -> str:
    """
    Bozza risposta di Fabrizia a un messaggio in un gruppo medico.
    style: collegiale | formale | didattico
    """
    prompt = f"""Contesto gruppo: {group_context}
Messaggio a cui rispondere:
"{original_message}"

Stile richiesto: {style}

Scrivi una risposta di Fabrizia al messaggio.
Massimo 5-6 righe, tono {style}.{DISCLAIMER}"""

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": prompt},
        ],
        temperature=0.4,
        max_tokens=400,
    )
    return resp.choices[0].message.content


def draft_linkedin_post(
    topic: str,
    source: str,
    client: OpenAI,
    post_type: str = "insight_clinico",
) -> str:
    """
    Bozza post LinkedIn nel registro professionale di Fabrizia.
    post_type: insight_clinico | aggiornamento_ricerca | riflessione_professionale | caso_anonimizzato
    """
    type_instructions = {
        "insight_clinico":        "Condividi un insight dalla pratica clinica quotidiana",
        "aggiornamento_ricerca":  "Commenta un paper recente o tendenza della letteratura",
        "riflessione_professionale": "Riflessione sul ruolo del medico moderno e la tecnologia",
        "caso_anonimizzato":      "Caso clinico didattico completamente anonimizzato (no dati identificativi)",
    }

    prompt = f"""Tipo di post: {type_instructions.get(post_type, 'post professionale')}
Argomento/fonte: {topic}
Fonte/contesto: {source}

Scrivi un post LinkedIn di Fabrizia:
- Apertura che cattura l'attenzione (no cliché)
- Contenuto sostanziale (3-5 paragrafi brevi)
- Conclusione con domanda aperta ai colleghi
- 3-5 hashtag rilevanti (#diabetologia #endocrinologia #medicinadigitale ecc.)
- Lunghezza: 150-250 parole{DISCLAIMER}"""

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": prompt},
        ],
        temperature=0.5,
        max_tokens=600,
    )
    return resp.choices[0].message.content


def draft_group_summary_post(
    digest_content: str,
    client: OpenAI,
) -> str:
    """
    Da un digest di community, genera un post di condivisione per i colleghi.
    """
    prompt = f"""Basandoti su questo digest delle community mediche:

{digest_content[:1500]}

Scrivi un breve messaggio di Fabrizia da condividere con un gruppo di colleghi medici
(stile Telegram, informale ma professionale, max 5 righe).
Evidenzia 1-2 spunti clinici o novità più rilevanti.{DISCLAIMER}"""

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": prompt},
        ],
        temperature=0.3,
        max_tokens=300,
    )
    return resp.choices[0].message.content


def enrich_profile(new_info: str) -> str:
    """Aggiunge nuove informazioni al profilo di Fabrizia (chiamato manualmente)."""
    global FABRIZIA_PROFILE
    FABRIZIA_PROFILE += f"\n{new_info}"
    return f"Profilo aggiornato. Nuova info: {new_info}"
