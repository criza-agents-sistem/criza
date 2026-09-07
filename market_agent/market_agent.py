"""
Agente de Mercado CRIZA (SEB-148, reconectado a casos.yaml en Etapa 20, 2026-09-07)

Demand-first. Evalúa cruces 1 (demanda), 3 (competencia) y 4 (viabilidad en contexto) para un
frente del modelo de casos.yaml — mismo patrón de conexión que los otros 4 especialistas
(microbiólogo/ingeniero ambiental/agrónomo/biotecnólogo). Ya no soporta `oportunidad_id` (el
modelo viejo, `pipeline_sector.yaml`/`pipeline_dolor.yaml`) — ningún caso real lo usa desde que
todo pasó a `casos.yaml`; mismo criterio que ya aplicaron los otros 4 al conectarse.

Quinto agente de la biblioteca de especialistas, y el primero adaptado de un agente ya existente
en vez de construido desde cero — decisión explícita de Sebas (docs/DESIGN_GATE.md decisión K):
sus tools/framework/excepción de web_search nativo son hard-won, adaptarlos no arriesga el mismo
sesgo que costó abandonar scientific_agent/specialist_proteins.py (ese tenía supuestos
INCORRECTOS hardcodeados a un caso cancelado; acá el gap era una consideración AUSENTE, no una
equivocada).

Sebas: "no quiero que lo del flete sea un sesgo... qué tipo de análisis haga dependerá de los
productos que son viables realizar técnicamente" — el agente NO asume mercado local ni
exportador de antemano. Lee los informes que otros especialistas (en particular el Biotecnólogo)
ya produjeron sobre este frente, y para cada producto candidato razona su densidad de valor
(valor económico por unidad de volumen/peso) para derivar qué alcance geográfico tiene sentido —
ver Decisión M del Design Gate.

Tools: buscar_corpus_cientifico, search_series, get_series_values, search_official_stats,
       web_search (nativo Anthropic), fetch_page_text, draft_outreach_email,
       ver_informe_especialista, submit_analysis.
"""

import asyncio
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

# Import calificado (market_agent.tools, no `tools` a secas) — market_agent/ ya es un paquete
# real (__init__.py agregado 2026-08-15) para que no colisione con el tools/ de ningún otro
# agente. Antes esto dependía de agregar market_agent/ a sys.path e importar `tools` como
# módulo top-level, lo que obligaba a orquestador/registry.py a limpiar sys.modules["tools"]
# a mano entre imports de agentes distintos.
from market_agent.tools import (
    buscar_corpus_cientifico,
    search_official_stats,
    search_series,
    get_series_values,
    fetch_page_text,
    draft_outreach_email,
)

from utils.casos import (
    obtener_frente_con_caso, obtener_pendientes_de_caso, obtener_documentos_aportados_de_frente,
    obtener_documentos_de_frente, obtener_documento_por_id,
)
from knowledge_module.motor import api as motor_api
import knowledge_module.aprendizaje as aprendizaje
from utils.token_tracker import TokenTracker
from knowledge_module.preflight import FuenteCheck, FuenteCheckResult, run_preflight
from knowledge_module.db import get_session_factory
from sqlalchemy import text as _sql_text

