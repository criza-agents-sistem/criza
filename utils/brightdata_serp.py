"""
Bright Data SERP API — utilidad compartida CRIZA.

Etapa 22 (cont., 2026-09-14): Sebas ve en redes/revistas especializadas productos de
biorefinería/valorización que no están en OpenAlex/CONICET/INTA por ser internacionales o
comerciales, no académicos. Búsqueda técnica multilenguaje contra buscadores reales (Google) —
no un buscador de Instagram (no existe, verificado antes de construir esto), pero sí encuentra
prensa especializada, sitios de empresas y notas técnicas en varios idiomas.

Requiere BRIGHTDATA_API_KEY en .env (cuenta paga, brightdata.com) y una zona SERP API ya creada
(zone="serp_api1" hoy — ver Web Access > SERP API en el panel de Bright Data).

Sin API key: retorna error claro con instrucciones, mismo criterio que utils/bcra.py y
market_agent/tools/comtrade.py.
"""

import os
from urllib.parse import quote

import requests

_ENDPOINT = "https://api.brightdata.com/request"
_ZONE = "serp_api1"
_TIMEOUT = 30


def buscar_web_tecnico(
    query: str,
    idioma: str = "en",
    pais: str | None = None,
    max_total: int = 30,
    descripcion_max_chars: int = 300,
) -> dict:
    """
    Busca en Google (vía Bright Data SERP API) — pagina hasta agotar resultados reales o
    max_total, mismo criterio que search_literature_exhaustivo (utils/openalex.py): no trae
    solo el top-10, pero trunca cada resultado para no reventar el contexto del modelo.

    Args:
        query: Búsqueda técnica y específica — mismo criterio que search_literature (una
            consulta por ángulo/sinónimo/idioma, no un término genérico).
        idioma: Código de idioma de los resultados (ej. "en", "es", "pt", "de").
        pais: Código de país opcional para geo-targeting (ej. "us", "ar", "de").
        max_total: Techo de seguridad de resultados a traer.
        descripcion_max_chars: Trunca la descripción de cada resultado.

    Returns:
        dict con 'results' [{titulo, url, descripcion}], 'total_traido', 'agotado', 'source'.
        {"error": ...} si falta la API key o falla el pedido.
    """
    api_key = os.getenv("BRIGHTDATA_API_KEY", "")
    if not api_key:
        return {
            "error": (
                "BRIGHTDATA_API_KEY no configurada. Crear cuenta en brightdata.com, agregar "
                "una zona SERP API (Web Access > SERP API), y agregar BRIGHTDATA_API_KEY=<key> "
                "en api/.env."
            ),
        }

    resultados: list[dict] = []
    start = 0
    total_reportado = None

    while len(resultados) < max_total:
        google_url = f"https://www.google.com/search?q={quote(query)}&hl={idioma}&brd_json=1"
        if pais:
            google_url += f"&gl={pais}"
        if start:
            google_url += f"&start={start}"

        try:
            resp = requests.post(
                _ENDPOINT,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"zone": _ZONE, "url": google_url, "format": "raw"},
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            return {
                "query": query, "results": resultados, "total_traido": len(resultados),
                "agotado": False, "source": "brightdata_serp",
                "error_en_pagina": f"Falló en start={start}: {e}. Se devuelve lo traído hasta acá.",
            }

        if total_reportado is None:
            total_reportado = (data.get("general") or {}).get("results_cnt")

        organic = data.get("organic") or []
        if not organic:
            break  # se agotaron los resultados reales, no el techo

        for r in organic:
            descripcion = r.get("description") or ""
            if len(descripcion) > descripcion_max_chars:
                descripcion = descripcion[:descripcion_max_chars] + "…"
            resultados.append({
                "titulo": r.get("title"),
                "url": r.get("link"),
                "descripcion": descripcion,
            })

        start += 10
        if start > 90:  # 100 resultados de Google es el límite práctico habitual — corte duro
            break

    agotado = start <= 90 and len(resultados) <= max_total
    return {
        "query": query,
        "results": resultados[:max_total],
        "total_found": total_reportado,
        "total_traido": min(len(resultados), max_total),
        "agotado": agotado,
        "source": "brightdata_serp",
    }
