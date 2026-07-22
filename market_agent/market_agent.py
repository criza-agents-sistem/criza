"""
Agente de Mercado CRIZA v1 (SEB-148)

Demand-first. Evalúa cruces 1 (demanda), 3 (competencia) y 4 (viabilidad en contexto)
para oportunidades de biotech agro. No analiza importaciones.

Tools: buscar_corpus_cientifico, search_series, get_series_values,
       search_official_stats, fetch_page_text, draft_outreach_email, submit_analysis.
"""

import asyncio
import json
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
_KM_PATH = _AGENT_DIR.parent.parent / "knowledge_module"
# KM primero, criza/ segundo, luego el directorio local — local queda en posición 0 para que
# 'from tools import ...' encuentre market_agent/tools/ y no knowledge_module/tools/
sys.path.insert(0, str(_KM_PATH))
sys.path.insert(0, str(_CRIZA_DIR))
sys.path.insert(0, str(_AGENT_DIR))

# Importar tools ANTES de motor/aprendizaje: motor/api.py hace sys.path.insert(0, KM) al
# importarse, lo que empujaría KM delante de AGENT_DIR. Importando tools primero, Python
# cachea sys.modules['tools'] = market_agent/tools/ antes de que motor altere el orden.
from tools import (
    buscar_corpus_cientifico,
    search_official_stats,
    search_series,
    get_series_values,
    fetch_page_text,
    draft_outreach_email,
)

from motor import api as motor_api
import aprendizaje
from utils.token_tracker import TokenTracker
from preflight import FuenteCheck, FuenteCheckResult, run_preflight
from db import get_session_factory
from sqlalchemy import text as _sql_text

client = anthropic.Anthropic()
DEFAULT_MODEL = os.getenv("MARKET_MODEL", "claude-sonnet-4-6")
_AGENTE = "mercado"
_TENANT = "criza"
_WEB_SEARCH_MAX_USES = 5

# Documento compartido — cargado en runtime, mismo patrón que investigacion_amplia/armador:
# cualquier cambio al marco se aplica automáticamente sin tocar código.
_MARCO = (_CRIZA_DIR / "docs" / "marco_blue_ocean_CRIZA.md").read_text(encoding="utf-8")


# ── Pre-flight check ──────────────────────────────────────────────────────────

async def _check_corpus_cientifico() -> FuenteCheckResult:
    """CONICET+INTA vía corpus_cientifico — fuente que controlamos, bloqueante."""
    async with get_session_factory()() as s:
        r = await s.execute(_sql_text(
            "SELECT COUNT(*) FROM ficha f "
            "JOIN tipo_ficha tf ON tf.id = f.tipo_ficha_id "
            "JOIN area a ON a.id = tf.area_id "
            "WHERE a.nombre = 'corpus_cientifico' AND a.tenant_id = :t"
        ), {"t": _TENANT})
        total = r.scalar() or 0
    return FuenteCheckResult(ok=total > 0, detalle=f"{total} fichas", conteo=total)


async def _check_datos_gob_ar() -> FuenteCheckResult:
    """datos.gob.ar — externo, no bloqueante (puede estar caído sin que sea nuestro error)."""
    result = search_official_stats(query="agro", max_results=1)
    if result.get("success"):
        return FuenteCheckResult(ok=True, detalle="reachable")
    return FuenteCheckResult(ok=False, detalle=result.get("error") or "sin detalle")


async def _check_web_search() -> FuenteCheckResult:
    """web_search (tool nativo Anthropic) — bloqueante: sin esto, Cruce 3 no puede
    descubrir competencia real, solo confirmar URLs que el agente ya conoce."""
    if os.getenv("ANTHROPIC_API_KEY"):
        return FuenteCheckResult(ok=True, detalle="ANTHROPIC_API_KEY configurada")
    return FuenteCheckResult(ok=False, detalle="ANTHROPIC_API_KEY no configurada")