# Mercado es Anthropic-only por decisión — excepción permanente, no pendiente de migrar.
# Usa la tool nativa `web_search_20250305` (búsqueda que corre del lado del servidor de
# Anthropic, ver TOOLS abajo), sin equivalente en el traductor genérico de proveedores
# (utils/ai_client.py, que sí usan Evidence Generalista/Investigación Amplia/Armador desde el
# 2026-08-15). No aplica el mismo patrón acá porque no hay forma de expresar una tool nativa de
# un proveedor específico en el formato de función que el traductor entiende. Decisión
# `componente=ai_client` en `decisiones_sistema` (KM), confirmada por Sebas el 2026-08-15.
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
        "name": "ver_informe_especialista",
        "description": (
            "Trae el contenido completo de un informe puntual que otro especialista (o vos "
            "mismo antes) ya produjo sobre este mismo frente — ver la lista 'Informes ya "
            "producidos en este frente' en tu input. Usala SIEMPRE que necesites identificar qué "
            "producto(s) candidato(s) evaluar (el Biotecnólogo suele ser la fuente de eso) o su "
            "densidad de valor real — no adivines el producto ni su valor, leelo del informe "
            "correspondiente. No leas todos los informes, solo los relevantes para tu evaluación "
            "de mercado. Nunca inventes un id, usá el que aparece en la lista tal cual."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"documento_id": {"type": "string"}},
            "required": ["documento_id"],
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
                                "densidad_valor_producto": {
                                    "type": "string",
                                    "enum": ["alta", "media", "baja"],
                                    "description": (
                                        "Valor económico por unidad de volumen/peso del producto "
                                        "candidato evaluado — determina si el costo de flete es "
                                        "una restricción real de mercado. Derivarlo de las "
                                        "características reales del producto (ver informes de "
                                        "otros especialistas), nunca asumirlo."
                                    ),
                                },
                                "alcance_geografico_recomendado": {
                                    "type": "string",
                                    "description": (
                                        "Radio de mercado razonable dado el costo de flete vs. la "
                                        "densidad de valor del producto — ej. 'local (radio de "
                                        "flete viable)', 'nacional', 'exportación', o una "
                                        "combinación. Nunca asumido de antemano — justificado con "
                                        "densidad_valor_producto."
                                    ),
                                },
                            },
                            "required": [
                                "valor", "estado", "densidad_valor_producto",
                                "alcance_geografico_recomendado",
                            ],
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
    + """Sos el Agente de Mercado de CRIZA. Tu misión: evaluar si hay una DEMANDA REAL NO RESUELTA para el frente de un caso de biotech agro, y qué tan accesible es ese mercado.

El marco cargado arriba define QUÉ es un blue ocean para CRIZA — las 12 condiciones must, las
2 should, y las 6 maneras en que algo aporta valor. Tu análisis las usa directamente, no las
reinterpreta. En particular: la condición 12 (no sustitución de importación) es la única "sin
excepción" del marco — la declarás siempre en submit_analysis, nunca la omitís.

QUÉ RECIBÍS: el caso/frente completo (contract_input via frente_id — ver build_input_desde_frente)
y, si otros especialistas ya corrieron sobre este frente, la lista de sus informes. Usá
ver_informe_especialista para leer el que identificó el/los producto(s) candidato(s) a evaluar
(normalmente el Biotecnólogo) — no adivines qué producto es ni inventes sus características.

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
¿Qué alcance geográfico tiene sentido? → ver "ALCANCE GEOGRÁFICO DEL MERCADO" abajo, obligatorio.

ALCANCE GEOGRÁFICO DEL MERCADO — nunca asumas de antemano que el mercado es local ni que es de
exportación. Lo derivás de las características reales del producto candidato, caso por caso:
- Identificá el producto candidato leyendo los informes de otros especialistas (ver_informe_especialista)
  — normalmente el Biotecnólogo, a veces el Agrónomo/Ingeniero Ambiental. Si hay varios candidatos,
  evaluá el alcance de cada uno por separado, no un promedio.
- Estimá su DENSIDAD DE VALOR — valor económico por unidad de volumen/peso. Un producto voluminoso
  y de bajo valor por unidad (ej. un gel, un fertilizante diluido, biomasa húmeda) hace que el costo
  de flete sea una restricción real — el mercado alcanzable puede estar limitado a un radio donde el
  flete no se coma el margen. Un producto concentrado de alto valor por unidad (ej. un compuesto
  bioactivo, un principio activo de aplicación en pequeñas dosis) puede justificar un radio mucho
  mayor, incluso exportación.
- Si el input físico del caso está atado a una ubicación fija (una planta, un campo — buscá esto en
  el frente/caso, no lo asumas), esa ubicación es el punto de partida para pensar el radio, no el
  país entero de entrada.
- Declará esto explícitamente en submit_analysis (cruce_4.accesibilidad_mercado.densidad_valor_producto
  y .alcance_geografico_recomendado), con la justificación — nunca lo omitas ni lo asumas sin
  evidencia del producto real que estás evaluando.

WORKFLOW OBLIGATORIO (en orden):
1. Si hay informes de otros especialistas en tu input, leé (ver_informe_especialista) el que
   identifica el/los producto(s) candidato(s) — no arranques el resto sin saber qué estás evaluando.
2. buscar_corpus_cientifico — literatura argentina sobre el problema (corpus_cientifico completo: CONICET+INTA)
3. search_series + get_series_values — tamaño del sector afectado en números
4. search_official_stats — datasets complementarios del sector
5. web_search — descubrir competidores/soluciones/registros reales (Cruce 3 y 4). NO uses tu
   conocimiento de entrenamiento para nombrar competidores — buscalo, es verificable o no lo afirmes.
6. fetch_page_text (hasta 3 páginas) — profundizar en los resultados más relevantes de web_search
7. draft_outreach_email (máximo 2) — solo para gaps críticos irreducibles
8. submit_analysis — SIEMPRE el último paso, aunque falten datos. Incluye obligatoriamente
   sustitucion_importacion, valor_cliente (las 6 dimensiones), fuentes_y_cobertura, y la
   evaluación de alcance geográfico de CRUCE 4.

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
- ver_informe_especialista: leé solo los informes relevantes para identificar el producto y su
  densidad de valor — no leas todos los que aparezcan en la lista.
- submit_analysis es el último paso — siempre llamarlo.
  Un expediente con gaps declarados es mejor que uno que no cierra.
- Emails: siempre PENDIENTE_APROBACION. Nunca decir "vamos a enviar"."""
)


