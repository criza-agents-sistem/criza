"""
PubMed (NCBI E-utilities) — utilidad compartida CRIZA.

Etapa 22 (cont., 2026-09-14): investigando qué herramientas nuevas sumó Anthropic para agentes
científicos (Claude Science / Claude for Life Sciences), PubMed apareció como conector propio —
verificado real hoy que trae cobertura biomédica que OpenAlex no cubre igual (vocabulario MeSH):
"digestate valorization value-added products" devolvió 94 resultados reales, con expansión MeSH
automática (ej. "digest" -> digestión/digestibilidad/etc.), más preciso para temas de
microbiología/bioquímica que una búsqueda de texto libre.

No reemplaza utils/openalex.py::search_literature_exhaustivo (esa sigue siendo la fuente
exhaustiva-por-diseño de literatura global) — este es un complemento de precisión biomédica,
mismo criterio que search_kegg/search_rhea/search_pubchem/search_chebi (tools de dominio
específico, no otro pilar de búsqueda exhaustiva obligatoria).

Sin API key: ~3 req/seg (NCBI). Con NCBI_API_KEY (opcional, .env): 10 req/seg — ver
scientific_agent/.env.example, mismo criterio ya documentado ahí para su propia integración.
"""

import os
import xml.etree.ElementTree as ET

import requests

_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
_TIMEOUT = 30


def search_pubmed(query: str, max_results: int = 20, abstract_max_chars: int = 600) -> dict:
    """
    Busca en PubMed (NCBI E-utilities) — título, abstract truncado, año, revista y link por
    resultado.

    Args:
        query: Búsqueda en inglés (sintaxis PubMed con field tags, o texto libre).
        max_results: Techo de resultados a traer — no exhaustiva por diseño (a diferencia de
            utils/openalex.py::search_literature_exhaustivo).
        abstract_max_chars: Trunca cada abstract — mismo criterio que utils/openalex.py y
            utils/brightdata_serp.py (Etapa 22: sin truncar, una corrida real reventó el contexto
            del modelo).

    Returns:
        dict con 'results' [{pmid, titulo, resumen, año, revista, url}], 'total_found', 'source'.
        {"error": ...} si falla el pedido a NCBI (la búsqueda o el fetch de abstracts).
    """
    api_key = os.getenv("NCBI_API_KEY", "")
    extra = {"api_key": api_key} if api_key else {}

    search_params = {
        "db": "pubmed", "term": query, "retmax": max_results,
        "retmode": "json", "sort": "relevance", **extra,
    }
    try:
        resp = requests.get(f"{_BASE_URL}esearch.fcgi", params=search_params, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return {"error": f"PubMed esearch falló: {e}", "results": [], "total_found": 0, "source": "pubmed"}

    pmids = data.get("esearchresult", {}).get("idlist", [])
    total = int(data.get("esearchresult", {}).get("count", 0) or 0)
    if not pmids:
        return {"query": query, "results": [], "total_found": total, "source": "pubmed"}

    fetch_params = {
        "db": "pubmed", "id": ",".join(pmids), "rettype": "abstract", "retmode": "xml", **extra,
    }
    try:
        resp = requests.get(f"{_BASE_URL}efetch.fcgi", params=fetch_params, timeout=_TIMEOUT)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except Exception as e:
        return {"error": f"PubMed efetch falló: {e}", "results": [], "total_found": total, "source": "pubmed"}

    resultados = []
    for article in root.findall(".//PubmedArticle"):
        pmid_el = article.find(".//PMID")
        title_el = article.find(".//ArticleTitle")
        year_el = article.find(".//PubDate/Year")
        journal_el = article.find(".//Journal/Title")

        abstract_parts = article.findall(".//AbstractText")
        abstract = " ".join(
            (el.get("Label", "") + ": " if el.get("Label") else "") + (el.text or "")
            for el in abstract_parts
        ).strip()
        if len(abstract) > abstract_max_chars:
            abstract = abstract[:abstract_max_chars] + "…"

        pmid = pmid_el.text if pmid_el is not None else "unknown"
        resultados.append({
            "pmid": pmid,
            "titulo": title_el.text if title_el is not None else "Sin título",
            "resumen": abstract or "Sin abstract disponible",
            "año": year_el.text if year_el is not None else None,
            "revista": journal_el.text if journal_el is not None else None,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        })

    return {
        "query": query,
        "total_found": total,
        "results": resultados,
        "source": "pubmed",
    }
