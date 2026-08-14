"""
OpenAlex search tool — reemplazo de Semantic Scholar.

OpenAlex es la base de datos académica open-access más grande del mundo:
- 250M+ papers, mismo coverage que Semantic Scholar
- Sin API key requerida
- Rate limit generoso: 10 req/seg en polite pool (vs 1 req/seg de SS)
- Mantenido por OurResearch, financiado por Mellon Foundation / Microsoft

API docs: https://docs.openalex.org/api-entities/works/search-works

Diferencias internas vs Semantic Scholar:
- Abstract viene como "inverted index" — se reconstruye en _reconstruct_abstract()
- Journal está en primary_location.source.display_name
- DOI viene sin prefijo "https://doi.org/"

Output: idéntico al de semantic_scholar.py — compatible con todos los tools del agente.
"""

import os
import requests
from typing import Optional

BASE_URL = "https://api.openalex.org/works"
MAILTO = "datos.dpn@gmail.com"  # polite pool: mejor rate limit

FIELDS = ",".join([
    "id",
    "title",
    "abstract_inverted_index",
    "publication_year",
    "authorships",
    "primary_location",
    "doi",
    "ids",
    "cited_by_count",
    "open_access",
])


def _reconstruct_abstract(inverted_index: Optional[dict]) -> str:
    """
    OpenAlex almacena abstracts como índice invertido: {"word": [pos1, pos2], ...}
    Esta función reconstruye el texto en orden de posición.
    """
    if not inverted_index:
        return "No abstract available"
    word_at = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            word_at[pos] = word
    if not word_at:
        return "No abstract available"
    return " ".join(word_at[i] for i in sorted(word_at.keys()))


def search_literature(query: str, max_results: int = 10) -> dict:
    """
    Busca literatura científica via OpenAlex (250M+ papers, todos los dominios).
    Drop-in replacement para semantic_scholar.search_literature() — mismo output.

    Args:
        query: Búsqueda en inglés, específica
        max_results: Cantidad de resultados (5-20 recomendado, max 200)

    Returns:
        dict con 'results' list y 'total_found' count
        Cada result: title, abstract, year, journal, authors, url, doi, pmid,
                      pdf_url, citation_count, paper_id
    """
    params = {
        "search": query,
        "per_page": min(max_results, 200),
        "select": FIELDS,
        "mailto": MAILTO,
        "sort": "relevance_score:desc",
    }

    try:
        resp = requests.get(BASE_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.HTTPError as e:
        # Fallback a Semantic Scholar si OpenAlex falla
        if resp.status_code in (429, 503):
            return _fallback_semantic_scholar(query, max_results, reason=str(e))
        return {
            "error": f"OpenAlex search failed ({resp.status_code}): {str(e)}",
            "results": [],
            "total_found": 0,
            "query": query,
            "source": "openalex",
        }
    except Exception as e:
        return _fallback_semantic_scholar(query, max_results, reason=str(e))

    meta = data.get("meta", {})
    total = meta.get("count", 0)
    works = data.get("results", [])

    results = []
    for w in works:
        # DOI — OpenAlex lo devuelve como "https://doi.org/10.xxxx/..."
        doi_raw = w.get("doi") or ""
        doi = doi_raw.replace("https://doi.org/", "") if doi_raw else None

        # PMID
        ids = w.get("ids") or {}
        pmid_raw = ids.get("pmid") or ""
        pmid = pmid_raw.replace("https://pubmed.ncbi.nlm.nih.gov/", "").strip("/") if pmid_raw else None

        # URL — preferir DOI, fallback a OpenAlex page
        openalex_id = w.get("id", "")  # "https://openalex.org/W..."
        if doi:
            url = f"https://doi.org/{doi}"
        elif pmid:
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        else:
            url = openalex_id  # URL directa a OpenAlex

        # Journal
        primary_loc = w.get("primary_location") or {}
        source = primary_loc.get("source") or {}
        journal = source.get("display_name") or "Unknown"

        # Authors (primeros 3)
        authorships = w.get("authorships") or []
        author_names_list = []
        for a in authorships[:3]:
            author = a.get("author") or {}
            name = author.get("display_name", "")
            if name:
                author_names_list.append(name)
        authors = ", ".join(author_names_list)
        if len(authorships) > 3:
            authors += " et al."

        # PDF open access
        oa = w.get("open_access") or {}
        pdf_url = oa.get("oa_url")

        # Abstract (reconstruir desde inverted index)
        abstract = _reconstruct_abstract(w.get("abstract_inverted_index"))

        results.append({
            "title":          w.get("title") or "No title",
            "abstract":       abstract,
            "year":           str(w.get("publication_year") or "Unknown"),
            "journal":        journal,
            "authors":        authors,
            "url":            url,
            "doi":            doi,
            "pmid":           pmid,
            "pdf_url":        pdf_url,
            "citation_count": w.get("cited_by_count", 0),
            "paper_id":       openalex_id,
        })

    return {
        "query":       query,
        "total_found": total,
        "returned":    len(results),
        "results":     results,
        "source":      "openalex",
    }


def _fallback_semantic_scholar(query: str, max_results: int, reason: str = "") -> dict:
    """
    Fallback a Semantic Scholar si OpenAlex no responde.
    Solo se usa si OpenAlex falla — no al revés.
    """
    try:
        from tools.semantic_scholar import search_literature as ss_search
        result = ss_search(query, max_results)
        result["source"] = "semantic_scholar_fallback"
        result["fallback_reason"] = reason
        return result
    except Exception as e:
        return {
            "error": f"OpenAlex falló ({reason}) y Semantic Scholar también falló: {str(e)}",
            "results": [],
            "total_found": 0,
            "query": query,
            "source": "none",
        }