def _merge_web_search_coverage(fuentes_y_cobertura: dict, calls: int, results_total: int) -> None:
    """Pisa (o agrega) la entrada 'web_search' en fuentes_y_cobertura con el conteo
    objetivo de la tool server-side — no confiamos en que el modelo lo autoreporte bien
    (veracidad por dato: establecido > asumido)."""
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
        "name": "buscar_corpus_cientifico",
        "description": (
            "Busca en el corpus científico local: papers de CONICET, INTA y repositorios argentinos.\n"
            "Retorna: título, abstract (hasta 500 chars), autores, año, URL. Sin latencia de red.\n\n"
            "Cuándo usar:\n"
            "- PRIMER PASO SIEMPRE — evidencia local del dolor o del problema (Cruce 1)\n"
            "- Estado del arte de soluciones existentes en la literatura argentina (Cruce 3)\n"
            "- Validar la urgencia del problema con datos de investigación local\n\n"
            "Queries efectivos (describir el problema o el sector):\n"
            "- 'olor estiércol porcino manejo ambiental'\n"
            "- 'garrapata resistencia acaricida bovino'\n"
            "- 'fitasa digestibilidad fósforo monogástrico'\n"
            "Sin resultados → declarar 'literatura local no encontrada' (a-confirmar)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "consulta": {"type": "string", "description": "Problema, solución o sector a buscar"},
                "limit": {"type": "integer", "description": "Máximo de papers (default 100 — corpus_cientifico completo, no muestrear)", "default": 100},
            },
            "required": ["consulta"],
        },
    },
    {
        "name": "search_series",
        "description": (
            "Busca SERIES DE TIEMPO en la API de datos.gob.ar (INDEC, MAGyP, Economía).\n"
            "Retorna: id, descripción, unidad, frecuencia, rango temporal, publicador.\n"
            "Usá get_series_values(series_id) para traer los valores numéricos de la serie elegida.\n\n"
            "Cuándo usar:\n"
            "- Cruce 1 — tamaño del sector: stock de animales, superficie sembrada, producción\n"
            "- Para cuantificar cuántos productores/hectáreas/cabezas tienen el problema\n\n"
            "Queries útiles: 'producción porcina', 'faena porcina', 'stock bovino',\n"
            "'producción soja', 'producción avícola', 'superficie soja sembrada'"
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
        "description": (
            "Trae los últimos N valores de una serie por su id (datos.gob.ar).\n"
            "Retorna: lista de {fecha, valor} — más reciente primero.\n\n"
            "Cuándo usar:\n"
            "- Después de search_series para obtener los números reales\n"
            "- Pedí last=4 o last=8 para el promedio reciente"
        ),
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
            "Busca datasets en el catálogo datos.gob.ar (INDEC, MAGyP, SENASA, Aduana).\n"
            "Retorna: títulos, descripciones, URLs de descarga CSV/XLS.\n"
            "Diferencia con search_series: devuelve datasets para descargar, no valores.\n\n"
            "Cuándo usar:\n"
            "- Para encontrar datasets del sector afectado\n"
            "- Estadísticas de SENASA sobre registros de productos\n\n"
            "Organismos: 'magyp' (agro), 'senasa' (sanidad animal/vegetal), 'indec' (macro)"
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
        "name": "fetch_page_text",
        "description": (
            "Descarga y extrae el texto de una URL pública.\n\n"
            "Cuándo usar:\n"
            "- Cruce 3: competidores locales — ¿quién ya ofrece la solución en Argentina?\n"
            "- Cruce 3: SENASA — productos habilitados en la categoría (senasa.gob.ar)\n"
            "- Cruce 4: encuadre regulatorio — resoluciones SENASA aplicables\n"
            "- Cruce 4: asociaciones de productores — canal de llegada al mercado\n\n"
            "Fuentes clave AR:\n"
            "- SENASA registros: senasa.gob.ar / argentina.gob.ar/senasa\n"
            "- CAENA (nutrición animal): caena.org.ar\n"
            "- BCR (granos/agro): bcr.com.ar\n"
            "- MAGYP: magyp.gob.ar\n"
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
        "name": "draft_outreach_email",
        "description": (
            "Redacta un email de contacto para APROBACIÓN HUMANA — nunca envía.\n\n"
            "Cuándo usar:\n"
            "- Solo si hay un gap CRÍTICO irreducible con fuentes públicas\n"
            "- SENASA: categoría regulatoria exacta de un producto nuevo\n"
            "- INTA o CREA: dimensión real del problema en el campo\n"
            "- Productores o distribuidores: condiciones de mercado reales\n\n"
            "Máximo 2 emails por corrida. Si hay más de 2 gaps, elegí los más críticos.\n"
            "Status siempre PENDIENTE_APROBACION — nunca decir 'vamos a enviar'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "recipient_company": {"type": "string", "description": "Empresa destinataria"},
                "recipient_role": {"type": "string", "description": "Cargo del destinatario"},
                "product_or_ingredient": {"type": "string", "description": "Producto o categoría"},
                "context": {"type": "string", "description": "Qué información se necesita y por qué"},
                "sender_name": {"type": "string", "description": "Remitente", "default": "Equipo CRIZA"},
                "language": {"type": "string", "description": "'es' (default) o 'en'", "default": "es"},
            },
            "required": ["recipient_company", "recipient_role", "product_or_ingredient", "context"],
        },
    },
    {
        "name": "submit_analysis",
        "description": (
            "Envía el análisis completo — LLAMAR SIEMPRE COMO ÚLTIMO PASO.\n"
            "Solo llamar cuando consultaste las fuentes para los tres cruces.\n"
            "Un expediente con gaps declarados es mejor que uno que no cierra."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "cruce_1": {
                    "type": "object",
                    "description": "Demanda real no resuelta",
                    "properties": {
                        "tamaño": {
                            "type": "object",
                            "properties": {
                                "valor": {"type": "string"},
                                "unidad": {"type": "string"},
                                "fuente": {"type": "string"},
                                "estado": {"type": "string", "enum": ["establecido", "asumido", "a-confirmar"]},
                            },
                            "required": ["valor", "estado"],
                        },
                        "urgencia": {
                            "type": "object",
                            "properties": {
                                "valor": {"type": "string"},
                                "estado": {"type": "string"},
                                "peso": {"type": "string", "enum": ["alto", "medio", "bajo"]},
                            },
                            "required": ["valor", "estado", "peso"],
                        },
                        "evidencia": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Fuentes que evidencian la demanda",
                        },
                    },
                    "required": ["tamaño", "urgencia", "evidencia"],
                },
                "cruce_3": {
                    "type": "object",
                    "description": "Competencia",
                    "properties": {
                        "qué_existe": {
                            "type": "object",
                            "properties": {
                                "valor": {"type": "string"},
                                "estado": {"type": "string"},
                                "fuente": {"type": "string"},
                            },
                            "required": ["valor", "estado"],
                        },
                        "registros_senasa": {
                            "type": "object",
                            "properties": {
                                "estado": {"type": "string"},
                                "dónde_confirmar": {"type": "string"},
                            },
                            "required": ["estado"],
                        },
                        "intensidad": {
                            "type": "object",
                            "properties": {
                                "valor": {"type": "string", "enum": ["vacío", "débil", "fuerte"]},
                                "estado": {"type": "string"},
                            },
                            "required": ["valor", "estado"],
                        },
                    },
                    "required": ["qué_existe", "intensidad"],
                },
                "cruce_4": {
                    "type": "object",
                    "description": "Viabilidad en contexto",
                    "properties": {
                        "encuadre_regulatorio": {
                            "type": "object",
                            "properties": {
                                "valor": {"type": "string"},
                                "estado": {"type": "string"},
                            },
                            "required": ["valor", "estado"],
                        },
                        "accesibilidad_mercado": {
                            "type": "object",
                            "properties": {
                                "valor": {"type": "string"},
                                "estado": {"type": "string"},
                                "dónde_confirmar": {"type": "string"},
                            },
                            "required": ["valor", "estado"],
                        },
                        "factibilidad_costo": {
                            "type": "object",
                            "properties": {
                                "valor": {"type": "string"},
                                "estado": {"type": "string"},
                                "dónde_confirmar": {"type": "string"},
                            },
                            "required": ["valor", "estado"],
                        },
                    },
                    "required": ["encuadre_regulatorio", "accesibilidad_mercado", "factibilidad_costo"],
                },
                "bloque_6_anclas": {
                    "type": "object",
                    "properties": {
                        "inversión": {
                            "type": "object",
                            "properties": {
                                "comparables": {"type": "string"},
                                "estado": {"type": "string"},
                            },
                        },
                        "regulatorio": {
                            "type": "object",
                            "properties": {
                                "camino": {"type": "string"},
                                "plazo": {"type": "string"},
                                "estado": {"type": "string"},
                            },
                        },
                    },
                },
                "sustitucion_importacion": {
                    "type": "object",
                    "description": "Condición 12 del marco blue ocean — la única 'sin excepción'. Obligatorio declararla, nunca omitirla.",
                    "properties": {
                        "es_sustitucion": {"type": "boolean"},
                        "justificacion": {"type": "string", "description": "Por qué sí/no aplica — evidencia, no juicio de valor"},
                    },
                    "required": ["es_sustitucion", "justificacion"],
                },
                "valor_cliente": {
                    "type": "object",
                    "description": "Las 6 maneras en que la oportunidad aporta valor (marco blue ocean). Evaluar TODAS explícitamente, sin prejuzgar dónde va a estar el valor.",
                    "properties": {
                        "productividad":     {"type": "string", "enum": ["fuerte", "presente", "no-aplica"]},
                        "reduccion_riesgo":  {"type": "string", "enum": ["fuerte", "presente", "no-aplica"]},
                        "conveniencia":      {"type": "string", "enum": ["fuerte", "presente", "no-aplica"]},
                        "simplicidad":       {"type": "string", "enum": ["fuerte", "presente", "no-aplica"]},
                        "imagen":            {"type": "string", "enum": ["fuerte", "presente", "no-aplica"]},
                        "cuidado_ambiente":  {"type": "string", "enum": ["fuerte", "presente", "no-aplica"]},
                    },
                    "required": ["productividad", "reduccion_riesgo", "conveniencia", "simplicidad", "imagen", "cuidado_ambiente"],
                },
                "fuentes_y_cobertura": {
                    "type": "object",
                    "description": "Qué fuentes se consultaron y con qué cobertura — obligatorio (orchestration-layer.md Decisión 6). Declarar corpus_cientifico, datos.gob.ar y web_search como mínimo.",
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
                "gaps_prioritarios": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Hasta 3 gaps críticos que quedan a-confirmar",
                },
                "resumen_markdown": {
                    "type": "string",
                    "description": "Resumen legible en markdown para Sebas — datos clave de cada cruce, gaps, y señal de blue ocean o no",
                },
                "lecciones_caso": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Aprendizajes de dominio de esta corrida para el loop de aprendizaje",
                },
            },
            "required": [
                "cruce_1", "cruce_3", "cruce_4", "resumen_markdown",
                "sustitucion_importacion", "valor_cliente", "fuentes_y_cobertura",
            ],
        },
    },
]

# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    _MARCO
    + "\n\n---\n\n"
    + """Sos el Agente de Mercado de CRIZA v1. Tu misión: evaluar si hay una DEMANDA REAL NO RESUELTA para una oportunidad de biotech agro, y qué tan accesible es ese mercado para una empresa emergente argentina.

El marco cargado arriba define QUÉ es un blue ocean para CRIZA — las 12 condiciones must, las
2 should, y las 6 maneras en que algo aporta valor. Tu análisis las usa directamente, no las
reinterpreta. En particular: la condición 12 (no sustitución de importación) es la única "sin
excepción" del marco — la declarás siempre en submit_analysis, nunca la omitís.

FRAMEWORK: llenás tres cruces del expediente de decisión.

─── CRUCE 1 — Demanda real no resuelta ───
¿Cuántos productores tienen este problema? → search_series (stock, producción del sector afectado)
¿Qué tan grave/urgente es el dolor? → buscar_corpus_cientifico, fetch_page_text (noticias, asociaciones)
¿Hay evidencia científica local? → buscar_corpus_cientifico (papers CONICET/INTA, corpus_cientifico completo)

─── CRUCE 3 — Competencia ───
¿Quién ya resuelve esto en Argentina? → web_search PRIMERO (descubrir competidores, productos, registros — no lo sabés de antemano, buscalo)
¿Qué dice la página encontrada en detalle? → fetch_page_text sobre los resultados más relevantes de web_search
¿Hay productos registrados/habilitados? → web_search + fetch_page_text en senasa.gob.ar
¿Qué tan fuerte es la competencia? → tu juicio sobre lo que ENCONTRASTE buscando, no sobre lo que ya sabías (no te dejes anclar — marco cargado arriba)

─── CRUCE 4 — Viabilidad en contexto ───
¿Qué regulación aplica? → web_search + fetch_page_text (SENASA uso animal, ANMAT humano, MAGYP agro-alimentos)
¿Cómo se llega a los compradores? → web_search (asociaciones de productores, distribuidores)
¿Es factible en costo? → comparables, estimaciones razonables; a-confirmar si no hay datos

WORKFLOW OBLIGATORIO (en orden):
1. buscar_corpus_cientifico — literatura argentina sobre el problema (corpus_cientifico completo: CONICET+INTA)
2. search_series + get_series_values — tamaño del sector afectado en números
3. search_official_stats — datasets complementarios del sector
4. web_search — descubrir competidores/soluciones/registros reales (Cruce 3 y 4). NO uses tu
   conocimiento de entrenamiento para nombrar competidores — buscalo, es verificable o no lo afirmes.
5. fetch_page_text (hasta 3 páginas) — profundizar en los resultados más relevantes de web_search
6. draft_outreach_email (máximo 2) — solo para gaps críticos irreducibles
7. submit_analysis — SIEMPRE el último paso, aunque falten datos. Incluye obligatoriamente
   sustitucion_importacion, valor_cliente (las 6 dimensiones) y fuentes_y_cobertura.

CONVENCIÓN DE ESTADO — OBLIGATORIO en todo dato reportado:
- establecido: verificado, tiene fuente citable (paper CONICET, serie oficial, SENASA, resultado de web_search)
- asumido: sin verificar; incluir peso (¿cuánto depende la tesis de este dato?)
- a-confirmar: no disponible públicamente; incluir dónde_confirmar

NUNCA un número sin estado. Gap declarado > inferencia disfrazada.
NUNCA un competidor sin fuente de web_search o fetch_page_text — un nombre "recordado" sin
búsqueda real es exactamente el sesgo de anclaje que el marco prohíbe.

REGLAS:
- Máximo 3 fetch_page_text por corrida — elegí bien las URLs (las que devolvió web_search).
- Máximo 2 draft_outreach_email — solo gaps críticos irreducibles.
- submit_analysis es el último paso — siempre llamarlo.
  Un expediente con gaps declarados es mejor que uno que no cierra.
- Emails: siempre PENDIENTE_APROBACION. Nunca decir "vamos a enviar"."""
)