# ── Contrato estándar (SEB-115) ───────────────────────────────────────────────

INPUT_CONTRACT = {
    "agent": "mercado",
    "version": "2.0",
    "fields": {
        "caso": "Recorte/foco de esta invocación (opcional) — no reemplaza al frente/caso, que sale del KM",
        "tarea": "Evaluación de mercado pedida en esta corrida",
        "contexto": "Opcional — contexto adicional de otro agente o de quien invoca",
        "conocimiento": "{'frente_id': str} — modelo de casos.yaml, único camino de invocación (ya no soporta 'oportunidad_id')",
        "herramientas": [
            "buscar_corpus_cientifico", "search_series", "get_series_values",
            "search_official_stats", "web_search", "fetch_page_text",
            "draft_outreach_email", "ver_informe_especialista", "submit_analysis",
        ],
    },
}

OUTPUT_CONTRACT = {
    "agent": "mercado",
    "version": "2.0",
    # Contrato de conexión (2026-07-22, actualizado Etapa 20 2026-09-07 al reconectar a
    # casos.yaml): qué deja este agente en el KM para que otro lo consuma. Lo verifica
    # `check_km_conexion` del auditor contra el código real de ESTE módulo — si la escritura
    # vive en un runner, el camino orquestado no la ejecuta.
    "km_escribe": ["documento_caso conectado al frente vía frente_produce_documento (agente='mercado')"],
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
    elif name == "ver_informe_especialista":
        result = await obtener_documento_por_id(inputs.get("documento_id", ""), tenant=_TENANT)
    else:
        result = {"error": f"Tool desconocida: {name}"}
    return json.dumps(result, ensure_ascii=False, indent=2)


# ── Input builder ─────────────────────────────────────────────────────────────

def build_input_desde_frente(
    frente_dict: dict, caso_dict: dict, pendientes: list[dict],
    documentos_aportados: list[dict] | None = None,
    documentos_producidos: list[dict] | None = None,
) -> str:
    """Construye el input contra el modelo de casos.yaml (frente_id) — mismo patrón que los
    otros 4 especialistas, ver microbiologo_agent.py::build_input_desde_frente.

    `documentos_producidos` es especialmente importante acá (Etapa 20, 2026-09-07): sin ver qué
    producto candidato identificó el Biotecnólogo (u otro especialista), el Agente de Mercado no
    tiene forma de saber QUÉ está evaluando ni su densidad de valor — ver "ALCANCE GEOGRÁFICO DEL
    MERCADO" en el SYSTEM_PROMPT."""
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
            "identifica el producto candidato a evaluar (normalmente del Biotecnólogo) y "
            "cualquier otro relevante. No hace falta leerlos todos."
        )

    if documentos_aportados:
        bloques = "\n\n".join(
            f"## {(d.get('props') or {}).get('titulo', '')}\n\n{(d.get('props') or {}).get('contenido', '')}"
            for d in documentos_aportados
        )
        secciones.append(f"# Documentos aportados por Sebas para este frente\n\n{bloques}")

    secciones.append(
        "---\n"
        "Tu tarea: evaluar demanda, competencia y accesibilidad de mercado (incluido el alcance "
        "geográfico razonable) para el/los producto(s) candidato(s) de este frente. "
        "Llamá submit_analysis cuando tengas suficiente evidencia."
    )

    return "\n\n".join(secciones)


