"""
Semantic Scholar — AI-powered, 200M+ paper, 100 req/min gratuiti, no key.
Unico a calcolare "influential citations" (citazioni che cambiano direzione della ricerca).
https://api.semanticscholar.org/graph/v1
"""
import requests
import time

BASE   = "https://api.semanticscholar.org/graph/v1"
FIELDS = (
    "paperId,externalIds,title,abstract,year,authors,"
    "citationCount,influentialCitationCount,isOpenAccess,"
    "publicationVenue,fieldsOfStudy,tldr"
)


def _get(endpoint: str, params: dict) -> dict:
    r = requests.get(f"{BASE}/{endpoint}", params=params, timeout=15)
    if r.status_code == 429:
        time.sleep(2)
        r = requests.get(f"{BASE}/{endpoint}", params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def search_papers(
    query: str,
    max_results: int = 20,
    year_from: int = 2020,
) -> list[dict]:
    """Cerca paper con ranking AI (influential citations)."""
    params = {
        "query":       query,
        "limit":       min(max_results, 100),
        "fields":      FIELDS,
        "year":        f"{year_from}-",
    }
    data = _get("paper/search", params)
    results = []
    for p in data.get("data", []):
        doi = (p.get("externalIds") or {}).get("DOI", "")
        pmid = (p.get("externalIds") or {}).get("PubMed", "")
        results.append({
            "source":        "Semantic Scholar",
            "id":            p.get("paperId", ""),
            "title":         p.get("title", ""),
            "year":          str(p.get("year", "")),
            "doi":           doi,
            "citations":     p.get("citationCount", 0),
            "influential":   p.get("influentialCitationCount", 0),
            "open_access":   p.get("isOpenAccess", False),
            "journal":       (p.get("publicationVenue") or {}).get("name", ""),
            "authors":       ", ".join(a["name"] for a in (p.get("authors") or [])[:5]),
            "abstract":      p.get("abstract", ""),
            "tldr":          (p.get("tldr") or {}).get("text", ""),  # AI summary di S2
            "fields":        p.get("fieldsOfStudy") or [],
            "url":           f"https://www.semanticscholar.org/paper/{p.get('paperId', '')}",
            "pubmed_url":    f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
        })
    return results


def get_paper_details(paper_id: str) -> dict:
    """Dettaglio completo di un paper (riferimenti, citazioni)."""
    params = {"fields": FIELDS + ",references,citations"}
    data = _get(f"paper/{paper_id}", params)
    return data
