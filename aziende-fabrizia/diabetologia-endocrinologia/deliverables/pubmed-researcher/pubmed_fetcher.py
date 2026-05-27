"""
NCBI E-utilities wrapper — ufficiale, gratuito, no scraping.
Rate limit: 3 req/s senza API key, 10 req/s con NCBI_API_KEY.
"""
import os
import time
import requests
import xml.etree.ElementTree as ET

NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_EMAIL = "fabrizia.aceto@gmail.com"  # richiesto da NCBI per identificazione
_API_KEY = os.getenv("NCBI_API_KEY", "")  # opzionale, aumenta rate limit


def _base_params() -> dict:
    p = {"email": _EMAIL}
    if _API_KEY:
        p["api_key"] = _API_KEY
    return p


def search_pubmed(
    query: str,
    max_results: int = 20,
    date_range: tuple[str, str] | None = None,
    sort: str = "relevance",
) -> list[str]:
    """
    Cerca su PubMed e restituisce lista di PMID.
    date_range: ("2022/01/01", "2024/12/31")
    sort: "relevance" | "pub_date"
    """
    params = {
        **_base_params(),
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
        "sort": sort,
    }
    if date_range:
        params["mindate"] = date_range[0]
        params["maxdate"] = date_range[1]
        params["datetype"] = "pdat"

    r = requests.get(f"{NCBI_BASE}/esearch.fcgi", params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    return data["esearchresult"]["idlist"]


def fetch_papers(pmids: list[str]) -> list[dict]:
    """Scarica dettagli completi per una lista di PMID."""
    if not pmids:
        return []
    time.sleep(0.35)  # rispetto rate limit NCBI
    params = {
        **_base_params(),
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
        "rettype": "abstract",
    }
    r = requests.get(f"{NCBI_BASE}/efetch.fcgi", params=params, timeout=30)
    r.raise_for_status()
    return _parse_xml(r.text)


def _parse_xml(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    papers = []

    for article in root.findall(".//PubmedArticle"):
        p: dict = {}

        pmid = article.find(".//PMID")
        p["pmid"] = pmid.text if pmid is not None else ""

        title = article.find(".//ArticleTitle")
        p["title"] = "".join(title.itertext()) if title is not None else "(no title)"

        # Abstract: può essere strutturato (BACKGROUND / METHODS / RESULTS / CONCLUSIONS)
        abstract_nodes = article.findall(".//AbstractText")
        parts = []
        for node in abstract_nodes:
            label = node.get("Label", "")
            text = "".join(node.itertext()).strip()
            parts.append(f"**{label}:** {text}" if label else text)
        p["abstract"] = "\n".join(parts) if parts else ""

        # Autori (max 6, poi "et al.")
        authors = []
        for author in article.findall(".//Author"):
            last = author.find("LastName")
            fore = author.find("Initials")
            if last is not None:
                name = last.text
                if fore is not None:
                    name += f" {fore.text}"
                authors.append(name)
        if len(authors) > 6:
            p["authors"] = ", ".join(authors[:6]) + " et al."
        else:
            p["authors"] = ", ".join(authors)

        journal = article.find(".//Journal/Title")
        p["journal"] = journal.text if journal is not None else ""

        year = article.find(".//PubDate/Year")
        p["year"] = year.text if year is not None else ""

        doi = article.find(".//ArticleId[@IdType='doi']")
        p["doi"] = doi.text if doi is not None else ""
        p["url"] = f"https://pubmed.ncbi.nlm.nih.gov/{p['pmid']}/"

        mesh_terms = [m.find("DescriptorName").text
                      for m in article.findall(".//MeshHeading")
                      if m.find("DescriptorName") is not None]
        p["mesh"] = mesh_terms[:8]

        papers.append(p)

    return papers
