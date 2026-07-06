"""
Evidence Generalista — CRIZA

Evalúa si existe —o puede crearse— una solución técnica para el dolor que
el agente de mercado ya caracterizó. Technology-agnostic: no asume qué
tecnología resuelve el problema. Llena el cruce 2 del expediente de
decisión a nivel de screening.

Tools: search_literature (OpenAlex), buscar_corpus_cientifico (CONICET+INTA),
       search_corpus_inta (INTA legacy, exhaustivo), expand_agrovoc, submit_evidencia.
Ver docs/DESIGN_GATE.md — decisiones A–D (2026-06-16).
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
_KM_PATH = _CRIZA_DIR.parent / "knowledge_module"
sys.path.insert(0, str(_KM_PATH))
sys.path.insert(0, str(_CRIZA_DIR))
sys.path.insert(0, str(_AGENT_DIR))

from utils.openalex import search_literature as _search_literature_fn
from tools.search import get_sector_corpus as _get_sector_corpus_fn
from utils.agrovoc import expand_term as _expand_agrovoc_fn
from utils.corpus import buscar_corpus_cientifico as _buscar_corpus_cientifico_fn
from motor import api as motor_api
import aprendizaje
from utils.token_tracker import TokenTracker
from preflight import FuenteCheck, FuenteCheckResult, run_preflight
from db import get_session_factory
from sqlalchemy import text as _sql_text

DEFAULT_MODEL = os.getenv("EVIDENCE_MODEL", "claude-sonnet-4-6")
_AGENTE = "evidencia"
_TENANT = "criza"

# Documento compartido — cargado en runtime, mismo patrón que investigacion_amplia/armador.
_MARCO = (_CRIZA_DIR / "docs" / "marco_blue_ocean_CRIZA.md").read_text(encoding="utf-8")


async def _search_inta_fn(query: str, tipo: str | None = None, limit: int = 1000, tenant_id: str = "criza") -> dict:
    """
    Busca en el corpus INTA de forma exhaustiva — OR sobre los términos de `query`, vía
    get_sector_corpus (la misma fuente exhaustiva que usa investigacion_amplia), en vez de
    mantener un segundo camino de búsqueda más débil (search_fuentes_externas, FTS con LIMIT
    chico) sobre la misma tabla. `limit` ya no acota la consulta — solo trunca el resultado si
    se pide explícitamente un número menor al total real (política: fuentes propias exhaustivas
    por default, cap declarado nunca en silencio — orchestration-layer.md Decisión 6).
    """
    terminos = [t for t in query.split() if len(t) > 2]
    if not terminos:
        return {"success": False, "data": None, "error": "Sin términos válidos para la búsqueda"}

    resultado = await _get_sector_corpus_fn(terminos, tenant_id=tenant_id)
    if not resultado.get("success"):
        return resultado

    documentos = resultado["data"]["documentos"]
    if tipo:
        documentos = [d for d in documentos if d.get("tipo") == tipo]
    if limit:
        documentos = documentos[:limit]

    return {
        "success": True,
        "data": {"query": query, "total": len(documentos), "results": documentos},
    }


# ── Pre-flight check ──────────────────────────────────────────────────────────

async def _check_inta_corpus() -> FuenteCheckResult:
    """INTA corpus (tabla documento, FTS exhaustivo) — fuente que controlamos, bloqueante."""
    async with get_session_factory()() as s:
        r = await s.execute(_sql_text(
            "SELECT COUNT(*) FROM documento WHERE tenant_id = :t AND agente IN ('harvest', 'ingest')"
        ), {"t": _TENANT})
        total = r.scalar() or 0
    return FuenteCheckResult(ok=total > 0, detalle=f"{total} documentos", conteo=total)


async def _check_corpus_cientifico() -> FuenteCheckResult:
    """corpus_cientifico — CONICET+INTA vía el motor nuevo. Fuente que controlamos, bloqueante."""
    async with get_session_factory()() as s:
        r = await s.execute(_sql_text(
            "SELECT COUNT(*) FROM ficha f "
            "JOIN tipo_ficha tf ON tf.id = f.tipo_ficha_id "
            "JOIN area a ON a.id = tf.area_id "
            "WHERE a.nombre = 'corpus_cientifico' AND a.tenant_id = :t"
        ), {"t": _TENANT})
        total = r.scalar() or 0
    return FuenteCheckResult(ok=total > 0, detalle=f"{total} fichas", conteo=total)


async def _check_openalex() -> FuenteCheckResult:
    """OpenAlex — externo, no bloqueante (puede estar caído sin que sea nuestro error)."""
    try:
        test = _search_literature_fn("biotechnology enzyme Argentina", max_results=1)
        if isinstance(test, dict) and test.get("error"):
            return FuenteCheckResult(ok=False, detalle=str(test["error"])[:120])
        return FuenteCheckResult(ok=True, detalle="reachable")
    except Exception as exc:
        return FuenteCheckResult(ok=False, detalle=str(exc)[:120])


# ── Tool definitions ──────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "search_literature",
        "description": (
            "Busca en literatura científica via OpenAlex (250M+ papers).\n"
            "Usar para: evaluar si existe base científica para resolver un dolor dado,\n"
            "entender madurez de la solución, identificar brechas y alternativas existentes.\n"
            "Buscás evidencia de qué puede hacerse —mecanismo, propiedad, resultado—,\n"
            "no qué herramienta usar. Siempre en inglés. max_results=10 por defecto."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Búsqueda en inglés, focalizada en el mecanismo o propiedad buscada."
                },
                "max_results": {
                    "type": "integer",
                    "description": "Número de resultados (5-15 recomendado).",
                    "default": 10
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "expand_agrovoc",
        "description": (
            "Expande un término de búsqueda contra el tesauro AGROVOC de la FAO.\n"
            "Retorna el prefLabel en español e inglés, términos más amplios (broader),\n"
            "más específicos (narrower) y relacionados (related).\n"
            "Usar ANTES de search_corpus_inta cuando:\n"
            "  1) El término está en inglés y querés buscar en el corpus INTA (español).\n"
            "  2) Necesitás los términos AGROVOC exactos que INTA usa para indexar.\n"
            "  3) Querés enriquecer la búsqueda con narrower (más específico) o related.\n"
            "NO usar para OpenAlex (search_literature) — está en inglés y no necesita AGROVOC."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "term": {
                    "type": "string",
                    "description": (
                        "Término a expandir. Puede ser en español o inglés. "
                        "AGROVOC busca primero en ES, luego fallback a EN."
                    )
                }
            },
            "required": ["term"]
        }
    },
    {
        "name": "search_corpus_inta",
        "description": (
            "Busca en el corpus de papers INTA Digital cosechados localmente (1.600+ trabajos de CICVyA).\n"
            "Áreas cubiertas: biotecnología agropecuaria, virología, patobiología animal,\n"
            "sanidad vegetal, inocuidad alimentaria, genómica aplicada.\n"
            "Usar cuando el dolor sea en agropecuaria argentina: garrapata, sanidad bovina,\n"
            "aftosa, brucelosis, soja, maíz, enfermedades regionales.\n"
            "Complementa search_literature (OpenAlex global) con literatura local específica.\n"
            "Soporta español e inglés. Operadores: 'garrapata biocontrol', 'virus AND vacuna'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Texto libre en español o inglés."
                },
                "tipo": {
                    "type": "string",
                    "description": "Filtrar por tipo de documento.",
                    "enum": ["paper", "reporte", "norma", "patente", "otro",
                             "tesis", "ponencia", "libro", "parte_libro", "divulgacion", "folleto"]
                },
                "limit": {
                    "type": "integer",
                    "description": "Máximo de resultados (default 1000 — búsqueda exhaustiva, no muestrea; bajalo solo si querés acotar explícitamente).",
                    "default": 1000
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "buscar_corpus_cientifico",
        "description": (
            "Busca por similitud semántica en corpus_cientifico — CONICET (625 fichas, repositorios\n"
            "argentinos vía OAI-PMH) + INTA (vía el motor nuevo, complementa search_corpus_inta que\n"
            "usa la tabla legacy). Es la ÚNICA fuente de literatura científica argentina con papers\n"
            "de CONICET — sin este tool el agente no tiene ningún acceso a CONICET.\n"
            "Usar para: literatura académica argentina sobre el mecanismo/propiedad buscado,\n"
            "sin acotar a agropecuario (CONICET cubre todas las disciplinas).\n"
            "Complementa search_literature (OpenAlex global) y search_corpus_inta (INTA agropecuario)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "consulta": {
                    "type": "string",
                    "description": "Términos a buscar — mecanismo, propiedad o resultado buscado. ES o EN."
                },
                "limit": {
                    "type": "integer",
                    "description": "Máximo de papers (default 100 — corpus_cientifico completo, no muestrear).",
                    "default": 100
                }
            },
            "required": ["consulta"]
        }
    },
    {
        "name": "submit_evidencia",
        "description": (
            "ÚNICO output del agente. Llamar cuando tengas suficiente evidencia para responder:\n"
            "¿Existe base científica para resolver este dolor? ¿Qué tan madura está?\n"
            "¿Necesita análisis especializado adicional?\n"
            "No esperes tener certeza total — declarar estado epistémico es suficiente."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "cruce_2": {
                    "type": "object",
                    "description": "Análisis estructurado de factibilidad técnica.",
                    "properties": {
                        "solucion_propuesta": {
                            "type": "object",
                            "description": "Qué podría resolver el dolor. Puede no existir aún — eso también es un hallazgo.",
                            "properties": {
                                "valor":  {"type": "string"},
                                "estado": {"type": "string", "enum": ["establecido", "asumido", "a-confirmar"]},
                                "fuente": {"type": "string"}
                            },
                            "required": ["valor", "estado"]
                        },
                        "estado_cientifico": {
                            "type": "object",
                            "description": "Madurez de la base científica detrás de la solución.",
                            "properties": {
                                "valor":        {"type": "string", "enum": ["maduro", "emergente", "experimental", "conceptual"]},
                                "justificacion": {"type": "string"},
                                "estado":       {"type": "string", "enum": ["establecido", "asumido", "a-confirmar"]},
                                "fuente":       {"type": "string"}
                            },
                            "required": ["valor", "justificacion", "estado"]
                        },
                        "factibilidad_produccion": {
                            "type": "object",
                            "description": "¿Puede producirse? Describí en términos de capacidades, sin nombrar tecnologías.",
                            "properties": {
                                "valor":        {"type": "string", "enum": ["propia", "socio", "hibrida", "a-confirmar"]},
                                "que_requiere": {"type": "string"},
                                "estado":       {"type": "string", "enum": ["establecido", "asumido", "a-confirmar"]}
                            },
                            "required": ["valor", "que_requiere", "estado"]
                        },
                        "ventaja_vs_incumbente": {
                            "type": "object",
                            "description": "¿Qué aportaría vs. las alternativas existentes?",
                            "properties": {
                                "valor":  {"type": "string"},
                                "estado": {"type": "string", "enum": ["establecido", "asumido", "a-confirmar"]},
                                "fuente": {"type": "string"}
                            },
                            "required": ["valor", "estado"]
                        },
                        "brechas_tecnicas": {
                            "type": "array",
                            "description": "Obstáculos técnicos que quedan sin resolver.",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "brecha":               {"type": "string"},
                                    "impacto_en_decision":  {"type": "string", "enum": ["alto", "medio", "bajo"]},
                                    "donde_confirmar":      {"type": "string"}
                                },
                                "required": ["brecha", "impacto_en_decision"]
                            }
                        },
                        "evidencia": {
                            "type": "object",
                            "properties": {
                                "fuentes": {"type": "array", "items": {"type": "string"}},
                                "estado":  {"type": "string", "enum": ["establecido", "asumido", "a-confirmar"]}
                            },
                            "required": ["fuentes", "estado"]
                        }
                    },
                    "required": [
                        "solucion_propuesta", "estado_cientifico", "factibilidad_produccion",
                        "ventaja_vs_incumbente", "brechas_tecnicas", "evidencia"
                    ]
                },
                "especialista_recomendado": {
                    "type": "object",
                    "description": "¿Se necesita análisis especializado más profundo?",
                    "properties": {
                        "si_no":      {"type": "boolean"},
                        "descripcion": {
                            "type": "string",
                            "description": (
                                "Qué análisis adicional aportaría valor. "
                                "Texto libre describiendo QUÉ se necesita evaluar, "
                                "sin nombrar tecnologías específicas."
                            )
                        },
                        "razon": {
                            "type": "string",
                            "description": "Por qué el análisis de literatura no es suficiente para este caso."
                        }
                    },
                    "required": ["si_no"]
                },
                "informe_completo": {
                    "type": "string",
                    "description": (
                        "Narrative completa del análisis en markdown. "
                        "Incluir: preguntas técnicas identificadas, búsquedas realizadas, "
                        "papers clave revisados, razonamiento, conclusiones. Mínimo 3 secciones."
                    )
                },
                "fuentes_y_cobertura": {
                    "type": "object",
                    "description": "Qué fuentes se consultaron y con qué cobertura — obligatorio (orchestration-layer.md Decisión 6). Declarar corpus_cientifico (CONICET+INTA), INTA corpus (legacy) y OpenAlex como mínimo.",
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
                "lecciones_caso": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lecciones para el loop de aprendizaje."
                }
            },
            "required": ["cruce_2", "especialista_recomendado", "informe_completo", "fuentes_y_cobertura"]
        }
    }
]


# ── System prompt ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    _MARCO
    + "\n\n---\n\n"
    + """Sos el Evidence Generalista de CRIZA.