# ── Contrato estándar (SEB-115) ───────────────────────────────────────────────

INPUT_CONTRACT = {
    "agent": "mercado",
    "version": "1.1",
    "fields": {
        "caso": "Descripción del dolor o problema a analizar",
        "tarea": "Evaluar cruces 1 (demanda), 3 (competencia) y 4 (viabilidad en contexto)",
        "contexto": "Opcional — outputs de agentes anteriores relevantes para el análisis de mercado",
        "conocimiento": "Opcional — {'oportunidad_id': str} para leer la ficha del KM",
        "herramientas": [
            "buscar_corpus_cientifico", "search_series", "get_series_values",
            "search_official_stats", "web_search", "fetch_page_text",
            "draft_outreach_email", "submit_analysis",
        ],
    },
}

OUTPUT_CONTRACT = {
    "agent": "mercado",
    "version": "1.2",
    # Contrato de conexión (2026-07-22): qué deja este agente en el KM para que otro lo
    # consuma. Lo verifica `check_km_conexion` del auditor contra el código real de ESTE
    # módulo — si la escritura vive en un runner, el camino orquestado no la ejecuta.
    "km_escribe": ["props.mercado"],
    "fields": {
        "análisis": (
            "{'resumen': str, 'cruces': {'cruce_1': dict, 'cruce_3': dict, 'cruce_4': dict, "
            "'sustitucion_importacion': dict, 'valor_cliente': dict, 'fuentes_y_cobertura': dict, ...}}"
        ),
        "nivel_confianza": (
            "'alto' | 'medio' | 'bajo' — basado en proporción de gaps_prioritarios; "
            "forzado a 'bajo' si sustitucion_importacion.es_sustitucion=true (condición 12, sin excepción)"
        ),
        "recomendaciones": "gaps_prioritarios — hasta 3 datos críticos para cerrar la decisión",
        "próximo_agente": None,
        "nuevo_conocimiento": "lecciones_caso — aprendizajes de dominio para el loop de aprendizaje",
    },
}


