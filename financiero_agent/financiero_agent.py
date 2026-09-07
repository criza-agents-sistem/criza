"""
Agente Financiero — CRIZA (Etapa 21, 2026-09-07)

Sexto especialista de la biblioteca, y el modelo económico-financiero que el propio Conductor
identificó como gap sin cubrir (docs/progress/2026-08-24.md). Sebas: "vamos con el modelo
económico-financiero, este tiene que ser muy profesional." Responde una pregunta que ningún otro
especialista cubre: dado un producto/proceso candidato ya identificado por otro especialista (y
su mercado, si el Agente de Mercado ya corrió), ¿es financieramente viable, con qué inversión, en
qué plazo, y con qué sensibilidad a los supuestos?

Construido de cero (no adaptado, a diferencia de Mercado en la Etapa 20) — mismo patrón general
que los otros 5 especialistas (contrato SEB-115, chat conversacional, ver_informe_especialista),
pero con cliente nativo Anthropic (como Mercado, por la excepción permanente de `web_search` —
ver docs/DESIGN_GATE.md decisión C) y dos capacidades nuevas: `search_bcra` (tasas/inflación/tipo
de cambio reales del BCRA) y `pedir_informacion_faltante` (crea un `pendiente` real en el caso en
vez de asumir un dato que falta — Sebas: "el agente podría pedir qué información necesita").

CHEQUEO ANTI-SESGO (pedido explícito de Sebas, "sólo te pido último chequeo de que no tenga
sesgos" — ver docs/DESIGN_GATE.md decisión D, tabla completa de riesgos + mitigación):
- Tasa de descuento: NUNCA un default de manual de finanzas — se deriva de search_bcra + una
  prima de riesgo justificada, siempre con fuente citada.
- Costos/precios: NUNCA "recordados" del entrenamiento — solo de una búsqueda real (web_search/
  fetch_page_text/search_series) o declarados a-confirmar/pedidos vía pedir_informacion_faltante.
- Proyecciones: el escenario pesimista de analisis_sensibilidad es obligatorio y tiene que ser
  genuinamente adverso (costos más altos y/o ingresos más bajos que el caso base), no "base menos
  un poco".
- Riesgo cambiario: campo obligatorio (aunque la respuesta sea "no aplica") — lee el alcance
  geográfico que recomendó el Agente de Mercado antes de fijar monedas de ingresos vs. costos.
- El agente ARMA el modelo con sus números y gaps — nunca concluye "conviene"/"no conviene"
  (mismo límite que rige a los otros 5, CLAUDE.md: "el sistema ARMA, el humano ELIGE").
- SYSTEM_PROMPT sin ningún caso concreto mencionado (mismo checklist anti-sesgo de siempre).

Tools: ver_informe_especialista, search_bcra, search_series, get_series_values,
       search_official_stats, buscar_corpus_cientifico, web_search (nativo Anthropic),
       fetch_page_text, pedir_informacion_faltante, submit_modelo_financiero.
"""

import json
import logging
import os
import sys
import time
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

import anthropic

_AGENT_DIR = Path(__file__).parent
_CRIZA_DIR = _AGENT_DIR.parent
sys.path.insert(0, str(_CRIZA_DIR))

# Reuso directo de market_agent/tools — mismos datos oficiales que ya necesita Mercado (series
# INDEC/MAGyP, corpus científico, fetch de páginas públicas). No se duplica el código.
from market_agent.tools import (
    search_official_stats,
    search_series,
    get_series_values,
    fetch_page_text,
    buscar_corpus_cientifico,
)
from utils.bcra import search_bcra_variables, get_bcra_values
from utils.casos import (
    obtener_frente_con_caso, obtener_pendientes_de_caso, obtener_documentos_aportados_de_frente,
    obtener_documentos_de_frente, obtener_documento_por_id, crear_pendiente,
)
from knowledge_module.motor import api as motor_api
import knowledge_module.aprendizaje as aprendizaje
from utils.token_tracker import TokenTracker
from knowledge_module.preflight import FuenteCheck, FuenteCheckResult, run_preflight
from knowledge_module.db import get_session_factory
from sqlalchemy import text as _sql_text

# Financiero es Anthropic-only, mismo motivo y misma excepción permanente que market_agent.py
# (ver ese docstring y decisiones_sistema, componente=ai_client, 2026-08-15): necesita la tool
# nativa `web_search_20250305` para comparables de costo/inversión/precio vigentes, sin
# equivalente en utils/ai_client.py.
client = anthropic.Anthropic()
DEFAULT_MODEL = os.getenv("FINANCIERO_MODEL", "claude-sonnet-4-6")
_AGENTE = "financiero"
_TENANT = "criza"
_WEB_SEARCH_MAX_USES = 5


# ── Pre-flight check ──────────────────────────────────────────────────────────

async def _check_corpus_cientifico() -> FuenteCheckResult:
    async with get_session_factory()() as s:
        r = await s.execute(_sql_text(
            "SELECT COUNT(*) FROM ficha f "
            "JOIN tipo_ficha tf ON tf.id = f.tipo_ficha_id "
            "JOIN area a ON a.id = tf.area_id "
            "WHERE a.nombre = 'corpus_cientifico' AND a.tenant_id = :t"
        ), {"t": _TENANT})
        total = r.scalar() or 0
    return FuenteCheckResult(ok=total > 0, detalle=f"{total} fichas", conteo=total)


async def _check_bcra() -> FuenteCheckResult:
    """BCRA — bloqueante: sin esto, no hay forma de fundamentar la tasa de descuento con datos
    reales (ver decisión D del Design Gate, el chequeo anti-sesgo central de este agente)."""
    result = search_bcra_variables(query="tipo de cambio minorista", max_results=1)
    if result.get("success") and result.get("variables"):
        return FuenteCheckResult(ok=True, detalle="reachable")
    return FuenteCheckResult(ok=False, detalle=result.get("error") or "sin resultados")


async def _check_web_search() -> FuenteCheckResult:
    if os.getenv("ANTHROPIC_API_KEY"):
        return FuenteCheckResult(ok=True, detalle="ANTHROPIC_API_KEY configurada")
    return FuenteCheckResult(ok=False, detalle="ANTHROPIC_API_KEY no configurada")


