"""
Aggregatore multi-source — interroga tutte le API in parallelo,
deduplica per DOI/titolo, merge e ordina per rilevanza.
"""
import concurrent.futures
import hashlib
from typing import Callable

from sources.openalex       import search_works      as oa_search
from sources.semantic_scholar import search_papers   as ss_search
from sources.europe_pmc     import search_papers     as epmc_search
from sources.crossref       import search_papers     as cr_search


def _title_hash(title: str) -> str:
    """Fingerprint su titolo normalizzato per deduplicazione."""
    normalized = " ".join(title.lower().split())
    return hashlib.md5(normalized.encode()).hexdigest()[:12]


def _safe_run(fn: Callable, *args, **kwargs) -> list[dict]:
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        return [{"source": fn.__module__, "error": str(e), "title": ""}]


def search_all(
    query: str,
    max_per_source: int = 15,
    year_from: int = 2020,
    sources: list[str] | None = None,
) -> dict:
    """
    Interroga tutte le API in parallelo.
    Restituisce dict con risultati per source + lista unificata deduplicata.
    sources: sottoinsieme di ['openalex','semantic_scholar','europe_pmc','crossref']
             None = tutti
    """
    all_sources = {
        "openalex":        lambda: _safe_run(oa_search,   query, max_per_source, year_from),
        "semantic_scholar":lambda: _safe_run(ss_search,   query, max_per_source, year_from),
        "europe_pmc":      lambda: _safe_run(epmc_search, query, max_per_source, year_from),
        "crossref":        lambda: _safe_run(cr_search,   query, max_per_source, year_from),
    }
    active = {k: v for k, v in all_sources.items() if sources is None or k in sources}

    raw: dict[str, list[dict]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(fn): name for name, fn in active.items()}
        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            raw[name] = future.result()

    # Deduplicazione per DOI e poi per titolo
    seen_dois:   set[str] = set()
    seen_titles: set[str] = set()
    merged: list[dict] = []

    for source_name, papers in raw.items():
        for p in papers:
            if p.get("error"):
                continue
            doi = (p.get("doi") or "").strip().lower()
            title_fp = _title_hash(p.get("title", ""))

            if doi and doi in seen_dois:
                continue
            if title_fp in seen_titles:
                continue

            if doi:
                seen_dois.add(doi)
            seen_titles.add(title_fp)
            merged.append(p)

    # Ordine: citazioni desc (con fallback 0)
    merged.sort(key=lambda x: x.get("citations", 0), reverse=True)

    return {
        "by_source": raw,
        "merged":    merged,
        "stats": {
            "total_unique": len(merged),
            "by_source": {k: len([p for p in v if not p.get("error")]) for k, v in raw.items()},
            "errors":    {k: v[0]["error"] for k, v in raw.items() if v and v[0].get("error")},
        },
    }