# ── Tool dispatcher ───────────────────────────────────────────────────────────

async def _dispatch(name: str, inputs: dict) -> str:
    if name == "buscar_corpus_cientifico":
        result = await buscar_corpus_cientifico(
            consulta=inputs["consulta"],
            limit=inputs.get("limit", 100),
        )
    elif name == "search_series":
        result = search_series(
            query=inputs["query"],
            max_results=inputs.get("max_results", 10),
        )
    elif name == "get_series_values":
        result = get_series_values(
            series_id=inputs["series_id"],
            last=inputs.get("last", 12),
        )
    elif name == "search_official_stats":
        result = search_official_stats(
            query=inputs["query"],
            organization=inputs.get("organization"),
            max_results=inputs.get("max_results", 10),
        )
    elif name == "fetch_page_text":
        result = fetch_page_text(
            url=inputs["url"],
            max_chars=inputs.get("max_chars", 8000),
        )
    elif name == "draft_outreach_email":
        result = draft_outreach_email(
            recipient_company=inputs["recipient_company"],
            recipient_role=inputs["recipient_role"],
            product_or_ingredient=inputs["product_or_ingredient"],
            context=inputs["context"],
            sender_name=inputs.get("sender_name", "Equipo CRIZA"),
            language=inputs.get("language", "es"),
        )
    else:
        result = {"error": f"Tool desconocida: {name}"}
    return json.dumps(result, ensure_ascii=False, indent=2)