def _merge_web_search_coverage(fuentes_y_cobertura: dict, calls: int, results_total: int) -> None:
    """Mismo patrón que market_agent._merge_web_search_coverage — no confiamos en el
    autoreporte del modelo, pisamos con el conteo objetivo de la tool server-side."""
    entradas = fuentes_y_cobertura.setdefault("fuentes_consultadas", [])
    entrada = next((e for e in entradas if e.get("nombre") == "web_search"), None)
    if entrada is None:
        entrada = {"nombre": "web_search"}
        entradas.append(entrada)
    entrada["disponible"] = calls > 0
    entrada["unidades_procesadas"] = results_total
    entrada["de_un_total"] = None
    entrada["motivo_si_no_disponible"] = None if calls > 0 else "no se realizaron búsquedas web en esta corrida"


# ── Tool definitions ──────────────────────────────────────────────────────────

TOOLS = [
    {
        "type": "web_search_20250305",
        "name": "web_search",
        "max_uses": _WEB_SEARCH_MAX_USES,
    },
    {
        "name": "ver_informe_especialista",
        "description": (
            "Trae el contenido completo de un informe que otro especialista (Biotecnólogo, "
            "Microbiólogo, Ingeniero Ambiental, Agrónomo, Mercado) ya produjo sobre este mismo "
            "frente — ver la lista 'Informes ya producidos en este frente' en tu input. USALA "
            "SIEMPRE antes de modelar: necesitás saber qué producto/proceso estás costeando "
            "(normalmente del Biotecnólogo) y, si existe, qué alcance geográfico de mercado "
            "recomendó el Agente de Mercado (define en qué moneda entran los ingresos vs. los "
            "costos — ver riesgo_cambiario). Nunca inventes el producto ni el mercado. No leas "
            "todos los informes, solo los relevantes. Nunca inventes un id, usá el que aparece "
            "en la lista tal cual."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"documento_id": {"type": "string"}},
            "required": ["documento_id"],
        },
    },
    {
        "name": "search_bcra",
        "description": (
            "Busca variables monetarias del BCRA (Banco Central) por texto — tipo de cambio, "
            "tasas de interés de referencia (BADLAR, TM20, política monetaria), inflación. "
            "Retorna id_variable + último valor. Usar SIEMPRE antes de fijar tasa_descuento: la "
            "tasa nunca sale de un default de manual de finanzas, sale de una tasa de referencia "
            "real más una prima de riesgo justificada. Ejemplos de query: 'tipo de cambio "
            "minorista', 'BADLAR', 'inflación mensual', 'tasa de política monetaria'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Término a buscar en la descripción de la variable."},
                "max_results": {"type": "integer", "description": "Máximo de variables (default 15).", "default": 15},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_bcra_values",
        "description": (
            "Trae los valores históricos de una variable del BCRA por su id_variable (de "
            "search_bcra). Más reciente primero. Usar para ver la tendencia reciente (ej. últimos "
            "3-6 meses) antes de fijar un supuesto, no solo el último valor puntual."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "id_variable": {"type": "integer", "description": "id_variable de search_bcra."},
                "desde": {"type": "string", "description": "Fecha 'YYYY-MM-DD', opcional."},
                "hasta": {"type": "string", "description": "Fecha 'YYYY-MM-DD', opcional."},
                "limit": {"type": "integer", "description": "Máximo de valores (default 30).", "default": 30},
            },
            "required": ["id_variable"],
        },
    },
    {
        "name": "search_series",
        "description": (
            "Busca series de tiempo oficiales (datos.gob.ar: INDEC/MAGyP) — producción, precios, "
            "volúmenes del sector relevante. Usá get_series_values(series_id) para los valores.\n"
            "Cuándo usar: para fundamentar supuestos de volumen/precio de ingresos_proyectados o "
            "de un insumo de costo, con datos oficiales en vez de estimación libre."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Término de búsqueda"},
                "max_results": {"type": "integer", "description": "Máximo de series (default 10)", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_series_values",
        "description": "Trae los últimos N valores de una serie por su id (datos.gob.ar) — más reciente primero.",
        "input_schema": {
            "type": "object",
            "properties": {
                "series_id": {"type": "string", "description": "ID de la serie (de search_series)"},
                "last": {"type": "integer", "description": "Últimos N valores (default 12)", "default": 12},
            },
            "required": ["series_id"],
        },
    },
    {
        "name": "search_official_stats",
        "description": (
            "Busca datasets en datos.gob.ar (INDEC/MAGyP/SENASA) — complementa search_series con "
            "datasets descargables cuando no hay una serie puntual."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Término de búsqueda en español"},
                "organization": {"type": "string", "description": "'indec', 'magyp', 'senasa'. Omitir = todos."},
                "max_results": {"type": "integer", "description": "Máximo de datasets (default 10)", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "buscar_corpus_cientifico",
        "description": (
            "Busca en el corpus científico local (CONICET+INTA) — literatura sobre costos/escala "
            "de proceso, rendimiento, comparables técnicos que sustenten CAPEX/OPEX."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "consulta": {"type": "string", "description": "Términos a buscar. ES o EN."},
                "limit": {"type": "integer", "description": "Máximo de papers (default 100).", "default": 100},
            },
            "required": ["consulta"],
        },
    },
    {
        "name": "fetch_page_text",
        "description": (
            "Descarga y extrae el texto de una URL pública — usar sobre los resultados de "
            "web_search para leer el detalle de un comparable de costo/inversión/precio. "
            "MÁXIMO 3 fetches por corrida. Solo URLs públicas, sin login."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL completa de la página"},
                "max_chars": {"type": "integer", "description": "Máximo de caracteres (default 8000)", "default": 8000},
            },
            "required": ["url"],
        },
    },
    {
        "name": "pedir_informacion_faltante",
        "description": (
            "Crea un pendiente real en el caso — usar cuando un dato es indispensable para el "
            "modelo (ej. costo real de un equipo específico, escala de planta prevista) y ninguna "
            "búsqueda lo trae con confianza razonable. Preferible a asumir un número inventado o a "
            "bloquear el análisis completo — el modelo sigue con ese ítem declarado a-confirmar y "
            "el pendiente queda registrado para que Sebas lo resuelva. No abusar: solo para gaps "
            "genuinamente críticos, no para cualquier duda menor (esas van como a-confirmar en el "
            "campo correspondiente, sin crear un pendiente)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "descripcion": {"type": "string", "description": "Qué información falta y por qué es necesaria para el modelo."},
            },
            "required": ["descripcion"],
        },
    },
    {
        "name": "submit_modelo_financiero",
        "description": (
            "ÚNICO output del agente. Llamar cuando el modelo esté completo — con gaps declarados "
            "donde haga falta, no con certeza total. Un modelo con supuestos a-confirmar "
            "explícitos es mejor que uno con números inventados sin fuente."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "supuestos": {
                    "type": "array",
                    "description": "Cada supuesto numérico o cualitativo relevante del modelo, con su estado.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "variable": {"type": "string"},
                            "valor": {"type": "string"},
                            "estado": {"type": "string", "enum": ["establecido", "asumido", "a-confirmar"]},
                            "fuente": {"type": "string"},
                        },
                        "required": ["variable", "valor", "estado"],
                    },
                },
                "capex": {
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "concepto": {"type": "string"},
                                    "monto": {"type": "number"},
                                    "moneda": {"type": "string"},
                                    "estado": {"type": "string", "enum": ["establecido", "asumido", "a-confirmar"]},
                                    "fuente": {"type": "string"},
                                },
                                "required": ["concepto", "monto", "moneda", "estado"],
                            },
                        },
                        "total": {"type": "number"},
                        "estado": {"type": "string", "enum": ["establecido", "asumido", "a-confirmar"]},
                    },
                    "required": ["items", "total", "estado"],
                },
                "opex": {
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "concepto": {"type": "string"},
                                    "monto_mensual": {"type": "number"},
                                    "moneda": {"type": "string"},
                                    "estado": {"type": "string", "enum": ["establecido", "asumido", "a-confirmar"]},
                                    "fuente": {"type": "string"},
                                },
                                "required": ["concepto", "monto_mensual", "moneda", "estado"],
                            },
                        },
                        "total_mensual": {"type": "number"},
                        "estado": {"type": "string", "enum": ["establecido", "asumido", "a-confirmar"]},
                    },
                    "required": ["items", "total_mensual", "estado"],
                },
                "ingresos_proyectados": {
                    "type": "object",
                    "properties": {
                        "supuesto_precio": {"type": "string"},
                        "supuesto_volumen": {"type": "string"},
                        "proyeccion_anual": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "año": {"type": "integer"},
                                    "monto": {"type": "number"},
                                    "moneda": {"type": "string"},
                                },
                                "required": ["año", "monto", "moneda"],
                            },
                        },
                        "estado": {"type": "string", "enum": ["establecido", "asumido", "a-confirmar"]},
                    },
                    "required": ["supuesto_precio", "supuesto_volumen", "proyeccion_anual", "estado"],
                },
                "pyl_multianual": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "año": {"type": "integer"},
                            "ingresos": {"type": "number"},
                            "costos": {"type": "number"},
                            "resultado": {"type": "number"},
                        },
                        "required": ["año", "ingresos", "costos", "resultado"],
                    },
                },
                "flujo_de_caja": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "año": {"type": "integer"},
                            "flujo_neto": {"type": "number"},
                        },
                        "required": ["año", "flujo_neto"],
                    },
                },
                "tasa_descuento": {
                    "type": "object",
                    "description": (
                        "OBLIGATORIO citar fuente_bcra — nunca un % de manual de finanzas sin "
                        "fundamento en una tasa de referencia real (ver search_bcra)."
                    ),
                    "properties": {
                        "valor_pct": {"type": "number"},
                        "justificacion": {"type": "string"},
                        "fuente_bcra": {"type": "string", "description": "Qué variable BCRA y qué valor la fundamentan."},
                        "estado": {"type": "string", "enum": ["establecido", "asumido", "a-confirmar"]},
                    },
                    "required": ["valor_pct", "justificacion", "fuente_bcra", "estado"],
                },
                "van": {
                    "type": "object",
                    "properties": {
                        "valor": {"type": "number"},
                        "moneda": {"type": "string"},
                        "estado": {"type": "string", "enum": ["establecido", "asumido", "a-confirmar"]},
                    },
                    "required": ["valor", "moneda", "estado"],
                },
                "tir": {
                    "type": "object",
                    "properties": {
                        "valor_pct": {"type": "number"},
                        "estado": {"type": "string", "enum": ["establecido", "asumido", "a-confirmar"]},
                    },
                    "required": ["valor_pct", "estado"],
                },
                "payback": {
                    "type": "object",
                    "properties": {
                        "años": {"type": "number"},
                        "estado": {"type": "string", "enum": ["establecido", "asumido", "a-confirmar"]},
                    },
                    "required": ["años", "estado"],
                },
                "riesgo_cambiario": {
                    "type": "object",
                    "description": (
                        "OBLIGATORIO declararlo aunque la respuesta sea 'no aplica' — leer el "
                        "alcance geográfico que recomendó Mercado (ver_informe_especialista) antes "
                        "de decidir si ingresos y costos están en la misma moneda."
                    ),
                    "properties": {
                        "aplica": {"type": "boolean"},
                        "descripcion": {"type": "string"},
                    },
                    "required": ["aplica", "descripcion"],
                },
                "analisis_sensibilidad": {
                    "type": "object",
                    "description": (
                        "OBLIGATORIO un escenario pesimista genuinamente adverso (costos más "
                        "altos y/o ingresos más bajos que el caso base, con su propia "
                        "justificación) — no 'base menos un poco'."
                    ),
                    "properties": {
                        "optimista": {"type": "object", "properties": {"van": {"type": "number"}, "tir_pct": {"type": "number"}, "supuestos_clave": {"type": "string"}}},
                        "base": {"type": "object", "properties": {"van": {"type": "number"}, "tir_pct": {"type": "number"}, "supuestos_clave": {"type": "string"}}},
                        "pesimista": {"type": "object", "properties": {"van": {"type": "number"}, "tir_pct": {"type": "number"}, "supuestos_clave": {"type": "string"}}},
                    },
                    "required": ["optimista", "base", "pesimista"],
                },
                "informacion_faltante_pedida": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"descripcion": {"type": "string"}, "pendiente_id": {"type": "string"}},
                        "required": ["descripcion", "pendiente_id"],
                    },
                    "description": "Ítems para los que se llamó pedir_informacion_faltante en esta corrida.",
                },
                "fuentes_y_cobertura": {
                    "type": "object",
                    "description": "Qué fuentes se consultaron y con qué cobertura (orchestration-layer.md Decisión 6).",
                    "properties": {
                        "fuentes_consultadas": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "nombre": {"type": "string"},
                                    "disponible": {"type": "boolean"},
                                    "unidades_procesadas": {"type": "integer"},
                                    "de_un_total": {"type": ["integer", "null"]},
                                    "motivo_si_no_disponible": {"type": ["string", "null"]},
                                },
                                "required": ["nombre", "disponible", "unidades_procesadas"],
                            },
                        },
                        "cobertura_declarada": {
                            "type": "string",
                            "enum": ["exhaustiva", "muestreada", "parcial-por-falla-de-fuente"],
                        },
                    },
                    "required": ["fuentes_consultadas", "cobertura_declarada"],
                },
                "informe_completo": {
                    "type": "string",
                    "description": (
                        "Narrativa completa en markdown: producto/proceso evaluado, supuestos "
                        "clave con su fuente, el modelo (CAPEX/OPEX/P&L/cash flow), VAN/TIR/"
                        "payback con su tasa de descuento justificada, sensibilidad, gaps. Sección "
                        "'Búsquedas realizadas' obligatoria (mismo hallazgo real de otros "
                        "especialistas, 2026-08-19: sin esa sección en prosa, el trabajo real "
                        "queda invisible para quien lee el informe)."
                    ),
                },
                "lecciones_caso": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lecciones para el loop de aprendizaje.",
                },
            },
            "required": [
                "supuestos", "capex", "opex", "ingresos_proyectados", "tasa_descuento", "van",
                "tir", "payback", "riesgo_cambiario", "analisis_sensibilidad",
                "fuentes_y_cobertura", "informe_completo",
            ],
        },
    },
]


