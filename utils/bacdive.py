"""
BacDive REST API — utilidad compartida CRIZA.

Base: https://api.bacdive.dsmz.de/v2 — la base de datos de fenotipos bacterianos más grande
(metabolismo, tolerancia a O2, rango de temperatura/pH, hábitat) del DSMZ.

**Sin auth ni cuenta** — desde febrero 2026 el DSMZ sacó el requisito de registro (verificado
en vivo 2026-08-16 releyendo la doc real en api.bacdive.dsmz.de: "No Registration Required...
Our API is now freely accessible — no sign-up, no account needed"). Antes de esa fecha requería
Basic Auth con cuenta gratuita — esta versión ya no la pide.

Se usa **v2** (`/v2/taxon/<nombre>`, `/v2/fetch/<id>`), no v1 — v1 quedó congelado en abril 2025
y no recibe datos nuevos (confirmado en vivo: mismo `doi` con timestamp de 2024 en v1 vs. 2026
en v2 para el mismo strain).
"""

import requests

_BASE = "https://api.bacdive.dsmz.de/v2"
_TIMEOUT = 20


def _resumir_strain(strain_id: str, detalle: dict) -> dict:
    general = detalle.get("General", {})
    taxonomia = detalle.get("Name and taxonomic classification", {})
    fisiologia = detalle.get("Physiology and metabolism", {})
    cultivo = detalle.get("Culture and growth conditions", {})

    nombre_cientifico = (taxonomia.get("LPSN") or {}).get("full scientific name")

    return {
        "bacdive_id": strain_id,
        "nombre_cientifico": nombre_cientifico,
        "descripcion": general.get("description"),
        "keywords": general.get("keywords"),
        "metabolismo": fisiologia.get("metabolite utilization") or fisiologia.get("oxygen tolerance"),
        "condiciones_cultivo": cultivo.get("culture temp"),
    }


def search_bacdive(organism: str, max_results: int = 5) -> dict:
    """
    Busca cepas bacterianas por taxón (género/especie) y trae detalle resumido de las primeras
    `max_results`. Sin auth — API pública desde febrero 2026.

    Returns:
        dict con 'resultados': [{bacdive_id, nombre_cientifico, descripcion, keywords, ...}]
        o {'error': ...} si falla la request.
    """
    try:
        resp = requests.get(f"{_BASE}/taxon/{organism}", timeout=_TIMEOUT,
                             headers={"Accept": "application/json"})
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        return {"error": f"BacDive taxon search falló: {exc}", "organism": organism}

    ids = (data.get("results") or [])[:max_results]
    if not ids:
        return {"organism": organism, "total_encontrados": 0, "resultados": [], "source": "bacdive"}

    resultados = []
    for strain_id in ids:
        try:
            r = requests.get(f"{_BASE}/fetch/{strain_id}", timeout=_TIMEOUT,
                              headers={"Accept": "application/json"})
            r.raise_for_status()
            detalle = (r.json().get("results") or {}).get(str(strain_id), {})
            resultados.append(_resumir_strain(str(strain_id), detalle))
        except Exception as exc:
            resultados.append({"bacdive_id": str(strain_id), "error": str(exc)})

    return {
        "organism": organism,
        "total_encontrados": data.get("count", len(ids)),
        "resultados": resultados,
        "source": "bacdive",
    }
