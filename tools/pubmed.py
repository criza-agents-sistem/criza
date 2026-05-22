"""
PubMed search tool via NCBI E-utilities.
No API key required for low volume. For production, add NCBI_API_KEY to .env.
"""

import requests
import xml.etree.ElementTree as ET
from typing import Optional


def search_pubmed(query: str, max_results: int = 10) -> dict:
    """
    Search PubMed and return titles + abstracts.

    Args:
        query: Search string (use English, be specific)
        max_results: Number of results (5-20 recommended)

    Returns:
        dict with 'results' list and 'total_found' count
    """
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

    # Step 1: Search for PMIDs
    search_params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
        "sort": "relevance",
        "usehistory": "y",
    }

    try:
        search_resp = requests.get(
            f"{base_url}esearch.fcgi", params=search_params, timeout=30
        )
        search_resp.raise_for_status()
        search_data = search_resp.json()
    except Exception as e:
        return {"error": f"PubMed search failed: {str(e)}", "results": [], "total_found": 0}

    pmids = search_data["esearchresult"]["idlist"]
    total = int(search_data["esearchresult"]["count"])

    if not pmids:
        return {"results": [], "total_found": 0, "query": query}

    # Step 2: Fetch abstracts
    fetch_params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "rettype": "abstract",
        "retmode": "xml",
    }

    try:
        fetch_resp = requests.get(
            f"{base_url}efetch.fcgi", params=fetch_params, timeout=30
        )
        fetch_resp.raise_for_status()
        root = ET.fromstring(fetch_resp.content)
    except Exception as e:
        return {"error": f"PubMed fetch failed: {str(e)}", "results": [], "total_found": total}

    # Step 3: Parse articles
    articles = []
    for article in root.findall(".//PubmedArticle"):
        pmid_el    = article.find(".//PMID")
        title_el   = article.find(".//ArticleTitle")
        year_el    = article.find(".//PubDate/Year")
        journal_el = article.find(".//Journal/Title")

        # Abstract can have multiple sections
        abstract_parts = article.findall(".//AbstractText")
        abstract = " ".join(
            (el.get("Label", "") + ": " if el.get("Label") else "") + (el.text or "")
            for el in abstract_parts
        ).strip()

        pmid = pmid_el.text if pmid_el is not None else "Unknown"
        articles.append({
            "pmid":     pmid,
            "title":    title_el.text if title_el is not None else "No title",
            "abstract": abstract or "No abstract available",
            "year":     year_el.text if year_el is not None else "Unknown",
            "journal":  journal_el.text if journal_el is not None else "Unknown",
            "url":      f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        })

    return {
        "query":       query,
        "total_found": total,
        "returned":    len(articles),
        "results":     articles,
    }