# ── System prompt ──────────────────────────────────────────────────────────────
# Deliberadamente sin ningún caso concreto mencionado (mismo checklist anti-sesgo de siempre) —
# el rol y el método son genéricos, el caso entra solo por build_input_desde_frente.

SYSTEM_PROMPT = """Sos el Agente Financiero de CRIZA. Tu misión: construir un modelo económico-
financiero PROFESIONAL para el producto/proceso candidato de un frente, con inversión, costos,
ingresos proyectados, rentabilidad (VAN/TIR/payback) y sensibilidad a los supuestos.

TU OBJETIVO: dado el producto/proceso que otro especialista (normalmente el Biotecnólogo) ya
identificó, y el mercado que el Agente de Mercado ya evaluó (si corrió sobre este frente), armar
el modelo financiero completo: CAPEX, OPEX, P&L multianual, flujo de caja, VAN, TIR, payback, y un
análisis de sensibilidad con al menos tres escenarios. No proponés qué producto fabricar (eso es
de otro especialista) ni evaluás mercado (eso es de Mercado) — vos evaluás si, dado lo que los
otros ya identificaron, el proyecto es financieramente viable y con qué números concretos.

DECISIÓN FINAL SIEMPRE HUMANA: armás el modelo con sus números y sus gaps. Nunca concluís
"conviene" o "no conviene" — esa decisión es de Sebas, no tuya. Un modelo con supuestos
a-confirmar explícitos es un resultado válido y útil, no un fracaso del análisis.

QUÉ RECIBÍS: el caso/frente completo y, si hay, la lista de informes que otros especialistas ya
produjeron sobre este frente. Nunca asumas un caso específico si no te lo dan en el input de esta
corrida.

PASO 0 — OBLIGATORIO ANTES DE MODELAR: leé (ver_informe_especialista) el informe que identifica
el producto/proceso candidato (normalmente del Biotecnólogo) y, si existe, el del Agente de
Mercado (define el alcance geográfico — local/nacional/exportación — que determina en qué moneda
entran los ingresos). No inventes ninguno de los dos.

FUENTES DISPONIBLES:
- search_bcra / get_bcra_values: tasas de referencia (BADLAR, TM20, política monetaria),
  inflación, tipo de cambio — la ÚNICA fuente válida para fundamentar tasa_descuento. Nunca uses
  un porcentaje "típico" de manual de finanzas de mercados desarrollados como default — eso
  ignora el contexto real de tasas argentinas y distorsiona el VAN/TIR de cualquier proyecto
  evaluado acá.
- search_series / get_series_values / search_official_stats: series y datasets oficiales
  (INDEC/MAGyP) — volumen/precio del sector, útiles para fundamentar ingresos_proyectados o un
  insumo de costo con datos reales en vez de estimación libre.
- buscar_corpus_cientifico: literatura CONICET+INTA sobre costos/escala/rendimiento de proceso.
- web_search + fetch_page_text: comparables de CAPEX/OPEX/precio vigentes que ningún corpus local
  tiene. NUNCA un costo/precio "recordado" de tu entrenamiento sin una búsqueda real — un número
  plausible pero fabricado es exactamente el sesgo de anclaje que hay que evitar acá; si no lo
  podés verificar, va como a-confirmar (o pedís la información con pedir_informacion_faltante).
- pedir_informacion_faltante: si un dato es indispensable y ninguna búsqueda lo trae con
  confianza razonable, creá un pendiente real en vez de inventar el número — no abuses de esto
  para dudas menores, esas van como a-confirmar directamente en el campo correspondiente.
- ver_informe_especialista: contenido completo de informes de otros especialistas (ver PASO 0).

TASA DE DESCUENTO — chequeo anti-sesgo central de este agente: siempre derivada de una tasa de
referencia BCRA real (search_bcra) más una prima de riesgo justificada en el informe, nunca un
número "estándar" recordado. Citá en tasa_descuento.fuente_bcra exactamente qué variable y qué
valor usaste.

RIESGO CAMBIARIO — campo obligatorio, aunque la respuesta sea "no aplica". Si Mercado recomendó
alcance de exportación, los ingresos probablemente entran en una moneda distinta a los costos
locales — declaralo y explicá el tratamiento, no lo ignores.

ANÁLISIS DE SENSIBILIDAD — el escenario pesimista tiene que ser genuinamente adverso (costos
reales más altos y/o ingresos reales más bajos que el caso base, con su propia justificación), no
un ajuste cosmético del caso base. Un modelo que solo muestra un escenario favorable esconde el
riesgo real de la decisión.

TU PROCESO:
1. ver_informe_especialista — identificá producto/proceso (y mercado, si existe) — PASO 0
2. search_bcra + get_bcra_values — tasa de descuento fundamentada en datos reales
3. web_search + fetch_page_text (hasta 3) + search_series/search_official_stats — comparables
   reales de CAPEX/OPEX/precio; buscar_corpus_cientifico para literatura de costo/escala
4. Si algo indispensable no aparece con confianza razonable → pedir_informacion_faltante
   (declarar igual el ítem como a-confirmar en el campo correspondiente)
5. Armar CAPEX, OPEX, ingresos_proyectados, P&L multianual, flujo de caja
6. Calcular VAN/TIR/payback con la tasa de descuento fundamentada
7. Análisis de sensibilidad: optimista/base/pesimista, con supuestos_clave de cada uno
8. Declarar riesgo_cambiario explícitamente
9. submit_modelo_financiero — siempre el último paso, aunque falten datos

CUÁNDO CERRAR: cuando el modelo esté completo con sus gaps declarados. No acumulés búsquedas si
ya podés armar el modelo con lo que tenés.

VERACIDAD POR DATO:
- establecido: lo dice la fuente, citás referencia
- asumido: inferencia razonable, aclarás el peso
- a-confirmar: gap real, aclarás dónde verificar (o lo pediste con pedir_informacion_faltante)

Al llamar submit_modelo_financiero, declará siempre fuentes_y_cobertura: qué fuentes consultaste,
cuántos resultados procesaste de cada una, y si alguna no estuvo disponible. Ese campo NO alcanza
solo: informe_completo (la narrativa que se lee, no el JSON) tiene que incluir una sección visible
"Búsquedas realizadas" que resuma lo mismo en prosa — qué buscaste, en qué fuente, cuántos
resultados, y qué encontraste de relevante en cada una. Sin esa sección en el texto, el trabajo
real que hiciste queda invisible para quien lee el informe (encontrado real, 2026-08-19, en otro
especialista).

REGLAS:
- Máximo 3 fetch_page_text por corrida — elegí bien las URLs (las que devolvió web_search).
- ver_informe_especialista: leé solo los relevantes, no todos los que aparezcan en la lista.
- pedir_informacion_faltante: solo para gaps genuinamente críticos e indispensables.
- submit_modelo_financiero es el último paso — siempre llamarlo. Un modelo con gaps declarados es
  mejor que uno que no cierra.
"""


