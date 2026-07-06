"""
datos.gob.ar API (CKAN) — estadísticas oficiales del gobierno argentino.

Fuente: https://datos.gob.ar
API: https://datos.gob.ar/api/3/action/

Permite buscar datasets sobre:
- Comercio exterior (INDEC)
- Producción agropecuaria (MAGyP)
- Precios (INDEC)
- Exportaciones (Aduana)

Sin API key — acceso público.
"""

import requests
from typing import Optional

BASE_URL = "https://datos.gob.ar/api/3/action"
SERIES_URL = "https://apis.datos.gob.ar/series/api"

# Traducción de nombres amistosos → slug REAL de organización en datos.gob.ar.
# Bug histórico: el agente pasaba "magyp"/"senasa"/"indec", que NO son slugs válidos → fq devolvía
# 0 datasets en silencio (parecía "no conecta"). Los datos de MAGyP Y SENASA viven bajo 'agroindustria';
# muchas series tipo INDEC bajo 'sspm'. (Verificado en vivo 2026-06-12.)
_ORG_SLUGS = {
    "magyp": "agroindustria", "agricultura": "agroindustria", "ganaderia": "agroindustria",
    "ganadería": "agroindustria", "senasa": "agroindustria", "pesca": "agroindustria",
    "agroindustria": "agroindustria",
    "indec": "sspm", "economia": "sspm", "economía": "sspm", "macro": "sspm", "sspm": "sspm",
}


def _resolve_org(name: str) -> str:
    """Traduce un nombre amistoso al slug real. Si no lo conoce, devuelve el valor literal
    (y la red de seguridad de search_official_stats reintenta sin filtro si da 0)."""
    return _ORG_SLUGS.get(name.strip().lower(), name.strip())


def search_official_stats(
    query: str,
    organization: Optional[str] = None,
    max_results: int = 10,
) -> dict:
    """
    Busca datasets en datos.gob.ar relacionados con el query.

    Args:
        query: Término de búsqueda (ej: "lactoferrina", "proteínas bovinas importación",
               "fitasa producción")
        organization: Filtrar por organismo (ej: "indec", "magyp", "senasa"). None = todos.
        max_results: Máximo de datasets a retornar

    Returns:
        dict con:
          success: bool
          datasets: lista de [{title, description, url, formats, organization, last_modified}]
          resources: lista plana de recursos descargables con URL directa
          source: "datos.gob.ar [VERIFICADO]"
          error: mensaje si falla
    """
    slug = _resolve_org(organization) if organization else None
    nota = None

    def _buscar(fq):
        p = {"q": query, "rows": max_results, "include_private": False}
        if fq:
            p["fq"] = f"organization:{fq}"
        r = requests.get(f"{BASE_URL}/package_search", params=p, timeout=15)
        r.raise_for_status()
        return r.json()

    try:
        data = _buscar(slug)
        # Red de seguridad: si el filtro de organización devolvió 0, reintentar SIN filtro.
        # Evita el "falso vacío" por slug inválido (la causa del histórico "no conecta").
        if slug and data.get("result", {}).get("count", 0) == 0:
            data = _buscar(None)
            nota = (f"El filtro organization='{organization}' (slug '{slug}') no devolvió datasets; "
                    f"se reintentó sin filtro. Revisá el organismo o filtrá por relevancia.")
    except requests.RequestException as e:
        return {
            "success": False,
            "error": f"Error consultando datos.gob.ar: {e}",
            "datasets": [],
            "resources": [],
            "source": "datos.gob.ar",
        }

    if not data.get("success"):
        return {
            "success": False,
            "error": "La API de datos.gob.ar retornó error",
            "datasets": [],
            "resources": [],
            "source": "datos.gob.ar",
        }

    results = data.get("result", {}).get("results", [])
    datasets = []
    resources = []

    for pkg in results:
        pkg_resources = pkg.get("resources", [])
        res_summary = [
            {
                "name": r.get("name", ""),
                "format": r.get("format", ""),
                "url": r.get("url", ""),
            }
            for r in pkg_resources
            if r.get("url")
        ]

        datasets.append({
            "title": pkg.get("title", ""),
            "description": (pkg.get("notes") or "")[:300],
            "url": f"https://datos.gob.ar/dataset/{pkg.get('name', '')}",
            "organization": pkg.get("organization", {}).get("title", ""),
            "formats": list({r["format"] for r in res_summary if r["format"]}),
            "last_modified": pkg.get("metadata_modified", ""),
            "resources_count": len(pkg_resources),
        })
        resources.extend(res_summary)

    return {
        "success": True,
        "query": query,
        "total_found": data.get("result", {}).get("count", 0),
        "datasets": datasets,
        "resources": resources[:30],
        "nota": nota,
        "source": "datos.gob.ar [VERIFICADO]",
    }


def search_series(query: str, max_results: int = 10) -> dict:
    """
    Busca SERIES DE TIEMPO (los números reales: faena, producción, precios, etc.) en la API de
    Series de datos.gob.ar — INDEC, MAGyP, Economía. A diferencia de search_official_stats (que
    busca METADATOS de datasets en el catálogo), esto encuentra series con valores consultables.

    Returns dict con: success, series [{id, descripcion, unidad, frecuencia, desde, hasta,
    dataset, publicador}], total_found, source. Usá get_series_values(id) para traer los valores.
    """
    try:
        resp = requests.get(f"{SERIES_URL}/search/", params={"q": query, "limit": max_results}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        return {"success": False, "error": f"Error consultando API de Series: {e}",
                "series": [], "source": "apis.datos.gob.ar/series"}

    series = []
    for item in data.get("data", []):
        f = item.get("field", {}) or {}
        ds = item.get("dataset", {}) or {}
        series.append({
            "id": f.get("id"),
            "descripcion": f.get("description") or f.get("title"),
            "unidad": f.get("units"),
            "frecuencia": f.get("frequency"),
            "desde": f.get("time_index_start"),
            "hasta": f.get("time_index_end"),
            "dataset": ds.get("title"),
            "publicador": (ds.get("publisher") or {}).get("name"),
        })
    return {"success": True, "query": query, "total_found": len(series),
            "series": series, "source": "apis.datos.gob.ar/series [VERIFICADO]"}


def get_series_values(series_id: str, last: int = 12) -> dict:
    """Trae los últimos `last` valores de una serie por su id (más recientes primero)."""
    try:
        resp = requests.get(f"{SERIES_URL}/series/",
                            params={"ids": series_id, "limit": last, "sort": "desc"}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        return {"success": False, "error": f"Error consultando serie: {e}",
                "valores": [], "source": "apis.datos.gob.ar/series"}
    valores = [{"fecha": row[0], "valor": row[1]} for row in data.get("data", []) if len(row) >= 2]
    return {"success": True, "series_id": series_id, "valores": valores,
            "source": "apis.datos.gob.ar/series [VERIFICADO]"}