# ── Agentic loop ──────────────────────────────────────────────────────────────

def _bloque_instruccion(
    tarea: str | None, contexto_extra: str | None, foco: str | None = None
) -> str:
    """Instrucción propia de ESTA invocación, para el mensaje de usuario.

    Va en el mensaje de usuario y NO en el SYSTEM_PROMPT a propósito: el system prompt
    es lo estable (y lo cacheable); esto es lo que cambia en cada corrida.

    Existe porque hasta 2026-07-22 el contrato SEB-115 declaraba `tarea` y `contexto`,
    los flows los pasaban en cada paso, y ningún agente los leía — así que todo agente
    corría siempre igual, sin enterarse de qué se le pedía esta vez. Ver
    `check_contrato_input_no_leido` del auditor.

    `foco` es el campo `caso` cuando además hay `oportunidad_id`. Importa: en
    `pipeline_sector` el `caso` es `{gate.candidato_elegido}` — la respuesta que da el
    humano en el gate. Hasta 2026-07-22 se descartaba (había oportunidad_id, así que
    `texto_libre` quedaba en None), o sea que la elección del humano no llegaba a
    ningún agente y todos re-analizaban el sector completo.
    """
    partes = []
    if foco:
        partes.append(
            f"FOCO DE ESTA INVOCACIÓN: {foco}\n"
            "Priorizá este recorte por sobre el alcance general de la oportunidad."
        )
    if tarea:
        partes.append(f"TAREA ESPECÍFICA DE ESTA INVOCACIÓN:\n{tarea}")
    if contexto_extra:
        partes.append(f"CONTEXTO ADICIONAL PROVISTO POR QUIEN TE INVOCA:\n{contexto_extra}")
    return ("\n\n" + "\n\n".join(partes)) if partes else ""