# ── Contrato estándar (SEB-115) ───────────────────────────────────────────────

INPUT_CONTRACT = {
    "agent": "financiero",
    "version": "1.0",
    "fields": {
        "caso": "Recorte/foco de esta invocación (opcional) — no reemplaza al frente/caso, que sale del KM",
        "tarea": "Evaluación financiera pedida en esta corrida",
        "contexto": "Opcional — contexto adicional de otro agente o de quien invoca",
        "conocimiento": "{'frente_id': str} — modelo de casos.yaml, único camino de invocación",
        "herramientas": [
            "ver_informe_especialista", "search_bcra", "get_bcra_values", "search_series",
            "get_series_values", "search_official_stats", "buscar_corpus_cientifico",
            "web_search", "fetch_page_text", "pedir_informacion_faltante",
            "submit_modelo_financiero",
        ],
    },
}

OUTPUT_CONTRACT = {
    "agent": "financiero",
    "version": "1.0",
    "km_escribe": [
        "documento_caso conectado al frente vía frente_produce_documento (agente='financiero')",
        "pendiente conectado al caso vía tiene_pendiente (si usó pedir_informacion_faltante)",
    ],
    "fields": {
        "análisis": (
            "{'supuestos': list, 'capex': dict, 'opex': dict, 'ingresos_proyectados': dict, "
            "'pyl_multianual': list, 'flujo_de_caja': list, 'tasa_descuento': dict, 'van': dict, "
            "'tir': dict, 'payback': dict, 'riesgo_cambiario': dict, 'analisis_sensibilidad': "
            "dict, 'fuentes_y_cobertura': dict, 'informe_completo': str, ...}"
        ),
        "nivel_confianza": "'alto' | 'medio' | 'bajo' — basado en cuántos campos clave (tasa_descuento/van/tir) quedan a-confirmar",
        "recomendaciones": "ítems a-confirmar de mayor impacto",
        "próximo_agente": "None — no hay routing automático a otro especialista todavía",
        "nuevo_conocimiento": "lecciones_caso — aprendizajes de dominio para el loop de aprendizaje",
    },
}