El marco cargado arriba define QUÉ es un blue ocean para CRIZA. Tu trabajo (cruce 2 — factibilidad
técnica) es un insumo para evaluarlo, no una evaluación de mercado en sí — no le apliques las
condiciones de demanda/competencia (eso es del Agente de Mercado), pero sí el principio central:
la tecnología es una variable, nunca el punto de partida del análisis.

TU OBJETIVO: Evaluar si existe —o puede crearse— una solución técnica para el dolor que el agente de mercado ya caracterizó. No buscás productos existentes: buscás si la ciencia respalda la posibilidad.

PRINCIPIO FUNDAMENTAL: La tecnología es una variable, no un punto de partida. No asumas qué tecnología resuelve el problema. Buscá en literatura lo que la evidencia muestra, y describí la solución en términos de qué hace (mecanismo, propiedad, resultado), nunca en términos de qué tecnología usa. El dolor puede no tener solución conocida aún — eso también es un hallazgo válido.

QUÉ RECIBÍS:
- Descripción del dolor (quién lo sufre, qué impacto tiene)
- Contexto de demanda del agente de mercado (cruce 1: dolor caracterizado)

FUENTES DISPONIBLES:
- search_literature: Literatura científica global (OpenAlex, 250M+ papers). Buscar en inglés.
- buscar_corpus_cientifico: corpus_cientifico local — CONICET (625 fichas, todas las disciplinas) +
  INTA vía el motor nuevo. ÚNICA fuente con literatura de CONICET — usarla siempre, no solo para
  agropecuario. Búsqueda semántica, ES o EN.
