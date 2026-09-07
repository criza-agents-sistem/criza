"""
BCRA (Banco Central de la República Argentina) — API pública de estadísticas monetarias.

Fuente: https://api.bcra.gob.ar/estadisticas/v4.0/monetarias
Sin API key — acceso público. v3.0 está deprecada (410 Gone), usar siempre v4.0.

Verificado real 2026-09-07 (ver financiero_agent/docs/DESIGN_GATE.md): 1.610 variables
disponibles. Las relevantes para modelado financiero — tipo de cambio (id 4 minorista, id 5
mayorista), tasas de referencia (id 7 BADLAR, id 8 TM20, ambas bancos privados), inflación
(ids 27/28, mensual/interanual) — existen y devuelven series reales con `desde`/`hasta`/`limit`.

Este módulo es genérico (cualquier agente puede necesitar datos macro argentinos) — vive en
utils/ y no en financiero_agent/tools/ a propósito, mismo criterio que utils/corpus.py.
"""

import requests

BASE_URL = "https://api.bcra.gob.ar/estadisticas/v4.0/monetarias"

# IDs de referencia ya verificados reales (2026-09-07) — no exhaustivo, el catálogo completo
# tiene 1.610 variables. Se ofrecen como atajo documentado, no como límite: search_bcra_variables
# busca sobre el catálogo completo, no solo esta lista.
IDS_REFERENCIA = {
    "tipo_cambio_minorista": 4,
    "tipo_cambio_mayorista": 5,
    "badlar_bancos_privados": 7,
    "tm20_bancos_privados": 8,
    "inflacion_mensual": 27,
    "inflacion_interanual": 28,
    "tasa_politica_monetaria": 160,
}


def search_bcra_variables(query: str, max_results: int = 15) -> dict:
    """
    Busca variables monetarias del BCRA por coincidencia de texto en la descripción — el catálogo
    completo (1.610 variables) no tiene endpoint de búsqueda server-side, se trae entero (1 sola
    llamada, sin paginar — la API ya lo devuelve completo con limit=1000 default; acá se pide con
    un limit alto para no perder resultados) y se filtra localmente por substring, sin
    distinguir mayúsculas/acentos exactos (comparación simple, no normaliza tildes).

    Returns dict con: success, query, total_found, variables [{id_variable, descripcion,
    categoria, unidad, moneda, ultima_fecha, ultimo_valor}], source.
    """
    try:
        resp = requests.get(BASE_URL, params={"limit": 3000}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        return {"success": False, "error": f"Error consultando BCRA: {e}", "variables": [], "source": "api.bcra.gob.ar"}

    # Match por TODAS las palabras del query (AND), no substring literal del query completo —
    # bug real encontrado en la verificación viva del Agente Financiero (2026-09-07): un query
    # natural como "BADLAR bancos privados" no matcheaba la descripción real ("Tasa de interés
    # BADLAR DE bancos privados") por la palabra "de" de más, y el agente reportaba la tasa de
    # descuento como a-confirmar en vez de fundamentarla en datos reales — exactamente el
    # chequeo anti-sesgo central de este agente (ver financiero_agent/docs/DESIGN_GATE.md
    # decisión D). Con AND de palabras sueltas, cualquier orden/frase razonable matchea.
    palabras = [p for p in query.strip().lower().split() if p]
    resultados = [
        r for r in data.get("results", [])
        if palabras and all(p in (r.get("descripcion") or "").lower() for p in palabras)
    ]
    variables = [
        {
            "id_variable": r.get("idVariable"),
            "descripcion": r.get("descripcion"),
            "categoria": r.get("categoria"),
            "unidad": r.get("unidadExpresion"),
            "moneda": r.get("moneda"),
            "ultima_fecha": r.get("ultFechaInformada"),
            "ultimo_valor": r.get("ultValorInformado"),
        }
        for r in resultados[:max_results]
    ]
    return {
        "success": True, "query": query, "total_found": len(resultados),
        "variables": variables, "source": "api.bcra.gob.ar/estadisticas/v4.0 [VERIFICADO]",
    }


def get_bcra_values(id_variable: int, desde: str | None = None, hasta: str | None = None, limit: int = 30) -> dict:
    """
    Trae valores históricos de una variable monetaria del BCRA por su id_variable (de
    search_bcra_variables o de IDS_REFERENCIA). Más reciente primero.

    Args:
        id_variable: id numérico de la variable (ej. 4 = tipo de cambio minorista).
        desde/hasta: rango de fechas 'YYYY-MM-DD', opcional — sin rango, trae los últimos `limit`.
        limit: máximo de valores a traer (default 30).
    """
    params: dict = {"limit": limit}
    if desde:
        params["desde"] = desde
    if hasta:
        params["hasta"] = hasta
    try:
        resp = requests.get(f"{BASE_URL}/{id_variable}", params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        return {"success": False, "error": f"Error consultando serie BCRA {id_variable}: {e}", "valores": [], "source": "api.bcra.gob.ar"}

    resultados = data.get("results") or []
    if not resultados:
        return {"success": False, "error": f"id_variable {id_variable} no encontrado o sin datos en el rango pedido.", "valores": [], "source": "api.bcra.gob.ar"}

    detalle = resultados[0].get("detalle") or []
    valores = [{"fecha": d.get("fecha"), "valor": d.get("valor")} for d in detalle]
    return {
        "success": True, "id_variable": id_variable, "valores": valores,
        "source": "api.bcra.gob.ar/estadisticas/v4.0 [VERIFICADO]",
    }
