"""
OpenAlex search — utilidad compartida CRIZA.

Copia canónica: criza/utils/openalex.py
Los agentes que necesiten búsqueda de literatura importan desde acá.
Deuda técnica: divergent_agent/tools/openalex.py y scientific_agent/tools/openalex.py
son copias duplicadas — migrarlas a este módulo.

OpenAlex: 250M+ papers, sin API key, rate limit generoso (polite pool).
"""

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

    Args:
        query: Búsqueda en inglés, específica
        max_results: Cantidad de resultados (5-20 recomendado, max 200)

    Returns:
        dict con 'results' list y 'total_found' count.
        Cada result: title, abstract, year, journal, authors, url, doi,
                     pmid, pdf_url, citation_count, paper_id
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
        if resp.status_code in (429, 503):
            return _fallback_semantic_scholar(query, max_results, reason=str(e))
        return {
            "error": f"OpenAlex search failed ({resp.status_code}): {str(e)}",
            "results": [], "total_found": 0, "query": query, "source": "openalex",
        }
    except Exception as e:
        return _fallback_semantic_scholar(query, max_results, reason=str(e))

    meta = data.get("meta", {})
    total = meta.get("count", 0)
    works = data.get("results", [])

    results = [_procesar_work(w) for w in works]

    return {
        "query":       query,
        "total_found": total,
        "returned":    len(results),
        "results":     results,
        "source":      "openalex",
    }


def search_literature_exhaustivo(query: str, max_total: int = 40, abstract_max_chars: int = 250) -> dict:
    """
    Variante exhaustiva de search_literature — pagina de verdad en vez de devolver solo el
    top-N por relevancia. Etapa 22 (2026-09-14): Sebas, sobre el Biotecnólogo buscando productos
    de valorización raros/poco documentados: "estamos ante un problema que no sabemos si alguien
    encontró solución... si no somos exhaustivos el proyecto fracasa". Una búsqueda rankeada por
    relevancia puede dejar afuera justo el paper marginal/poco citado que describe el producto
    nicho que se busca — acá se trae todo lo que hay hasta max_total (techo de seguridad
    explícito, no infinito: OpenAlex tiene 250M+ papers, una query mal acotada podría intentar
    traer millones).

    No reemplaza search_literature (la deja intacta para los otros 3 especialistas que la usan
    hoy con el criterio de muestra dirigida, no exhaustiva) — es una función nueva, opt-in.

    Args:
        query: Búsqueda en inglés, específica.
        max_total: Techo de seguridad — no sigue paginando más allá de esto. 40 por defecto: no
            "poca cobertura" sino el punto donde más resultados dejan de agregar señal real y
            empiezan a costar contexto sin justificarlo (ver nota sobre abstract_max_chars).
        abstract_max_chars: Trunca el abstract de cada paper — con max_total alto y abstract
            completo, la conversación completa (se reenvía entera en cada turno del loop
            agéntico) revienta el límite de contexto del modelo en pocos turnos. Confirmado con
            una corrida real (2026-09-14): 4 consultas ya acumulaban 1.5M+ tokens sin truncar,
            muy por encima del límite real de Claude (1M).

    Returns:
        dict con 'results' (hasta max_total), 'total_found' (lo que reporta OpenAlex que existe
        en total), 'total_traido' (cuántos se trajeron realmente) y 'agotado' (bool — True si se
        trajeron todos los que había, False si se cortó por el techo de seguridad).
    """
    per_page = 200  # máximo que permite OpenAlex por página
    todos: list[dict] = []
    page = 1
    total_reportado = None

    while len(todos) < max_total:
        params = {
            "search": query,
            "per_page": per_page,
            "page": page,
            "select": FIELDS,
            "mailto": MAILTO,
            "sort": "relevance_score:desc",
        }
        try:
            resp = requests.get(BASE_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            return {
                "query": query, "results": todos, "total_found": total_reportado,
                "total_traido": len(todos), "agotado": False, "source": "openalex",
                "error_en_pagina": f"Falló en página {page}: {e}. Se devuelve lo traído hasta acá.",
            }

        meta = data.get("meta", {})
        if total_reportado is None:
            total_reportado = meta.get("count", 0)

        works = data.get("results", [])
        if not works:
            break  # se agotaron los resultados reales, no el techo

        for w in works:
            todos.append(_procesar_work(w))

        page += 1
        if page > 25:  # 25 páginas * 200 = 5000, muy por encima de max_total razonable — corte duro
            break

    # Encontrado real (2026-09-14): con max_total alto y abstract completo por paper, el
    # historial de la conversación explota el contexto del modelo en pocos turnos (1.5M+ tokens,
    # límite real de Claude es 1M) — confirmado con una corrida real, no una suposición. El
    # abstract se trunca acá (no en _procesar_work, que sigue devolviendo el completo para
    # search_literature normal, con max_results chico) — exhaustivo en CANTIDAD de papers
    # considerados, no en LARGO de cada uno.
    resultados_truncados = []
    for r in todos[:max_total]:
        r = dict(r)
        if r.get("abstract") and len(r["abstract"]) > abstract_max_chars:
            r["abstract"] = r["abstract"][:abstract_max_chars] + "…"
        resultados_truncados.append(r)

    agotado = len(todos) >= (total_reportado or 0) or len(todos) < per_page
    return {
        "query": query,
        "results": resultados_truncados,
        "total_found": total_reportado,
        "total_traido": min(len(todos), max_total),
        "agotado": agotado and len(todos) <= max_total,
        "source": "openalex",
    }


def _procesar_work(w: dict) -> dict:
    """Extraído de search_literature — mismo mapeo de campos, reusado por la variante exhaustiva."""
    doi_raw = w.get("doi") or ""
    doi = doi_raw.replace("https://doi.org/", "") if doi_raw else None

    ids = w.get("ids") or {}
    pmid_raw = ids.get("pmid") or ""
    pmid = pmid_raw.replace("https://pubmed.ncbi.nlm.nih.gov/", "").strip("/") if pmid_raw else None

    openalex_id = w.get("id", "")
    if doi:
        url = f"https://doi.org/{doi}"
    elif pmid:
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    else:
        url = openalex_id

    primary_loc = w.get("primary_location") or {}
    source = primary_loc.get("source") or {}
    journal = source.get("display_name") or "Unknown"

    authorships = w.get("authorships") or []
    author_names = [
        (a.get("author") or {}).get("display_name", "")
        for a in authorships[:3]
        if (a.get("author") or {}).get("display_name")
    ]
    authors = ", ".join(author_names)
    if len(authorships) > 3:
        authors += " et al."

    oa = w.get("open_access") or {}
    pdf_url = oa.get("oa_url")

    abstract = _reconstruct_abstract(w.get("abstract_inverted_index"))

    return {
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
    }


def _fallback_semantic_scholar(query: str, max_results: int, reason: str = "") -> dict:
    try:
        from semantic_scholar import search_literature as ss_search
        result = ss_search(query, max_results)
        result["source"] = "semantic_scholar_fallback"
        result["fallback_reason"] = reason
        return result
    except Exception as e:
        return {
            "error": f"OpenAlex falló ({reason}) y Semantic Scholar también falló: {str(e)}",
            "results": [], "total_found": 0, "query": query, "source": "none",
        }