# ── Tool dispatcher ───────────────────────────────────────────────────────────

async def _dispatch(name: str, inputs: dict, *, caso_id: str, verbose: bool) -> str:
    if name == "ver_informe_especialista":
        result = await obtener_documento_por_id(inputs.get("documento_id", ""), tenant=_TENANT)
    elif name == "search_bcra":
        result = search_bcra_variables(query=inputs["query"], max_results=inputs.get("max_results", 15))
    elif name == "get_bcra_values":
        result = get_bcra_values(
            id_variable=inputs["id_variable"], desde=inputs.get("desde"),
            hasta=inputs.get("hasta"), limit=inputs.get("limit", 30),
        )
    elif name == "search_series":
        result = search_series(query=inputs["query"], max_results=inputs.get("max_results", 10))
    elif name == "get_series_values":
        result = get_series_values(series_id=inputs["series_id"], last=inputs.get("last", 12))
    elif name == "search_official_stats":
        result = search_official_stats(
            query=inputs["query"], organization=inputs.get("organization"),
            max_results=inputs.get("max_results", 10),
        )
    elif name == "buscar_corpus_cientifico":
        result = await buscar_corpus_cientifico(consulta=inputs["consulta"], limit=inputs.get("limit", 100))
    elif name == "fetch_page_text":
        result = fetch_page_text(url=inputs["url"], max_chars=inputs.get("max_chars", 8000))
    elif name == "pedir_informacion_faltante":
        if not caso_id:
            result = {"success": False, "error": "Sin caso_id disponible en esta corrida (modo consulta libre) — no se puede crear un pendiente."}
        else:
            result = await crear_pendiente(caso_id, inputs.get("descripcion", ""), tenant=_TENANT)
        if verbose:
            print(f"  -> pedir_informacion_faltante: {inputs.get('descripcion', '')[:80]}")
    else:
        result = {"error": f"Tool desconocida: {name}"}
    return json.dumps(result, ensure_ascii=False, indent=2, default=str)


