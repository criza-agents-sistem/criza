"""
COMTRADE API — importaciones reales de Argentina por código HS.

Fuente: UN Comtrade Database (comtradeplus.un.org)
API: https://comtradeplus.un.org/TradeFlow

Devuelve datos verificados de importaciones: cantidad, valor CIF, país de origen.
Requiere COMTRADE_API_KEY en .env (registro gratuito en comtrade.un.org).

Sin API key: retorna error claro con instrucciones de registro.
"""

import os
import requests
from typing import Optional

BASE_URL = "https://comtradeapi.un.org/data/v1/get/C/A/HS"

# Código ISO numérico de Argentina
ARGENTINA_ISO = "032"


def get_import_data(
    hs_code: str,
    year: Optional[int] = None,
    partner_country: Optional[str] = None,
    max_results: int = 20,
) -> dict:
    """
    Obtiene datos de importaciones de Argentina para un código HS dado.

    Args:
        hs_code: Código HS del producto (4 o 6 dígitos, ej: "1702" azúcar, "2922" aminoácidos)
        year: Año de consulta. None = último año disponible (hasta 2023)
        partner_country: ISO numérico del país exportador (ej: "076" Brasil). None = todos.
        max_results: Máximo de filas a retornar

    Returns:
        dict con:
          success: bool
          data: lista de registros [{year, reporter, partner, hs_code, trade_value_usd,
                                      net_weight_kg, quantity, unit}]
          summary: resumen agregado (total USD, total kg, top 5 países)
          source: "COMTRADE [VERIFICADO]"
          error: mensaje si falla
    """
    api_key = os.getenv("COMTRADE_API_KEY", "")

    if not api_key:
        return {
            "success": False,
            "error": (
                "COMTRADE_API_KEY no configurada. "
                "Registrarse gratis en comtrade.un.org → sección API → obtener key. "
                "Agregar COMTRADE_API_KEY=<tu_key> en market_agent/.env"
            ),
            "data": [],
            "summary": None,
            "source": "COMTRADE",
        }

    target_year = year or 2023

    params = {
        "reporterCode": ARGENTINA_ISO,
        "period": str(target_year),
        "flowCode": "M",          # M = imports
        "cmdCode": hs_code,
        "partnerCode": partner_country or "0",  # 0 = world
        "maxRecords": max_results,
        "includeDesc": "true",
        "subscription-key": api_key,
    }

    try:
        resp = requests.get(BASE_URL, params=params, timeout=20)
        resp.raise_for_status()
        raw = resp.json()
    except requests.RequestException as e:
        return {
            "success": False,
            "error": f"Error HTTP consultando COMTRADE: {e}",
            "data": [],
            "summary": None,
            "source": "COMTRADE",
        }

    records_raw = raw.get("data", [])
    if not records_raw:
        return {
            "success": True,
            "data": [],
            "summary": {
                "total_records": 0,
                "note": f"Sin datos de importación para HS {hs_code} en {target_year}. "
                        "Probar con código HS de 4 dígitos o año anterior.",
            },
            "source": "COMTRADE [VERIFICADO]",
        }

    records = []
    total_usd = 0.0
    total_kg = 0.0
    partner_totals: dict[str, float] = {}

    for r in records_raw:
        value_usd = r.get("primaryValue") or 0.0
        net_kg = r.get("netWgt") or 0.0
        partner = r.get("partnerDesc", "Unknown")

        records.append({
            "year": r.get("period"),
            "reporter": r.get("reporterDesc", "Argentina"),
            "partner": partner,
            "hs_code": r.get("cmdCode"),
            "hs_description": r.get("cmdDesc", ""),
            "trade_value_usd": value_usd,
            "net_weight_kg": net_kg,
            "quantity": r.get("qty"),
            "unit": r.get("qtyUnitAbbr", ""),
        })

        total_usd += value_usd
        total_kg += net_kg
        partner_totals[partner] = partner_totals.get(partner, 0.0) + value_usd

    top_partners = sorted(partner_totals.items(), key=lambda x: x[1], reverse=True)[:5]

    price_per_kg = (total_usd / total_kg) if total_kg > 0 else None

    return {
        "success": True,
        "data": records,
        "summary": {
            "hs_code": hs_code,
            "year": target_year,
            "total_records": len(records),
            "total_import_usd": round(total_usd, 2),
            "total_import_kg": round(total_kg, 2),
            "price_cif_usd_per_kg": round(price_per_kg, 4) if price_per_kg else None,
            "top_origin_countries": [
                {"country": c, "value_usd": round(v, 2)} for c, v in top_partners
            ],
        },
        "source": "COMTRADE [VERIFICADO]",
    }