- search_corpus_inta: Corpus INTA Digital local (1.600+ papers de CICVyA, tabla legacy con FTS
  exhaustivo). Buscar en español o inglés. Usar para dolores en agropecuaria argentina — garrapata,
  sanidad animal, cultivos regionales. Complementa buscar_corpus_cientifico con cobertura exhaustiva
  (no top-N) sobre INTA específicamente.
- expand_agrovoc: Expande un término contra el tesauro AGROVOC (FAO). Retorna prefLabel ES/EN + broader/narrower/related. Usar antes de search_corpus_inta cuando tenés un término en inglés para buscar en el corpus español de INTA.
Combinar las tres fuentes propias cuando el dolor sea agropecuario argentino. Flujo sugerido:
buscar_corpus_cientifico (CONICET+INTA, cualquier dolor) → expand_agrovoc → search_corpus_inta con
términos ES si es agropecuario → search_literature con términos EN para contexto global.

TU PROCESO:
1. Identificá la pregunta técnica central que el dolor plantea
2. Buscá en literatura científica (3-5 búsquedas en total, usando la fuente más apropiada) —
   incluí siempre buscar_corpus_cientifico, es la única fuente con literatura de CONICET
3. Evaluá: ¿hay base científica para resolver el dolor? ¿qué tan madura?
4. Identificá las brechas técnicas que explican por qué la solución no existe o no está adoptada
5. Decidí si un análisis especializado más profundo aportaría valor que vos no podés dar
6. Llamá submit_evidencia con el análisis estructurado