# ── Input builder ─────────────────────────────────────────────────────────────

def build_input_desde_frente(
    frente_dict: dict, caso_dict: dict, pendientes: list[dict],
    documentos_aportados: list[dict] | None = None,
    documentos_producidos: list[dict] | None = None,
) -> str:
    """Construye el input contra el modelo de casos.yaml (frente_id) — mismo patrón que los otros
    5 especialistas, ver microbiologo_agent.py::build_input_desde_frente."""
    caso_props = caso_dict.get("props") or {}
    frente_props = frente_dict.get("props") or {}

    secciones = [
        f"# Caso\n\n**Nombre:** {caso_props.get('nombre', '')}\n\n{caso_props.get('descripcion', '')}",
        f"# Frente: {frente_props.get('nombre', '')}\n\n{frente_props.get('descripcion', '')}",
    ]

    if pendientes:
        lista = "\n".join(f"- {(p.get('props') or {}).get('descripcion', '')}" for p in pendientes)
        secciones.append(f"# Pendientes abiertos del caso (contexto, no necesariamente de este frente)\n\n{lista}")

    if documentos_producidos:
        lista = "\n".join(
            f"- [{d.get('id', '')}] {(d.get('props') or {}).get('titulo', '')} "
            f"— {(d.get('props') or {}).get('agente', '')} ({(d.get('creado_en') or '')[:10]})"
            for d in documentos_producidos
        )
        secciones.append(
            "# Informes ya producidos en este frente (por otros especialistas)\n\n"
            f"{lista}\n\n"
            "Son solo títulos — usá ver_informe_especialista(documento_id) para leer el que "
            "identifica el producto/proceso candidato (PASO 0, obligatorio) y el del Agente de "
            "Mercado si existe. No hace falta leerlos todos."
        )

    if documentos_aportados:
        bloques = "\n\n".join(
            f"## {(d.get('props') or {}).get('titulo', '')}\n\n{(d.get('props') or {}).get('contenido', '')}"
            for d in documentos_aportados
        )
        secciones.append(f"# Documentos aportados por Sebas para este frente\n\n{bloques}")

    secciones.append(
        "---\n"
        "Tu tarea: construir el modelo económico-financiero completo (CAPEX, OPEX, P&L, flujo de "
        "caja, VAN, TIR, payback, sensibilidad) para el producto/proceso candidato de este "
        "frente. Llamá submit_modelo_financiero cuando tengas el modelo armado."
    )

    return "\n\n".join(secciones)


# ── Agentic loop ──────────────────────────────────────────────────────────────

def _bloque_instruccion(tarea: str | None, contexto_extra: str | None, foco: str | None = None) -> str:
    """Instrucción propia de ESTA invocación — ver market_agent._bloque_instruccion, mismo patrón."""
    partes = []
    if foco:
        partes.append(
            f"FOCO DE ESTA INVOCACIÓN: {foco}\n"
            "Priorizá este recorte por sobre el alcance general del modelo."
        )
    if tarea:
        partes.append(f"TAREA ESPECÍFICA DE ESTA INVOCACIÓN:\n{tarea}")
    if contexto_extra:
        partes.append(f"CONTEXTO ADICIONAL PROVISTO POR QUIEN TE INVOCA:\n{contexto_extra}")
    return ("\n\n" + "\n\n".join(partes)) if partes else ""


async def _preflight() -> None:
    preflight = await run_preflight([
        FuenteCheck("corpus_cientifico", bloqueante=True, check_fn=_check_corpus_cientifico),
        FuenteCheck("BCRA", bloqueante=True, check_fn=_check_bcra),
        FuenteCheck("web_search", bloqueante=True, check_fn=_check_web_search),
    ])
    for adv in preflight.advertencias:
        logging.getLogger(__name__).warning(adv)
    if not preflight.ok:
        raise RuntimeError(
            "Pre-flight bloqueante — Agente Financiero no puede continuar:\n"
            + "\n".join(preflight.bloqueantes)
        )


