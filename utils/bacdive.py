"""
BacDive REST API — utilidad compartida CRIZA.

Base: https://api.bacdive.dsmz.de/ — la base de datos de fenotipos bacterianos más grande
(metabolismo, tolerancia a O2, rango de temperatura/pH, hábitat) del DSMZ.

Requiere cuenta gratuita (registro en https://api.bacdive.dsmz.de/) — HTTP Basic Auth con
email + password propios. Ver .env.example de cada agente que use este módulo:
BACDIVE_EMAIL / BACDIVE_PASSWORD. Sin credenciales, search_bacdive() devuelve un error claro
en vez de fallar silenciosamente.

Verificado en vivo (2026-08-16): /taxon/<nombre> (búsqueda) y /fetch/<id> (detalle) responden
200 con Basic Auth.
"""

import os
import requests
from typing import Optional

_BASE = "https://api.bacdive.dsmz.de"
_TIMEOUT = 20


def _credenciales() -> Optional[tuple[str, str]]:
    email = os.getenv("BACDIVE_EMAIL")
    password = os.getenv("BACDIVE_PASSWORD")
    if not email or not password:
        return None
    return (email, password)


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
    `max_results`.

    Returns:
        dict con 'resultados': [{bacdive_id, nombre_cientifico, descripcion, keywords, ...}]
        o {'error': ...} si faltan credenciales o falla la request.
    """
    auth = _credenciales()
    if not auth:
        return {
            "error": (
                "BACDIVE_EMAIL / BACDIVE_PASSWORD no configurados. Registrarse gratis en "
                "https://api.bacdive.dsmz.de/ y completar el .env del agente."
            )
        }

    try:
        resp = requests.get(f"{_BASE}/taxon/{organism}", auth=auth, timeout=_TIMEOUT,
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
            r = requests.get(f"{_BASE}/fetch/{strain_id}", auth=auth, timeout=_TIMEOUT,
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
