"""
Rhea REST API — utilidad compartida CRIZA.

Base: https://www.rhea-db.org/rhea (sin API key). Base de datos de reacciones bioquímicas
curada, cross-referenciada a EC number y ChEBI — útil para confirmar qué reacción/enzima
(EC) media una transformación química específica (ej. metano -> metanol).

Verificado en vivo (2026-08-16): el endpoint de búsqueda (?query=...&format=tsv) responde
200 sin auth. El endpoint de acceso directo por ID (/rhea/<id>) está detrás de Cloudflare y
bloquea requests sin navegador — por eso search_rhea() busca SIEMPRE vía ?query=, incluso
para un RHEA:ID puntual (funciona igual como término de búsqueda).
"""

import requests

_BASE = "https://www.rhea-db.org/rhea"
_TIMEOUT = 15
_COLUMNS = "rhea-id,equation,ec,chebi"


def search_rhea(query: str, max_results: int = 10) -> dict:
    """
    Busca reacciones en Rhea por texto libre (nombre de compuesto, EC number, o RHEA:ID).

    Returns:
        dict con 'resultados': [{rhea_id, ecuacion, ec_number, chebi}], sin auth requerida.
    """
    params = {
        "query": query,
        "columns": _COLUMNS,
        "format": "tsv",
        "limit": max_results,
    }
    try:
        resp = requests.get(_BASE, params=params, timeout=_TIMEOUT)
        resp.raise_for_status()
    except Exception as exc:
        return {"error": f"Rhea search falló: {exc}", "query": query}

    lineas = resp.text.strip().splitlines()
    if len(lineas) <= 1:
        return {"query": query, "total_encontrados": 0, "resultados": [], "source": "rhea"}

    resultados = []
    for linea in lineas[1:]:
        campos = linea.split("\t")
        if len(campos) < 4:
            continue
        resultados.append({
            "rhea_id": campos[0],
            "ecuacion": campos[1],
            "ec_number": campos[2] or None,
            "chebi": campos[3] or None,
        })

    return {
        "query": query,
        "total_encontrados": len(resultados),
        "resultados": resultados,
        "source": "rhea",
    }