async def _run_loop(
    identificador: str,
    caso_id: str,
    system_blocks: list[dict],
    user_message: str,
    model: str,
    verbose: bool,
) -> tuple[str, dict, list[str], TokenTracker]:
    """Loop agéntico de la corrida formal (termina en submit_modelo_financiero) — cliente nativo
    de Anthropic, mismo patrón que market_agent._run_loop. No persiste nada al KM salvo, si el
    modelo llamó pedir_informacion_faltante, el/los pendiente(s) (efecto de la tool en sí, no un
    paso aparte de persistencia)."""
    tracker = TokenTracker(agent=_AGENTE, oportunidad_id=identificador, model=model)
    messages = [{"role": "user", "content": user_message}]
    modelo_result = None
    web_search_calls = 0
    web_search_results_total = 0

    while True:
        for attempt in range(4):
            try:
                response = client.messages.create(
                    model=model, max_tokens=16000,
                    system=system_blocks, tools=TOOLS, messages=messages,
                )
                break
            except anthropic.RateLimitError:
                if attempt == 3:
                    raise
                wait = 20 * (attempt + 1)
                if verbose:
                    print(f"  [rate limit — esperando {wait}s...]\n")
                time.sleep(wait)

        messages.append({"role": "assistant", "content": response.content})
        tracker.add(response.usage)

        for block in response.content:
            if block.type == "web_search_tool_result":
                content = getattr(block, "content", None)
                if isinstance(content, list):
                    web_search_results_total += len(content)
            elif block.type == "server_tool_use" and getattr(block, "name", "") == "web_search":
                web_search_calls += 1
                if verbose:
                    query = (getattr(block, "input", {}) or {}).get("query", "")
                    print(f"-> web_search: {query}")

        if response.stop_reason == "max_tokens" and not modelo_result:
            raise RuntimeError(
                "Respuesta truncada por max_tokens antes de submit_modelo_financiero "
                f"(max_tokens=16000, output={response.usage.output_tokens}). "
                "El modelo está incompleto."
            )

        if response.stop_reason in ("end_turn", "max_tokens"):
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                if block.name == "submit_modelo_financiero":
                    modelo_result = block.input
                    if verbose:
                        print("-> submit_modelo_financiero [capturado]\n")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps({"success": True, "message": "Modelo financiero registrado."}),
                    })
                    continue

                if verbose:
                    preview = json.dumps(block.input, ensure_ascii=False)
                    print(f"-> {block.name}")
                    print(f"   {preview[:120]}{'...' if len(preview) > 120 else ''}")

                result_str = await _dispatch(block.name, block.input, caso_id=caso_id, verbose=verbose)

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_str,
                })

            messages.append({"role": "user", "content": tool_results})

            if modelo_result:
                break
        else:
            break

    tracker.log(verbose)

    if not modelo_result:
        # getattr(b, "text", None), no hasattr — bloques nativos de Anthropic distintos de texto
        # (server_tool_use, web_search_tool_result) tienen atributo `text` en None, hasattr da
        # True igual (bug real encontrado en market_agent.py, 2026-09-07 — mismo cliente nativo).
        resumen = next(
            (b.text for b in response.content if getattr(b, "text", None)),
            "Modelo incompleto — el agente no llamó submit_modelo_financiero.",
        )
        return resumen, {}, [], tracker

    informe = modelo_result.get("informe_completo", "")
    lecciones_auto = modelo_result.get("lecciones_caso") or []
    fuentes_y_cobertura = modelo_result.get("fuentes_y_cobertura") or {
        "fuentes_consultadas": [],
        "cobertura_declarada": "parcial-por-falla-de-fuente",
    }
    _merge_web_search_coverage(fuentes_y_cobertura, web_search_calls, web_search_results_total)

    modelo_dict = {
        "supuestos": modelo_result.get("supuestos", []),
        "capex": modelo_result.get("capex", {}),
        "opex": modelo_result.get("opex", {}),
        "ingresos_proyectados": modelo_result.get("ingresos_proyectados", {}),
        "pyl_multianual": modelo_result.get("pyl_multianual", []),
        "flujo_de_caja": modelo_result.get("flujo_de_caja", []),
        "tasa_descuento": modelo_result.get("tasa_descuento", {}),
        "van": modelo_result.get("van", {}),
        "tir": modelo_result.get("tir", {}),
        "payback": modelo_result.get("payback", {}),
        "riesgo_cambiario": modelo_result.get("riesgo_cambiario", {}),
        "analisis_sensibilidad": modelo_result.get("analisis_sensibilidad", {}),
        "informacion_faltante_pedida": modelo_result.get("informacion_faltante_pedida", []),
        "fuentes_y_cobertura": fuentes_y_cobertura,
        "agente": _AGENTE,
        "fecha": date.today().isoformat(),
        "modelo": model,
        "informe_completo": informe,
    }

    return informe, modelo_dict, lecciones_auto, tracker


async def run_agent_desde_frente(
    frente_id: str,
    verbose: bool = False,
    model: str = DEFAULT_MODEL,
    tarea: str | None = None,
    contexto_extra: str | None = None,
    foco: str | None = None,
) -> tuple[str, dict, list[str]]:
    """
    Corre el Agente Financiero contra un frente del modelo de casos.yaml — único camino de
    invocación desde el arranque (mismo criterio que los otros 5).

    Returns:
        (informe_markdown, modelo_dict, lecciones_caso)
        No escribe documento_caso al KM — eso lo hace la costura (orquestador/invocador.py). SÍ
        puede escribir pendiente(s) directo (efecto de pedir_informacion_faltante durante el loop).
    """
    if verbose:
        print(f"\n{'='*60}\n  AGENTE FINANCIERO — CRIZA (frente)\n  Modelo: {model}\n{'='*60}\n")

    contexto = await obtener_frente_con_caso(frente_id, tenant=_TENANT)
    frente_dict, caso_dict = contexto["frente"], contexto["caso"]
    if not frente_dict:
        raise ValueError(f"Frente {frente_id} no encontrado en el KM")
    if not caso_dict:
        raise ValueError(f"Frente {frente_id} no tiene un caso asociado (conexión tiene_frente ausente)")

    await _preflight()

    pendientes = await obtener_pendientes_de_caso(caso_dict["id"], tenant=_TENANT)
    documentos_aportados = await obtener_documentos_aportados_de_frente(frente_id, tenant=_TENANT)
    documentos_producidos = await obtener_documentos_de_frente(frente_id, tenant=_TENANT)

    await aprendizaje.ensure_area(tenant=_TENANT)
    caso_props = caso_dict.get("props") or {}
    bloque = await aprendizaje.bloque_lecciones_para_prompt(
        agente=_AGENTE,
        consulta=caso_props.get("descripcion") or caso_props.get("nombre") or frente_id,
        tenant=_TENANT,
    )
    system_blocks = [{
        "type": "text",
        "text": SYSTEM_PROMPT + bloque,
        "cache_control": {"type": "ephemeral"},
    }]
    user_message = build_input_desde_frente(
        frente_dict, caso_dict, pendientes, documentos_aportados, documentos_producidos
    ) + _bloque_instruccion(tarea, contexto_extra, foco)

    informe, modelo_dict, lecciones_auto, tracker = await _run_loop(
        frente_id, caso_dict["id"], system_blocks, user_message, model, verbose
    )

    existing_tu = (frente_dict.get("props") or {}).get("token_usage") or {}
    existing_tu[_AGENTE] = tracker.to_dict()
    await motor_api.actualizar_props(frente_id, {"token_usage": existing_tu}, tenant=_TENANT)

    return informe, modelo_dict, lecciones_auto