async def run_agent(
    oportunidad_id: str | None = None,
    texto_libre: str | None = None,
    oportunidad_descripcion: str | None = None,
    verbose: bool = True,
    model: str = DEFAULT_MODEL,
    tarea: str | None = None,
    contexto_extra: str | None = None,
    foco: str | None = None,
) -> tuple[str, dict, list[str]]:
    """
    Corre el agente de mercado.

    Args:
        oportunidad_id: UUID de la oportunidad en el KM (modo principal).
        texto_libre: Descripción sin KM (modo testing).
        oportunidad_descripcion: Override del texto de contexto (opcional con oportunidad_id).
        verbose: Imprime tool calls en tiempo real.
        model: Modelo Claude a usar.

    Returns:
        (resumen_markdown, cruces_dict, lecciones_auto)
        - cruces_dict: listo para write-back bajo clave "mercado" en el KM.
        - lecciones_auto: lista de strings para el loop de aprendizaje.
    """
    if verbose:
        print("\n" + "=" * 60)
        print(f"  AGENTE DE MERCADO CRIZA v1 — {model}")
        print("=" * 60 + "\n")

    tracker = TokenTracker(agent=_AGENTE, oportunidad_id=oportunidad_id or "test", model=model)

    # 1. Construir contexto de la oportunidad
    props: dict = {}
    if oportunidad_id:
        ficha = await motor_api.obtener(oportunidad_id, tenant=_TENANT)
        props = ficha.get("props", {}) if ficha else {}
        contexto_texto = oportunidad_descripcion or props.get("descripcion") or props.get("titulo") or ""
        user_message = (
            f"Oportunidad a analizar (id: {oportunidad_id}):\n\n"
            + json.dumps(props, ensure_ascii=False, indent=2)
        )
        if verbose:
            print(f"  Oportunidad: {contexto_texto[:100]}\n")
    else:
        contexto_texto = texto_libre or ""
        user_message = texto_libre or "Análisis de mercado libre."
        if verbose:
            print(f"  Modo testing: {contexto_texto[:100]}\n")

    user_message += _bloque_instruccion(tarea, contexto_extra, foco)

    # 1.5 Pre-flight: verificar fuentes críticas antes de arrancar el loop agéntico
    #     (objective-first — si lo que controlamos no está listo, frenamos).
    preflight = await run_preflight([
        FuenteCheck("corpus_cientifico", bloqueante=True, check_fn=_check_corpus_cientifico),
        FuenteCheck("datos.gob.ar", bloqueante=False, check_fn=_check_datos_gob_ar),
        FuenteCheck("web_search", bloqueante=True, check_fn=_check_web_search),
    ])
    if verbose:
        for adv in preflight.advertencias:
            print(f"  ⚠️  {adv}")
    if not preflight.ok:
        raise RuntimeError(
            "Pre-flight bloqueante — Agente de Mercado no puede continuar:\n"
            + "\n".join(preflight.bloqueantes)
        )

    # 2. Inyectar lecciones al system prompt
    await aprendizaje.ensure_area(tenant=_TENANT)
    bloque = await aprendizaje.bloque_lecciones_para_prompt(
        agente=_AGENTE,
        consulta=contexto_texto,
        tenant=_TENANT,
    )
    effective_system = SYSTEM_PROMPT + bloque
    # Prompt caching (2026-07-22): el loop agéntico reenvía el mismo system+tools en
    # cada vuelta (mercado hizo 6-7 llamadas en la corrida real) — sin esto, el prefijo
    # completo se factura a precio pleno todas las veces. El breakpoint en el último
    # bloque de system cachea tools+system juntos (orden de render: tools -> system ->
    # messages). ~9.5K chars de system + ~10.5K de tools, arriba del mínimo cacheable.
    system_blocks = [{
        "type": "text",
        "text": effective_system,
        "cache_control": {"type": "ephemeral"},
    }]

    # 3. Loop agéntico
    messages = [{"role": "user", "content": user_message}]
    analysis_result = None
    web_search_calls = 0
    web_search_results_total = 0

    while True:
        for attempt in range(4):
            try:
                response = client.messages.create(
                    model=model,
                    max_tokens=16000,
                    system=system_blocks,
                    tools=TOOLS,
                    messages=messages,
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

        # Conteo objetivo del uso de web_search (tool server-side) — no confiamos en que
        # el modelo lo autoreporte bien en fuentes_y_cobertura; esto pisa ese self-report.
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

        # max_tokens NO es terminación normal: la respuesta viene cortada y los
        # bloques tool_use de este turno nunca se procesan. Si todavía no capturamos
        # el análisis, fallar ruidoso — un resultado truncado no se persiste como válido.
        if response.stop_reason == "max_tokens" and not analysis_result:
            raise RuntimeError(
                "Respuesta truncada por max_tokens antes de submit_analysis "
                f"(max_tokens=16000, output={response.usage.output_tokens}). "
                "El análisis está incompleto."
            )

        if response.stop_reason in ("end_turn", "max_tokens"):
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                if block.name == "submit_analysis":
                    analysis_result = block.input
                    if verbose:
                        print("-> submit_analysis [análisis capturado]\n")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps({"success": True, "message": "Análisis registrado."}),
                    })
                else:
                    if verbose:
                        preview = json.dumps(block.input, ensure_ascii=False)
                        print(f"-> {block.name}")
                        print(f"   {preview[:120]}{'...' if len(preview) > 120 else ''}")

                    result_str = await _dispatch(block.name, block.input)

                    if verbose:
                        print(f"   done\n")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_str,
                    })

            messages.append({"role": "user", "content": tool_results})

            if analysis_result:
                break
        else:
            break

    # 4. Extraer resultado
    async def _persist_tokens() -> None:
        tracker.log(verbose)
        if oportunidad_id:
            existing = props.get("token_usage") or {}
            existing[_AGENTE] = tracker.to_dict()
            await motor_api.actualizar_props(oportunidad_id, {"token_usage": existing}, tenant=_TENANT)

    if not analysis_result:
        resumen = next(
            (b.text for b in response.content if hasattr(b, "text")),
            "Análisis incompleto — el agente no llamó submit_analysis.",
        )
        await _persist_tokens()
        return resumen, {}, []

    resumen_markdown = analysis_result.get("resumen_markdown", "")
    lecciones_auto = analysis_result.get("lecciones_caso") or []

    fuentes_y_cobertura = analysis_result.get("fuentes_y_cobertura") or {
        "fuentes_consultadas": [],
        "cobertura_declarada": "parcial-por-falla-de-fuente",
    }
    _merge_web_search_coverage(fuentes_y_cobertura, web_search_calls, web_search_results_total)

    cruces_dict = {
        "cruce_1":         analysis_result.get("cruce_1", {}),
        "cruce_3":         analysis_result.get("cruce_3", {}),
        "cruce_4":         analysis_result.get("cruce_4", {}),
        "bloque_6_anclas": analysis_result.get("bloque_6_anclas", {}),
        "sustitucion_importacion": analysis_result.get("sustitucion_importacion", {}),
        "valor_cliente":   analysis_result.get("valor_cliente", {}),
        "fuentes_y_cobertura": fuentes_y_cobertura,
        "gaps_prioritarios": analysis_result.get("gaps_prioritarios", []),
        "agente":          _AGENTE,
        "fecha":           date.today().isoformat(),
        "modelo":          model,
    }

    # Write-back al KM — resultado estructurado + informe narrativo completo.
    # Vive ACÁ y no en run.py (donde estaba) para que ocurra en TODOS los caminos:
    # el Motor llama run() -> run_agent() sin pasar por run.py, así que con la
    # escritura en el runner el pipeline orquestado nunca dejaba `props.mercado`
    # y el Armador se bloqueaba con "mercado: ausente". Mismo patrón que
    # evidence_generalista. Ver "Regla de escritura al KM" en CLAUDE.md.
    if oportunidad_id:
        await motor_api.actualizar_props(
            oportunidad_id,
            {"mercado": {**cruces_dict, "informe_completo": resumen_markdown}},
            tenant=_TENANT,
        )
        if verbose:
            print(f"  KM actualizado — cruces 1/3/4 + informe completo escritos.")

    await _persist_tokens()
    return resumen_markdown, cruces_dict, lecciones_auto


