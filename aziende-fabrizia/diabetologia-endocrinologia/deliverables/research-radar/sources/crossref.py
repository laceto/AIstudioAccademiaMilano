"""
CrossRef — 100M+ DOI, impact factor, citazioni, journal ranking.
Completamente gratuito. Polite pool con mailto = rate limit più alto.
https://api.crossref.org/swagger-ui/index.html
"""
import requests

BASE   = "https://api.crossref.org"
MAILTO = "fabrizia.aceto@gmail.com"


def _get(endpoint: str, params: dict) -> dict:
    params["mailto"] = MAILTO
    r = requests.get(f"{BASE}/{endpoint}", params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def search_papers(
    query: str,
    max_results: int = 20,
    year_from: int = 2020,
    doc_type: str = "journal-article",
) -> list[dict]:
    """Cerca su CrossRef per rilevanza + anno."""
    params = {
        "query":          query,
        "rows":           min(max_results, 50),
        "filter":         f"type:{doc_type},from-pub-date:{year_from}",
        "select":         "DOI,title,author,published,container-title,"
                          "is-referenced-by-count,abstract,URL,subject,ISSN",
        "sort":           "is-referenced-by-count",
        "order":          "desc",
    }
    data = _get("works", params)
    results = []
    for item in data.get("message", {}).get("items", []):
        pub = item.get("published", {})
        parts = pub.get("date-parts", [[""]])[0]
        year = str(parts[0]) if parts else ""

        authors_raw = item.get("author", [])
        authors = ", ".join(
            f"{a.get('family', '')} {a.get('given', [''])[0] if isinstance(a.get('given'), list) else a.get('given','')}"
            for a in authors_raw[:5]
        ).strip()

        titles = item.get("title", [])
        containers = item.get("container-title", [])

        results.append({
            "source":    "CrossRef",
            "doi":       item.get("DOI", ""),
            "title":     titles[0] if titles else "",
            "year":      year,
            "authors":   authors,
            "journal":   containers[0] if containers else "",
            "citations": item.get("is-referenced-by-count", 0),
            "abstract":  item.get("abstract", ""),
            "subjects":  item.get("subject", [])[:5],
            "url":       item.get("URL", "") or f"https://doi.org/{item.get('DOI','')}",
        })
    return results


def get_journal_works(issn: str, max_results: int = 10) -> list[dict]:
    """Ultimi paper da una specifica rivista (per ISSN)."""
    params = {
        "filter":  f"issn:{issn}",
        "rows":    min(max_results, 25),
        "sort":    "published",
        "order":   "desc",
        "select":  "DOI,title,author,published,is-referenced-by-count",
    }
    data = _get("works", params)
    items = data.get("message", {}).get("items", [])
    return [{"doi": i.get("DOI", ""), "title": (i.get("title") or [""])[0],
             "citations": i.get("is-referenced-by-count", 0),
             "url": f"https://doi.org/{i.get('DOI','')}"}
            for i in items]


# ISSN delle riviste chiave per Fabrizia
JOURNALS = {
    "Diabetes Care":          "0149-5992",
    "Diabetologia":           "0012-186X",
    "Lancet Diabetes & Endo": "2213-8587",
    "JCEM":                   "0021-972X",
    "NEJM":                   "0028-4793",
    "Thyroid":                "1050-7256",
}