CUÁNDO CERRAR: Cuando tengas suficiente evidencia para evaluar la madurez y las brechas principales. No acumulés papers si ya podés responder la pregunta central.

VERACIDAD POR DATO:
- establecido: lo dice la fuente, citás doi o paper
- asumido: inferencia razonable, aclarás el peso
- a-confirmar: gap real, aclarás dónde verificar

SOBRE BRECHAS: Las razones por las que la solución no existe o no está masificada definen si la oportunidad es real. Buscalas explícitamente.

Al llamar submit_evidencia, declará siempre fuentes_y_cobertura: qué fuentes consultaste
(search_literature, buscar_corpus_cientifico, search_corpus_inta), cuántos resultados procesaste
de cada una, y si alguna no estuvo disponible.
"""
)


# ── Contrato estándar (SEB-115) ───────────────────────────────────────────────

INPUT_CONTRACT = {
    "agent": "evidencia",
    "version": "1.2",
    "fields": {
        "caso": "Descripción del dolor (puede omitirse si se pasa oportunidad_id)",
        "tarea": "Evaluar factibilidad técnica — llenar cruce 2 del expediente de decisión",
        "contexto": "Opcional — cruce_1 del agente de mercado para orientar la búsqueda",
        "conocimiento": "{'oportunidad_id': str} — requerido para leer el KM y persistir resultados",
        "herramientas": ["search_literature", "buscar_corpus_cientifico", "expand_agrovoc", "search_corpus_inta", "submit_evidencia"],
    },
}

OUTPUT_CONTRACT = {
    "agent": "evidencia",
    "version": "1.2",
    "fields": {
        "análisis": "{'informe': str, 'evidencia': {'cruce_2': dict, 'especialista_recomendado': dict, 'fuentes_y_cobertura': dict, ...}}",
        "nivel_confianza": "'alto' | 'medio' | 'bajo' — basado en estado_cientifico y brechas de alto impacto",
        "recomendaciones": "brechas_tecnicas de impacto alto — obstáculos técnicos sin resolver",
        "próximo_agente": "'cientifico_especialista' si especialista_recomendado.si_no=True, else None",
        "nuevo_conocimiento": "lecciones_caso — aprendizajes de dominio para el loop de aprendizaje",
    },
}


# ── Input builder ─────────────────────────────────────────────────────────────

def build_input(oportunidad_id: str, oportunidad_dict: dict) -> str:
    props = oportunidad_dict.get("props") or {}
    nombre = oportunidad_dict.get("nombre") or props.get("nombre") or oportunidad_id
    descripcion = props.get("descripcion") or ""

    mercado = props.get("mercado") or {}
    cruce_1 = mercado.get("cruce_1") or {}
    mercado_informe = mercado.get("informe_completo", "")

    secciones = [
        f"# Oportunidad\n\n**ID:** {oportunidad_id}\n**Nombre:** {nombre}\n\n{descripcion}",
    ]

    if cruce_1:
        secciones.append(
            "## Dolor caracterizado por el Agente de Mercado (Cruce 1)\n\n"
            f"```json\n{json.dumps(cruce_1, ensure_ascii=False, indent=2)}\n```"
        )
    elif mercado_informe:
        secciones.append(f"## Análisis de Mercado\n\n{mercado_informe}")
    elif mercado:
        mercado_display = {k: v for k, v in mercado.items() if k != "informe_completo"}
        secciones.append(
            f"## Datos del Agente de Mercado\n\n"
            f"```json\n{json.dumps(mercado_display, ensure_ascii=False, indent=2)}\n```"
        )

    secciones.append(
        "---\n"
        "Tu tarea: evaluar la factibilidad técnica de crear una solución para este dolor. "
        "Llamá submit_evidencia cuando tengas suficiente evidencia para responder la pregunta central."
    )

    return "\n\n".join(secciones)


# ── Agentic loop ──────────────────────────────────────────────────────────────

async def run_agent(
    oportunidad_id: str,
    verbose: bool = False,
    model: str = DEFAULT_MODEL,
) -> tuple[str, dict, list[str]]:
    """
    Corre el Evidence Generalista.

    Args:
        oportunidad_id: UUID de la oportunidad en el KM.
        verbose: Imprime tool calls en tiempo real.
        model: Modelo Claude a usar.

    Returns:
        (informe_markdown, evidencia_dict, lecciones_caso)
        Side effect: escribe props.evidencia en el KM.
    """
    client = anthropic.Anthropic()

    if verbose:
        print(f"\n{'='*60}\n  EVIDENCE GENERALISTA — CRIZA\n  Modelo: {model}\n{'='*60}\n")

    oportunidad_dict = await motor_api.obtener(oportunidad_id, tenant=_TENANT)
    if not oportunidad_dict:
        raise ValueError(f"Oportunidad {oportunidad_id} no encontrada en el KM")

    # Pre-flight: verificar fuentes críticas antes de arrancar el loop agéntico
    # (objective-first — si lo que controlamos no está listo, frenamos).
    preflight = await run_preflight([
        FuenteCheck("INTA corpus", bloqueante=True, check_fn=_check_inta_corpus),
        FuenteCheck("corpus_cientifico (CONICET+INTA)", bloqueante=True, check_fn=_check_corpus_cientifico),
        FuenteCheck("OpenAlex", bloqueante=False, check_fn=_check_openalex),
    ])
    if verbose:
        for adv in preflight.advertencias:
            print(f"  ⚠️  {adv}")
    if not preflight.ok:
        raise RuntimeError(
            "Pre-flight bloqueante — Evidence Generalista no puede continuar:\n"
            + "\n".join(preflight.bloqueantes)
        )

    tracker = TokenTracker(agent=_AGENTE, oportunidad_id=oportunidad_id, model=model)

    await aprendizaje.ensure_area(tenant=_TENANT)
    bloque = await aprendizaje.bloque_lecciones_para_prompt(
        agente=_AGENTE,
        consulta=(oportunidad_dict.get("props") or {}).get("descripcion") or oportunidad_id,
        tenant=_TENANT,
    )
    effective_system = SYSTEM_PROMPT + bloque

    user_input = build_input(oportunidad_id, oportunidad_dict)
    messages = [{"role": "user", "content": user_input}]
    evidencia_result = None

    while True:
        for attempt in range(4):
            try:
                response = client.messages.create(
                    model=model,
                    max_tokens=16000,
                    system=effective_system,
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

        if verbose:
            print(
                f"  [{tracker.calls}] stop={response.stop_reason} | "
                f"tokens in={response.usage.input_tokens} out={response.usage.output_tokens}"
            )

        if response.stop_reason in ("end_turn", "max_tokens"):
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                if block.name == "submit_evidencia":
                    evidencia_result = block.input
                    if verbose:
                        print("  -> submit_evidencia [capturado]\n")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps({"success": True, "message": "Evidencia registrada."}),
                    })
                elif block.name == "expand_agrovoc":
                    term = block.input.get("term", "")
                    if verbose:
                        print(f"  -> expand_agrovoc: {term[:60]}")
                    try:
                        expanded = _expand_agrovoc_fn(term)
                        content = json.dumps(expanded, ensure_ascii=False, indent=2) if expanded else json.dumps({"found": False, "term": term})
                    except Exception as exc:
                        content = json.dumps({"error": str(exc), "term": term})
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": content,
                    })
                elif block.name == "search_corpus_inta":
                    query = block.input.get("query", "")
                    if verbose:
                        print(f"  -> search_corpus_inta: {query[:80]}")
                    result = await _search_inta_fn(
                        query=query,
                        tipo=block.input.get("tipo"),
                        limit=block.input.get("limit", 1000),
                        tenant_id=_TENANT,
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False, indent=2),
                    })
                elif block.name == "search_literature":
                    query = block.input.get("query", "")
                    if verbose:
                        print(f"  -> search_literature: {query[:80]}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(
                            _search_literature_fn(
                                query=query,
                                max_results=block.input.get("max_results", 10),
                            ),
                            ensure_ascii=False,
                            indent=2,
                        ),
                    })
                elif block.name == "buscar_corpus_cientifico":
                    consulta = block.input.get("consulta", "")
                    if verbose:
                        print(f"  -> buscar_corpus_cientifico: {consulta[:80]}")
                    result = await _buscar_corpus_cientifico_fn(
                        consulta=consulta,
                        limit=block.input.get("limit", 100),
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False, indent=2),
                    })
                else:
                    if verbose:
                        print(f"  -> [tool desconocido: {block.name}]")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps({"error": f"Tool '{block.name}' no implementado."}),
                    })

            messages.append({"role": "user", "content": tool_results})

            if evidencia_result:
                break
        else:
            break

    # Persistir tokens
    tracker.log(verbose)
    existing_tu = (oportunidad_dict.get("props") or {}).get("token_usage") or {}
    existing_tu[_AGENTE] = tracker.to_dict()
    await motor_api.actualizar_props(oportunidad_id, {"token_usage": existing_tu}, tenant=_TENANT)

    if evidencia_result is None:
        raw = "".join(b.text for b in response.content if hasattr(b, "text"))
        return raw or "El agente no llamó submit_evidencia.", {}, []

    informe = evidencia_result.get("informe_completo", "")
    cruce_2 = evidencia_result.get("cruce_2", {})
    especialista = evidencia_result.get("especialista_recomendado", {"si_no": False})
    lecciones_auto = evidencia_result.get("lecciones_caso") or []
    fuentes_y_cobertura = evidencia_result.get("fuentes_y_cobertura") or {
        "fuentes_consultadas": [],
        "cobertura_declarada": "parcial-por-falla-de-fuente",
    }

    evidencia_dict = {
        "cruce_2": cruce_2,
        "especialista_recomendado": especialista,
        "fuentes_y_cobertura": fuentes_y_cobertura,
        "agente": _AGENTE,
        "fecha": date.today().isoformat(),
        "modelo": model,
        "informe_completo": informe,
    }

    await motor_api.actualizar_props(oportunidad_id, {"evidencia": evidencia_dict}, tenant=_TENANT)

    if verbose:
        recomienda = especialista.get("si_no", False)
        estado = cruce_2.get("estado_cientifico", {}).get("valor", "?")
        print(f"\n  KM actualizado — estado científico: {estado}")
        if recomienda:
            print(f"  Especialista recomendado: {especialista.get('descripcion', '')[:100]}")
        else:
            print("  Sin especialista recomendado.")

    return informe, evidencia_dict, lecciones_auto


# ── Interfaz de contrato estándar (SEB-115) ───────────────────────────────────

def _derive_confidence(evidencia: dict) -> str:
    cruce_2 = evidencia.get("cruce_2") or {}
    estado = (cruce_2.get("estado_cientifico") or {}).get("estado", "a-confirmar")
    brechas_altas = [
        b for b in (cruce_2.get("brechas_tecnicas") or [])
        if b.get("impacto_en_decision") == "alto"
    ]
    if estado == "establecido" and not brechas_altas:
        return "alto"
    if estado in ("establecido", "asumido") and len(brechas_altas) <= 1:
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
    if not oportunidad_id:
        raise ValueError("Evidence Generalista requiere 'oportunidad_id' en contract_input['conocimiento']")

    informe, evidencia, lecciones = await run_agent(oportunidad_id, verbose=verbose, model=model)

    cruce_2 = evidencia.get("cruce_2") or {}
    brechas_altas = [
        b["brecha"]
        for b in (cruce_2.get("brechas_tecnicas") or [])
        if b.get("impacto_en_decision") == "alto"
    ]
    especialista = evidencia.get("especialista_recomendado") or {}

    return {
        "análisis": {"informe": informe, "evidencia": evidencia},
        "nivel_confianza": _derive_confidence(evidencia),
        "recomendaciones": brechas_altas,
        "próximo_agente": "cientifico_especialista" if especialista.get("si_no") else None,
        "nuevo_conocimiento": lecciones,
    }
