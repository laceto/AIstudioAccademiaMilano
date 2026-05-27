"""
Europe PMC — PubMed + letteratura europea + grants + patents.
Completamente gratuito, no key. Include full-text quando disponibile.
https://europepmc.org/RestfulWebService
"""
import requests

BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"


def search_papers(
    query: str,
    max_results: int = 20,
    year_from: int = 2020,
    source: str = "MED",  # MED=PubMed, PPR=preprint, PAT=patents, ETH=theses
) -> list[dict]:
    """
    Cerca su Europe PMC.
    source: 'MED' (PubMed), 'PPR' (preprint), 'ALL' (tutto)
    """
    q = f"{query} AND (FIRST_PDATE:[{year_from}-01-01 TO 9999-12-31])"
    if source != "ALL":
        q += f" AND SRC:{source}"

    params = {
        "query":       q,
        "format":      "json",
        "resultType":  "core",
        "pageSize":    min(max_results, 25),
        "sort":        "CITED desc",
    }
    r = requests.get(f"{BASE}/search", params=params, timeout=15)
    r.raise_for_status()
    data = r.json()

    results = []
    for a in data.get("resultList", {}).get("result", []):
        results.append({
            "source":      "Europe PMC",
            "id":          a.get("id", ""),
            "pmid":        a.get("pmid", ""),
            "title":       a.get("title", ""),
            "year":        str(a.get("pubYear", "")),
            "doi":         a.get("doi", ""),
            "citations":   a.get("citedByCount", 0),
            "open_access": a.get("isOpenAccess", "N") == "Y",
            "journal":     a.get("journalTitle", ""),
            "authors":     a.get("authorString", ""),
            "abstract":    a.get("abstractText", ""),
            "has_fulltext": a.get("hasTextMinedTerms", "N") == "Y",
            "url":         f"https://europepmc.org/article/med/{a.get('pmid', '')}" if a.get("pmid") else "",
        })
    return results


def get_preprints(query: str, max_results: int = 10) -> list[dict]:
    """Scarica preprint recenti (medRxiv/bioRxiv indicizzati su Europe PMC)."""
    return search_papers(query, max_results=max_results, source="PPR", year_from=2023)
