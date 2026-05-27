"""
Livello AI sopra i dati PubMed.
Usa GPT-4o per analisi singolo paper + sintesi complessiva della ricerca.
"""
import json
from openai import OpenAI

DISCLAIMER = (
    "\n\n---\n*Strumento di supporto alla ricerca clinica — "
    "non sostituisce la valutazione medica professionale.*"
)

_SYSTEM = (
    "Sei un assistente medico specializzato in diabetologia ed endocrinologia, "
    "che supporta la Dott.ssa Fabrizia Aceto nella revisione della letteratura scientifica. "
    "Rispondi sempre in italiano. Sii preciso, conciso e clinicamente rilevante."
)


def analyze_paper(paper: dict, client: OpenAI) -> dict:
    """
    Analisi strutturata di un singolo paper.
    Restituisce dict con summary, key_findings, clinical_implications, ecc.
    """
    if not paper.get("abstract"):
        return {
            "summary": "Abstract non disponibile per questo articolo.",
            "key_findings": [],
            "clinical_implications": [],
            "study_type": "N/D",
            "evidence_level": "N/D",
            "population": "N/D",
            "relevant_to_practice": False,
        }

    prompt = f"""Analizza questo abstract scientifico di medicina.

Titolo: {paper['title']}
Autori: {paper.get('authors', '')}
Rivista: {paper.get('journal', '')} ({paper.get('year', '')})
Abstract:
{paper['abstract']}

Rispondi SOLO con JSON valido (nessun testo fuori):
{{
    "summary": "Riassunto clinico in 2-3 frasi, cosa ha fatto lo studio e risultato principale",
    "key_findings": ["trovato 1", "trovato 2", "trovato 3"],
    "clinical_implications": ["implicazione pratica 1", "implicazione pratica 2"],
    "study_type": "RCT | meta-analisi | revisione sistematica | studio osservazionale | caso clinico | review narrativa | altro",
    "evidence_level": "alto | medio | basso",
    "population": "descrizione breve della popolazione studiata",
    "primary_outcome": "outcome principale dello studio",
    "relevant_to_practice": true
}}"""

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=600,
    )
    try:
        return json.loads(resp.choices[0].message.content)
    except json.JSONDecodeError:
        return {"summary": resp.choices[0].message.content, "key_findings": []}


def synthesize_research(
    papers: list[dict],
    analyses: list[dict],
    query: str,
    client: OpenAI,
) -> str:
    """Sintesi complessiva della letteratura trovata per una query."""
    if not papers:
        return "Nessun articolo da sintetizzare."

    # Costruisce input compatto per il LLM (max 12 paper)
    items = []
    for i, (p, a) in enumerate(zip(papers[:12], analyses[:12])):
        items.append(
            f"[{i+1}] {p.get('year','')} — {p['title']}\n"
            f"    Tipo: {a.get('study_type','?')} | Evidenza: {a.get('evidence_level','?')}\n"
            f"    Sintesi: {a.get('summary','')}\n"
            f"    Findings: {'; '.join(a.get('key_findings',[]))}"
        )
    corpus = "\n\n".join(items)

    prompt = f"""Sei un ricercatore senior in diabetologia ed endocrinologia.
Query di ricerca: "{query}"
Articoli analizzati ({len(papers)} totali, mostro i primi 12):

{corpus}

Scrivi una sintesi della letteratura strutturata così:

## Stato attuale della ricerca
(3-4 frasi che catturano il consenso attuale)

## Tendenze emergenti
(3-5 punti bullet con le direzioni più promettenti)

## Gap nella letteratura
(Cosa manca ancora? Studi futuri necessari?)

## Implicazioni pratiche per il clinico
(Cosa cambia nella pratica quotidiana della Dott.ssa Fabrizia?)

## Livello di evidenza complessivo
(Commento critico sulla qualità degli studi trovati)
{DISCLAIMER}"""

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=1200,
    )
    return resp.choices[0].message.content


def generate_clinical_question(
    papers: list[dict], analyses: list[dict], client: OpenAI
) -> str:
    """Genera 3 domande cliniche aperte basate sulla letteratura trovata."""
    titles = "\n".join(f"- {p['title']}" for p in papers[:8])
    prompt = f"""Basandoti su questi titoli di articoli scientifici in diabetologia:
{titles}

Genera 3 domande cliniche aperte che un medico potrebbe voler approfondire,
in formato numerato. Sii specifico e clinicamente rilevante.{DISCLAIMER}"""

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
        max_tokens=400,
    )
    return resp.choices[0].message.content