# ── Interfaz de contrato estándar (SEB-115) ───────────────────────────────────

def _derive_confidence(modelo: dict) -> str:
    if not modelo:
        return "bajo"
    campos_clave = [modelo.get("tasa_descuento") or {}, modelo.get("van") or {}, modelo.get("tir") or {}]
    a_confirmar = sum(1 for c in campos_clave if c.get("estado") == "a-confirmar")
    if a_confirmar == 0:
        return "alto"
    if a_confirmar == 1:
        return "medio"
    return "bajo"


async def run(
    contract_input: dict,
    verbose: bool = False,
    model: str = DEFAULT_MODEL,
) -> dict:
    """Interfaz de contrato estándar para el Orquestador (SEB-115). Solo acepta frente_id."""
    conocimiento = contract_input.get("conocimiento") or {}
    frente_id = conocimiento.get("frente_id") if isinstance(conocimiento, dict) else None
    oportunidad_id = conocimiento.get("oportunidad_id") if isinstance(conocimiento, dict) else None

    if oportunidad_id:
        raise ValueError("Agente Financiero solo acepta 'frente_id' en contract_input['conocimiento'] — no soporta 'oportunidad_id'")
    if not frente_id:
        raise ValueError("Agente Financiero requiere 'frente_id' en contract_input['conocimiento']")

    informe, modelo, lecciones = await run_agent_desde_frente(
        frente_id,
        verbose=verbose,
        model=model,
        tarea=contract_input.get("tarea") or None,
        contexto_extra=contract_input.get("contexto") or None,
        foco=contract_input.get("caso") or None,
    )

    a_confirmar_criticos = [
        s["variable"] for s in (modelo.get("supuestos") or [])
        if s.get("estado") == "a-confirmar"
    ]

    return {
        "análisis": modelo,
        "nivel_confianza": _derive_confidence(modelo),
        "recomendaciones": a_confirmar_criticos[:3],
        "próximo_agente": None,
        "nuevo_conocimiento": lecciones,
    }


# ── Chat conversacional (mismo patrón que los otros 5 especialistas) ───────────
#
# Distinto de run()/run_agent_desde_frente() (contrato SEB-115, un turno, termina en
# submit_modelo_financiero, la costura persiste un documento_caso) — esto es para que Sebas pueda
# CONVERSAR con el Agente Financiero sin que cada intercambio dispare un modelo formal.
# TOOLS_CHAT excluye submit_modelo_financiero a propósito.

TOOLS_CHAT = [t for t in TOOLS if t.get("name") != "submit_modelo_financiero"]


async def iniciar_sesion(frente_id: str, *, tenant: str = _TENANT) -> list[dict]:
    """Arma el primer mensaje de una sesión de chat contra un frente — mismo contexto que
    run_agent_desde_frente() arma para una corrida de un turno."""
    contexto = await obtener_frente_con_caso(frente_id, tenant=tenant)
    frente_dict, caso_dict = contexto["frente"], contexto["caso"]
    if not frente_dict:
        raise ValueError(f"Frente {frente_id} no encontrado en el KM")
    if not caso_dict:
        raise ValueError(f"Frente {frente_id} no tiene un caso asociado (conexión tiene_frente ausente)")
    pendientes = await obtener_pendientes_de_caso(caso_dict["id"], tenant=tenant)
    documentos_aportados = await obtener_documentos_aportados_de_frente(frente_id, tenant=tenant)
    documentos_producidos = await obtener_documentos_de_frente(frente_id, tenant=tenant)
    user_input = build_input_desde_frente(
        frente_dict, caso_dict, pendientes, documentos_aportados, documentos_producidos
    )
    return [{"role": "user", "content": user_input}]


async def enviar_mensaje(
    messages: list[dict],
    texto_usuario: str,
    frente_id: str | None = None,
    model: str = DEFAULT_MODEL,
    verbose: bool = False,
    tracker: TokenTracker | None = None,
    tenant: str = _TENANT,
) -> tuple[str, list[dict]]:
    """
    Un turno de chat con el Agente Financiero. `messages` se muta y se devuelve, mismo patrón que
    `conductor.enviar_mensaje()`. Usa el cliente nativo de Anthropic — TOOLS_CHAT incluye
    `web_search`.

    `frente_id=None` es el modo "consulta libre" — Sebas puede preguntarle algo puntual sin
    necesitar un caso/frente ya creado. En ese modo, pedir_informacion_faltante no puede crear un
    pendiente real (no hay caso_id) — _dispatch lo declara explícitamente en vez de fallar mudo.
    """
    messages.append({"role": "user", "content": texto_usuario})
    tracker = tracker or TokenTracker(agent=_AGENTE, oportunidad_id=frente_id or "", model=model)

    await aprendizaje.ensure_area(tenant=tenant)
    caso_id = ""
    if frente_id:
        contexto = await obtener_frente_con_caso(frente_id, tenant=tenant)
        caso_dict = contexto["caso"] or {}
        caso_id = caso_dict.get("id") or ""
        caso_props = caso_dict.get("props") or {}
        consulta_lecciones = caso_props.get("descripcion") or caso_props.get("nombre") or frente_id
    else:
        consulta_lecciones = texto_usuario
    bloque = await aprendizaje.bloque_lecciones_para_prompt(agente=_AGENTE, consulta=consulta_lecciones, tenant=tenant)
    system_blocks = [{"type": "text", "text": SYSTEM_PROMPT + bloque, "cache_control": {"type": "ephemeral"}}]

    while True:
        response = client.messages.create(
            model=model, max_tokens=4096,
            system=system_blocks, tools=TOOLS_CHAT, messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})
        tracker.add(response.usage)

        if response.stop_reason != "tool_use":
            texto = "".join(b.text for b in response.content if getattr(b, "text", None))
            return texto, messages

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            if verbose:
                print(f"  -> {block.name}({block.input})")
            result_str = await _dispatch(block.name, block.input, caso_id=caso_id, verbose=verbose)
            tool_results.append({
                "type": "tool_result", "tool_use_id": block.id,
                "content": result_str,
            })

        messages.append({"role": "user", "content": tool_results})
