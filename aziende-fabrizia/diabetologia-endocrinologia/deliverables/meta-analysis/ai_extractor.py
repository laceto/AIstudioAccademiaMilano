"""
GPT-4o estrae statistiche quantitative dagli abstract per la meta-analisi.
Gestisce i casi in cui i dati non sono estraibili (review narrative, qualitative, ecc.).
"""
import json
from openai import OpenAI

_SYSTEM = (
    "Sei un biostatistico esperto in meta-analisi cliniche. "
    "Analizzi abstract di studi medici ed estrai le statistiche necessarie "
    "per una meta-analisi quantitativa. Rispondi SOLO con JSON valido."
)


def extract_stats(paper: dict, outcome_of_interest: str, client: OpenAI) -> dict:
    """
    Estrae statistiche da un singolo paper.

    outcome_of_interest: es. "HbA1c reduction", "cardiovascular events", "body weight"

    Output:
      extractable: bool
      reason: str (se non estraibile)
      study_name: "Autore et al. (Anno)"
      study_type: RCT / cohort / caso-controllo / ...
      n_total / n_treatment / n_control
      outcome: descrizione outcome estratto
      effect_measure: MD / SMD / OR / RR / HR
      effect_size: valore numerico
      ci_lower / ci_upper: CI 95%
      se: standard error (calcolato se non riportato)
      p_value: float
      follow_up: durata follow-up
      notes: avvertenze cliniche
    """
    authors = paper.get("authors", "")
    year    = paper.get("year", "")
    last    = authors.split(",")[0].split()[-1] if authors else "N/D"
    study_name_hint = f"{last} et al. ({year})" if last != "N/D" else f"Studio {year}"

    prompt = f"""Abstract medico da analizzare per meta-analisi.

Outcome di interesse: "{outcome_of_interest}"

Titolo: {paper.get('title', '')}
Autori: {authors}
Anno: {year}
Rivista: {paper.get('journal', '')}
Abstract:
{paper.get('abstract', '')[:1200]}

Rispondi con JSON:
{{
  "extractable": true/false,
  "reason": "motivo se non estraibile (studio qualitativo, review, dati insufficienti, outcome diverso...)",
  "study_name": "{study_name_hint}",
  "study_type": "RCT | cohort | caso-controllo | cross-sectional | review | altro",
  "n_total": numero intero o null,
  "n_treatment": numero intero o null,
  "n_control": numero intero o null,
  "outcome": "descrizione precisa dell'outcome estratto",
  "effect_measure": "MD | SMD | OR | RR | HR",
  "effect_size": numero float o null,
  "ci_lower": numero float o null,
  "ci_upper": numero float o null,
  "p_value": numero float o null,
  "follow_up": "es. 24 settimane, 12 mesi",
  "notes": "avvertenze: ITT analysis, open-label, alto rischio bias, ecc."
}}

Regole:
- Se non trovi l'outcome di interesse, extractable=false
- Per OR/RR/HR usa scala originale (NON logaritmica)
- Se CI non è riportato ma c'è SD e n, calcola SE = SD/sqrt(n) per MD
- Sii conservativo: extractable=false se i dati sono ambigui"""

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
        max_tokens=500,
    )
    try:
        data = json.loads(resp.choices[0].message.content)
        data["doi"] = paper.get("doi", "")
        data["url"] = paper.get("url", "")
        return data
    except Exception:
        return {"extractable": False, "reason": "Errore parsing risposta AI",
                "study_name": study_name_hint}


def batch_extract(
    papers: list[dict],
    outcome: str,
    client: OpenAI,
    progress_callback=None,
) -> tuple[list[dict], list[dict]]:
    """
    Estrae statistiche da una lista di paper.
    Restituisce (extractable_list, skipped_list).
    """
    extractable = []
    skipped     = []

    for i, paper in enumerate(papers):
        if not paper.get("abstract"):
            skipped.append({**paper, "reason": "Abstract non disponibile"})
        else:
            result = extract_stats(paper, outcome, client)
            if result.get("extractable"):
                extractable.append(result)
            else:
                skipped.append(result)

        if progress_callback:
            progress_callback(i + 1, len(papers))

    return extractable, skipped


def generate_prisma_report(
    query: str,
    outcome: str,
    total_found: int,
    extractable: list[dict],
    skipped: list[dict],
    meta_result: dict,
    client: OpenAI,
) -> str:
    """Genera report PRISMA-style in Markdown con GPT-4o."""
    from datetime import datetime

    studies_summary = "\n".join([
        f"- {s.get('study_name','?')}: {s.get('effect_measure','?')} "
        f"{s.get('effect_size','?')} [{s.get('ci_lower','?')}, {s.get('ci_upper','?')}], "
        f"n={s.get('n_total','?')}"
        for s in extractable
    ])
    skipped_reasons = ", ".join(set(s.get("reason","?") for s in skipped[:10]))

    prompt = f"""Sei un ricercatore clinico che scrive un report di meta-analisi in italiano.

Query di ricerca: "{query}"
Outcome analizzato: "{outcome}"
Data: {datetime.now().strftime('%d %B %Y')}

Statistiche:
- Paper trovati: {total_found}
- Studi inclusi nella meta-analisi: {len(extractable)}
- Studi esclusi: {len(skipped)} ({skipped_reasons})

Studi inclusi:
{studies_summary}

Risultato pooled ({meta_result.get('method','?')}):
- Stima: {meta_result.get('estimate','?')}
  [{meta_result.get('ci_lower','?')}, {meta_result.get('ci_upper','?')}]
- p-value: {meta_result.get('p_value','?')}
- I²: {meta_result.get('I2','?'):.1f}% — {meta_result.get('heterogeneity','?')}
- Tau²: {meta_result.get('tau2','?'):.4f}

Scrivi un report strutturato:

# Meta-Analisi: {outcome}
## Metodi di ricerca
## Criteri di inclusione/esclusione
## Caratteristiche degli studi inclusi
## Risultati principali
## Eterogeneità
## Limitazioni
## Conclusioni cliniche
## Implicazioni per la pratica

*Disclaimer: Analisi basata su dati estratti da abstract — da verificare con full-text prima di pubblicazione.*"""

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=1800,
    )
    return resp.choices[0].message.content
