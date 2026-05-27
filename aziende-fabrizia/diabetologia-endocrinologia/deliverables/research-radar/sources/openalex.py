"""
OpenAlex — 250M+ works, 100k req/giorno, nessuna API key.
Il database più grande al mondo per letteratura scientifica open.
https://docs.openalex.org
"""
import requests
import time
from datetime import datetime

BASE = "https://api.openalex.org"
MAILTO = "fabrizia.aceto@gmail.com"  # cortesia verso OpenAlex, non obbligatorio


def _get(endpoint: str, params: dict) -> dict:
    params["mailto"] = MAILTO
    r = requests.get(f"{BASE}/{endpoint}", params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def search_works(
    query: str,
    max_results: int = 20,
    year_from: int = 2020,
    open_access_only: bool = False,
) -> list[dict]:
    """Cerca paper su OpenAlex con filtri anno e open access."""
    filters = [f"publication_year:>{year_from - 1}"]
    if open_access_only:
        filters.append("is_oa:true")

    params = {
        "search":    query,
        "filter":    ",".join(filters),
        "per-page":  min(max_results, 50),
        "sort":      "cited_by_count:desc",
        "select":    "id,doi,title,publication_year,cited_by_count,"
                     "open_access,primary_location,authorships,abstract_inverted_index,"
                     "concepts,type",
    }
    data = _get("works", params)
    results = []
    for w in data.get("results", []):
        results.append({
            "source":       "OpenAlex",
            "id":           w.get("id", ""),
            "title":        w.get("title", ""),
            "year":         str(w.get("publication_year", "")),
            "doi":          (w.get("doi") or "").replace("https://doi.org/", ""),
            "citations":    w.get("cited_by_count", 0),
            "open_access":  w.get("open_access", {}).get("is_oa", False),
            "journal":      (w.get("primary_location") or {}).get("source", {}).get("display_name", "") if w.get("primary_location") else "",
            "authors":      ", ".join(
                a["author"]["display_name"]
                for a in (w.get("authorships") or [])[:5]
            ),
            "abstract":     _reconstruct_abstract(w.get("abstract_inverted_index")),
            "concepts":     [c["display_name"] for c in (w.get("concepts") or [])[:5]],
            "url":          f"https://doi.org/{(w.get('doi') or '').replace('https://doi.org/', '')}" if w.get("doi") else "",
        })
    return results


def get_trending_concepts(query: str, top_n: int = 10) -> list[dict]:
    """Restituisce i concept/topic più associati a una query."""
    params = {
        "search":   query,
        "filter":   "publication_year:>2022",
        "per-page": 50,
        "select":   "concepts",
    }
    data = _get("works", params)
    concept_counts: dict[str, int] = {}
    for w in data.get("results", []):
        for c in w.get("concepts", []):
            name = c.get("display_name", "")
            concept_counts[name] = concept_counts.get(name, 0) + 1
    sorted_concepts = sorted(concept_counts.items(), key=lambda x: x[1], reverse=True)
    return [{"concept": k, "count": v} for k, v in sorted_concepts[:top_n]]


def get_citation_trend(query: str) -> dict[str, int]:
    """Conta paper per anno (trend pubblicazioni) per una query."""
    params = {
        "search":   query,
        "filter":   "publication_year:>2018",
        "per-page": 200,
        "select":   "publication_year",
    }
    data = _get("works", params)
    trend: dict[str, int] = {}
    for w in data.get("results", []):
        y = str(w.get("publication_year", ""))
        if y:
            trend[y] = trend.get(y, 0) + 1
    return dict(sorted(trend.items()))


def _reconstruct_abstract(inverted_index: dict | None) -> str:
    """OpenAlex salva gli abstract come indice invertito — lo ricostruisce."""
    if not inverted_index:
        return ""
    words = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            words[pos] = word
    return " ".join(words[i] for i in sorted(words))