# ── Interfaz de contrato estándar (SEB-115) ───────────────────────────────────

def _derive_confidence(cruces: dict) -> str:
    # Sin cruces no hay análisis, y sin análisis no hay confianza. Un dict vacío
    # significa que el agente no llegó a producir el resultado (truncado, o sin
    # submit_analysis) — NO que no haya gaps. Sin esta guarda, `len(gaps) == 0`
    # más abajo devolvía "alto" para una corrida fallida.
    if not cruces:
        return "bajo"

    # Condición 12 del marco (sustitución de importación) — la única "sin excepción".
    # Estructural: no depende de que el modelo la respete en el resto del análisis.
    sustitucion = cruces.get("sustitucion_importacion") or {}
    if sustitucion.get("es_sustitucion") is True:
        return "bajo"

    gaps = cruces.get("gaps_prioritarios") or []
    if len(gaps) == 0:
        return "alto"
    if len(gaps) <= 1:
        return "medio"
    return "bajo"


async def run(
    contract_input: dict,
    verbose: bool = False,
    model: str = DEFAULT_MODEL,
) -> dict:
    """
    Interfaz de contrato estándar para el Orquestador (SEB-115).
    Wraps run_agent() — acepta y retorna el formato estándar de agente.
    """
    conocimiento = contract_input.get("conocimiento") or {}
    oportunidad_id = conocimiento.get("oportunidad_id") if isinstance(conocimiento, dict) else None
    texto_libre = contract_input.get("caso") or ""

    resumen, cruces, lecciones = await run_agent(
        oportunidad_id=oportunidad_id,
        texto_libre=texto_libre if not oportunidad_id else None,
        verbose=verbose,
        model=model,
        tarea=contract_input.get("tarea") or None,
        contexto_extra=contract_input.get("contexto") or None,
        # Con oportunidad_id, `caso` no es el input principal (eso sale del KM) pero sí
        # es el recorte pedido — en pipeline_sector es la respuesta del gate humano.
        foco=texto_libre if (oportunidad_id and texto_libre) else None,
    )

    return {
        "análisis": {"resumen": resumen, "cruces": cruces},
        "nivel_confianza": _derive_confidence(cruces),
        "recomendaciones": cruces.get("gaps_prioritarios", []),
        "próximo_agente": None,
        "nuevo_conocimiento": lecciones,
    }