# ── Agentic loop ──────────────────────────────────────────────────────────────

def _bloque_instruccion(
    tarea: str | None, contexto_extra: str | None, foco: str | None = None
) -> str:
    """Instrucción propia de ESTA invocación, para el mensaje de usuario — ver
    microbiologo_agent.py::_bloque_instruccion, mismo patrón.

    Va en el mensaje de usuario y NO en el SYSTEM_PROMPT a propósito: el system prompt
    es lo estable (y lo cacheable); esto es lo que cambia en cada corrida.
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


async def _preflight() -> None:
    preflight = await run_preflight([
        FuenteCheck("corpus_cientifico", bloqueante=True, check_fn=_check_corpus_cientifico),
        FuenteCheck("datos.gob.ar", bloqueante=False, check_fn=_check_datos_gob_ar),
        FuenteCheck("web_search", bloqueante=True, check_fn=_check_web_search),
    ])
    for adv in preflight.advertencias:
        logging.getLogger(__name__).warning(adv)
    if not preflight.ok:
        raise RuntimeError(
            "Pre-flight bloqueante — Agente de Mercado no puede continuar:\n"
            + "\n".join(preflight.bloqueantes)
        )


async def _run_loop(
    identificador: str,
    system_blocks: list[dict],
    user_message: str,
    model: str,
    verbose: bool,
) -> tuple[str, dict, list[str], TokenTracker]:
    """Loop agéntico de la corrida formal (termina en submit_analysis) — usa el cliente nativo
    de Anthropic (excepción permanente, ver docstring del módulo), no `utils.ai_client`. No
    persiste nada al KM, eso lo hace la costura (orquestador/invocador.py)."""
    tracker = TokenTracker(agent=_AGENTE, oportunidad_id=identificador, model=model)
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

    # 4. Extraer resultado — no persiste nada al KM, eso lo hace la costura
    #    (orquestador/invocador.py::invocar_agente) vía el documento_caso que arma con lo que
    #    devuelve run(). El caller (run_agent_desde_frente) persiste token_usage en el frente.
    tracker.log(verbose)

    if not analysis_result:
        # getattr(b, "text", None), no hasattr: bloques nativos de Anthropic distintos de texto
        # (ej. server_tool_use, web_search_tool_result — reales cuando el modelo usó web_search
        # en el último turno sin llamar submit_analysis) SÍ tienen atributo `text`, pero en None
        # — hasattr(b, "text") da True igual y "".join() revienta con TypeError (encontrado real,
        # 2026-09-07, verificando el chat contra Helios).
        resumen = next(
            (b.text for b in response.content if getattr(b, "text", None)),
            "Análisis incompleto — el agente no llamó submit_analysis.",
        )
        return resumen, {}, [], tracker

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

    return resumen_markdown, cruces_dict, lecciones_auto, tracker


async def run_agent_desde_frente(
    frente_id: str,
    verbose: bool = False,
    model: str = DEFAULT_MODEL,
    tarea: str | None = None,
    contexto_extra: str | None = None,
    foco: str | None = None,
) -> tuple[str, dict, list[str]]:
    """
    Corre el Agente de Mercado contra un frente del modelo de casos.yaml — único camino de
    invocación (Etapa 20, 2026-09-07 — ver docs/DESIGN_GATE.md decisión L, ya no soporta
    oportunidad_id).

    Returns:
        (resumen_markdown, cruces_dict, lecciones_caso)
        No escribe al KM — eso lo hace la costura (orquestador/invocador.py::invocar_agente),
        que persiste un documento_caso conectado vía frente_produce_documento.
    """
    if verbose:
        print(f"\n{'='*60}\n  AGENTE DE MERCADO — CRIZA (frente)\n  Modelo: {model}\n{'='*60}\n")

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
    # Prompt caching (2026-07-22): el loop agéntico reenvía el mismo system+tools en cada
    # vuelta — sin esto, el prefijo completo se factura a precio pleno todas las veces.
    system_blocks = [{
        "type": "text",
        "text": SYSTEM_PROMPT + bloque,
        "cache_control": {"type": "ephemeral"},
    }]
    user_message = build_input_desde_frente(
        frente_dict, caso_dict, pendientes, documentos_aportados, documentos_producidos
    ) + _bloque_instruccion(tarea, contexto_extra, foco)

    resumen_markdown, cruces_dict, lecciones_auto, tracker = await _run_loop(
        frente_id, system_blocks, user_message, model, verbose
    )

    existing_tu = (frente_dict.get("props") or {}).get("token_usage") or {}
    existing_tu[_AGENTE] = tracker.to_dict()
    await motor_api.actualizar_props(frente_id, {"token_usage": existing_tu}, tenant=_TENANT)

    return resumen_markdown, cruces_dict, lecciones_auto


# ── Chat conversacional (mismo patrón que los otros 4 especialistas) ───────────
#
# Distinto de run()/run_agent_desde_frente() (contrato SEB-115, un turno, termina en
# submit_analysis, la costura persiste un documento_caso) — esto es para que Sebas pueda
# CONVERSAR con el Agente de Mercado sin que cada intercambio dispare un análisis formal.
# TOOLS_CHAT excluye submit_analysis a propósito.

TOOLS_CHAT = [t for t in TOOLS if t.get("name") != "submit_analysis"]


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
    Un turno de chat con el Agente de Mercado. `messages` se muta y se devuelve, mismo patrón
    que `conductor.enviar_mensaje()`. Usa el cliente nativo de Anthropic (excepción permanente
    del módulo), no `utils.ai_client` — TOOLS_CHAT incluye la tool nativa `web_search`.

    `frente_id=None` es el modo "consulta libre" — Sebas puede preguntarle algo puntual sin
    necesitar un caso/frente ya creado.
    """
    messages.append({"role": "user", "content": texto_usuario})
    tracker = tracker or TokenTracker(agent=_AGENTE, oportunidad_id=frente_id or "", model=model)

    await aprendizaje.ensure_area(tenant=tenant)
    if frente_id:
        contexto = await obtener_frente_con_caso(frente_id, tenant=tenant)
        caso_dict = contexto["caso"] or {}
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
            # getattr(b, "text", None), no hasattr — ver comentario en _run_loop, mismo bug real.
            texto = "".join(b.text for b in response.content if getattr(b, "text", None))
            return texto, messages

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            if verbose:
                print(f"  -> {block.name}({block.input})")
            result_str = await _dispatch(block.name, block.input)
            tool_results.append({
                "type": "tool_result", "tool_use_id": block.id,
                "content": result_str,
            })

        messages.append({"role": "user", "content": tool_results})


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
    """Interfaz de contrato estándar para el Orquestador (SEB-115). Solo acepta frente_id — ver
    INPUT_CONTRACT (Etapa 20, 2026-09-07 — ya no soporta oportunidad_id)."""
    conocimiento = contract_input.get("conocimiento") or {}
    frente_id = conocimiento.get("frente_id") if isinstance(conocimiento, dict) else None
    oportunidad_id = conocimiento.get("oportunidad_id") if isinstance(conocimiento, dict) else None

    if oportunidad_id:
        raise ValueError("Agente de Mercado solo acepta 'frente_id' en contract_input['conocimiento'] — no soporta 'oportunidad_id'")
    if not frente_id:
        raise ValueError("Agente de Mercado requiere 'frente_id' en contract_input['conocimiento']")

    resumen, cruces, lecciones = await run_agent_desde_frente(
        frente_id,
        verbose=verbose,
        model=model,
        tarea=contract_input.get("tarea") or None,
        contexto_extra=contract_input.get("contexto") or None,
        foco=contract_input.get("caso") or None,
    )

    return {
        # `análisis` es exactamente lo que la costura persiste en el documento_caso — por eso
        # incluye `informe_completo`, no un campo `resumen` aparte (ver invocador.py).
        "análisis": {**cruces, "informe_completo": resumen},
        "nivel_confianza": _derive_confidence(cruces),
        "recomendaciones": cruces.get("gaps_prioritarios", []),
        "próximo_agente": None,
        "nuevo_conocimiento": lecciones,
    }
