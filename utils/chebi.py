"""
ChEBI (via EBI Ontology Lookup Service) — utilidad compartida CRIZA.

Base: https://www.ebi.ac.uk/ols4/api (sin API key). ChEBI (Chemical Entities of Biological
Interest) clasifica compuestos por rol biológico/químico — útil para entender en qué categoría
cae un producto candidato (ej. "metabolito", "biofertilizante", "polímero biodegradable") y sus
sinónimos/definición curada.

Verificado en vivo (2026-08-17): el endpoint de búsqueda ols4 responde 200 sin auth. El
endpoint viejo (www.ebi.ac.uk/webservices/chebi/2.0) está deprecado — devuelve HTML, no XML/JSON
— confirmado al probarlo, no asumido.
"""

import requests

_BASE = "https://www.ebi.ac.uk/ols4/api/search"
_TIMEOUT = 15


def search_chebi(query: str, max_results: int = 5) -> dict:
    """
    Busca una entidad química en ChEBI por nombre (en inglés).

    Returns:
        dict con 'resultados': [{chebi_id, nombre, definicion, sinonimos}].
    """
    params = {"q": query, "ontology": "chebi", "rows": max_results}
    try:
        resp = requests.get(_BASE, params=params, timeout=_TIMEOUT)
        resp.raise_for_status()
    except Exception as exc:
        return {"error": f"ChEBI search falló: {exc}", "query": query}

    docs = ((resp.json().get("response") or {}).get("docs")) or []
    resultados = [
        {
            "chebi_id": d.get("obo_id"),
            "nombre": d.get("label"),
            "definicion": (d.get("description") or [None])[0],
            "sinonimos": (d.get("exact_synonyms") or [])[:5],
        }
        for d in docs
    ]

    return {
        "query": query,
        "total_encontrados": len(resultados),
        "resultados": resultados,
        "source": "chebi",
    }
