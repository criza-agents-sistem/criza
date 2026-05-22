"""
Semantic Scholar search tool via public API.
Covers 200M+ papers across all scientific domains — broader than PubMed.
No API key required for basic use (100 req/5min). Add SEMANTIC_SCHOLAR_API_KEY
to .env for higher limits (1 req/sec).

API docs: https://api.semanticscholar.org/api-docs/graph
"""

import os
import requests
from typing import Optional


FIELDS = "title,abstract,year,authors,venue,externalIds,openAccessPdf,citationCount"
BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/search"


def search_literature(query: str, max_results: int = 10) -> dict:
    """
    Search Semantic Scholar and return titles + abstracts.
    Drop-in replacement for search_pubmed() — same output structure.

    Args:
        query: Search string (use English, be specific)
        max_results: Number of results (5-20 recommended)

    Returns:
        dict with 'results' list and 'total_found' count
        Each result has: title, abstract, year, journal, url, doi, pmid, citation_count
    """
    headers = {}
    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key

    params = {
        "query": query,
        "limit": min(max_results, 100),
        "fields": FIELDS,
    }

    try:
        resp = requests.get(BASE_URL, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return {
            "error": f"Semantic Scholar search failed: {str(e)}",
            "results": [],
            "total_found": 0,
            "query": query,
        }

    total = data.get("total", 0)
    papers = data.get("data", [])

    results = []
    for p in papers:
        # Extract external IDs
        ext_ids = p.get("externalIds") or {}
        pmid = ext_ids.get("PubMed")
        doi = ext_ids.get("DOI")

        # Build URL — prefer DOI, fall back to Semantic Scholar page
        paper_id = p.get("paperId", "")
        if doi:
            url = f"https://doi.org/{doi}"
        elif pmid:
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        else:
            url = f"https://www.semanticscholar.org/paper/{paper_id}"

        # Authors (first 3)
        authors = p.get("authors") or []
        author_names = ", ".join(a.get("name", "") for a in authors[:3])
        if len(authors) > 3:
            author_names += " et al."

        # Open access PDF
        oa_pdf = p.get("openAccessPdf") or {}
        pdf_url = oa_pdf.get("url")

        results.append({
            "title":          p.get("title") or "No title",
            "abstract":       p.get("abstract") or "No abstract available",
            "year":           str(p.get("year") or "Unknown"),
            "journal":        p.get("venue") or "Unknown",
            "authors":        author_names,
            "url":            url,
            "doi":            doi,
            "pmid":           pmid,
            "pdf_url":        pdf_url,
            "citation_count": p.get("citationCount", 0),
            "paper_id":       paper_id,
        })

    return {
        "query":       query,
        "total_found": total,
        "returned":    len(results),
        "results":     results,
    }
