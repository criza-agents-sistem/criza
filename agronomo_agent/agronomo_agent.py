"""
Especialista Ingeniero Agrónomo — CRIZA

Evalúa el USO AGRONÓMICO de un producto/enfoque ya identificado por otro especialista: ¿sirve de
verdad como insumo agrícola/ganadero? Dosis, compatibilidad de cultivo/suelo, manejo en campo,
marco normativo de aplicación. Distinto del Microbiólogo (madurez biológica/química) y del
Ingeniero Ambiental (factibilidad de ingeniería de planta) — este especialista responde "¿esto
funciona como insumo en producción real?", no "¿es biológicamente viable?" ni "¿se puede
construir?".

Tercer especialista de la "biblioteca de especialistas" (docs/PROPUESTA_DESTINO.md §5) —
construido con señal real explícita de Sebas (no en abstracto, ver docs/DESIGN_GATE.md decisión
A): Helios necesita destino para su efluente, el sector agropecuario es un destino probable.

Tools: search_literature, buscar_corpus_cientifico, search_corpus_inta, expand_agrovoc (las 4
genéricas de corpus, mismo patrón que Microbiólogo/Ingeniero Ambiental), submit_evaluacion_tecnica
(mismo schema exacto que los otros dos especialistas).

Solo soporta invocación vía `frente_id` (modelo casos.yaml) — no `oportunidad_id` (mismo criterio
que ingeniero_ambiental_agent, ver docs/DESIGN_GATE.md decisión A).

El input entra SOLO por contract_input (caso/tarea/contexto) — el SYSTEM_PROMPT no menciona
ningún caso concreto, a propósito (mismo checklist anti-sesgo que los otros especialistas).
"""

import json
import logging
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

_AGENT_DIR = Path(__file__).parent
_CRIZA_DIR = _AGENT_DIR.parent
sys.path.insert(0, str(_CRIZA_DIR))
sys.path.insert(0, str(_AGENT_DIR))

from utils.ai_client import complete as _ai_complete, resolver_modelo as _resolver_modelo
from utils.openalex import search_literature as _search_literature_fn
from km_tools.search import get_sector_corpus as _get_sector_corpus_fn
from utils.agrovoc import expand_term as _expand_agrovoc_fn
from utils.corpus import buscar_corpus_cientifico as _buscar_corpus_cientifico_fn
from utils.casos import obtener_frente_con_caso, obtener_pendientes_de_caso
from knowledge_module.motor import api as motor_api
import knowledge_module.aprendizaje as aprendizaje
from utils.token_tracker import TokenTracker
from knowledge_module.preflight import FuenteCheck, FuenteCheckResult, run_preflight
from knowledge_module.db import get_session_factory
from sqlalchemy import text as _sql_text

DEFAULT_MODEL = os.getenv("AGRONOMO_MODEL", "claude-sonnet-4-6")
_AGENTE = "agronomo"
_TENANT = "criza"


async def _search_inta_fn(query: str, tipo: str | None = None, limit: int = 1000, tenant_id: str = "criza") -> dict:
    """Búsqueda exhaustiva sobre el corpus INTA — mismo patrón que los otros especialistas."""
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
    async with get_session_factory()() as s:
        r = await s.execute(_sql_text(
            "SELECT COUNT(*) FROM documento WHERE tenant_id = :t AND agente IN ('harvest', 'ingest')"
        ), {"t": _TENANT})
        total = r.scalar() or 0
    return FuenteCheckResult(ok=total > 0, detalle=f"{total} documentos", conteo=total)


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


async def _check_openalex() -> FuenteCheckResult:
    try:
        test = _search_literature_fn("agricultural application biofertilizer crop", max_results=1)
        if isinstance(test, dict) and test.get("error"):
            return FuenteCheckResult(ok=False, detalle=str(test["error"])[:120])
        return FuenteCheckResult(ok=True, detalle="reachable")
    except Exception as exc:
        return FuenteCheckResult(ok=False, detalle=str(exc)[:120])


async def _preflight() -> None:
    preflight = await run_preflight([
        FuenteCheck("INTA corpus", bloqueante=True, check_fn=_check_inta_corpus),
        FuenteCheck("corpus_cientifico (CONICET+INTA)", bloqueante=True, check_fn=_check_corpus_cientifico),
        FuenteCheck("OpenAlex", bloqueante=False, check_fn=_check_openalex),
    ])
    for adv in preflight.advertencias:
        logging.getLogger(__name__).warning(adv)
    if not preflight.ok:
        raise RuntimeError(
            "Pre-flight bloqueante — Especialista Ingeniero Agrónomo no puede continuar:\n"
            + "\n".join(preflight.bloqueantes)
        )


# ── Tool definitions ──────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "search_literature",
        "description": (
            "Busca en literatura científica vía OpenAlex (250M+ papers).\n"
            "Usar para: evaluar uso agronómico de un producto/enfoque (dosis, compatibilidad de\n"
            "cultivo/suelo, eficacia agronómica reportada, riesgos de aplicación), entender\n"
            "madurez de la práctica agrícola. Siempre en inglés. max_results=10 por defecto."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Búsqueda en inglés, focalizada en el uso agronómico buscado."},
                "max_results": {"type": "integer", "description": "Número de resultados (5-15 recomendado).", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "expand_agrovoc",
        "description": (
            "Expande un término de búsqueda contra el tesauro AGROVOC de la FAO — especialmente\n"
            "relevante para este especialista (vocabulario agrícola/agropecuario controlado).\n"
            "Retorna el prefLabel en español e inglés, términos más amplios, más específicos y\n"
            "relacionados. Usar antes de search_corpus_inta cuando el término está en inglés."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"term": {"type": "string", "description": "Término a expandir, ES o EN."}},
            "required": ["term"],
        },
    },
    {
        "name": "search_corpus_inta",
        "description": (
            "Busca en el corpus de papers INTA Digital cosechados localmente (1.600+ trabajos).\n"
            "Áreas cubiertas: producción agropecuaria argentina, manejo de suelos y cultivos,\n"
            "fertilización, sanidad vegetal/animal — la fuente más directamente relevante para\n"
            "este especialista. Complementa search_literature (OpenAlex global) con literatura\n"
            "local argentina. Soporta español e inglés. Operadores: 'biofertilizante suelo',\n"
            "'dosis AND aplicación'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Texto libre en español o inglés."},
                "tipo": {
                    "type": "string",
                    "description": "Filtrar por tipo de documento.",
                    "enum": ["paper", "reporte", "norma", "patente", "otro",
                             "tesis", "ponencia", "libro", "parte_libro", "divulgacion", "folleto"],
                },
                "limit": {"type": "integer", "description": "Máximo de resultados (default 1000 — exhaustivo).", "default": 1000},
            },
            "required": ["query"],
        },
    },
    {
        "name": "buscar_corpus_cientifico",
        "description": (
            "Busca por similitud semántica en corpus_cientifico — CONICET (625 fichas, repositorios\n"
            "argentinos vía OAI-PMH) + INTA (vía el motor nuevo). Única fuente con literatura de\n"
            "CONICET — sin este tool el agente no tiene ningún acceso a CONICET. Usar para\n"
            "literatura académica argentina sobre el uso agronómico buscado, cualquier disciplina."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "consulta": {"type": "string", "description": "Términos a buscar — uso o práctica agronómica buscada. ES o EN."},
                "limit": {"type": "integer", "description": "Máximo de papers (default 100).", "default": 100},
            },
            "required": ["consulta"],
        },
    },
    {
        "name": "submit_evaluacion_tecnica",
        "description": (
            "ÚNICO output del agente. Llamar cuando tengas suficiente evidencia para responder:\n"
            "¿este producto/enfoque funciona de verdad como insumo agrícola/ganadero? ¿qué dosis,\n"
            "compatibilidad de cultivo/suelo, riesgos de manejo? No esperes certeza total —\n"
            "declarar el estado epistémico es suficiente."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "evaluacion_tecnica": {
                    "type": "object",
                    "description": "Análisis estructurado.",
                    "properties": {
                        "resumen": {
                            "type": "object",
                            "properties": {
                                "valor": {"type": "string"},
                                "estado": {"type": "string", "enum": ["establecido", "asumido", "a-confirmar"]},
                                "fuente": {"type": "string"},
                            },
                            "required": ["valor", "estado"],
                        },
                        "microorganismos_o_procesos_relevantes": {
                            "type": "array",
                            "description": "En este especialista: cultivos/prácticas/insumos agronómicos relevantes — nombre de campo reusado del schema compartido por consistencia entre especialistas.",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "nombre": {"type": "string"},
                                    "rol": {"type": "string"},
                                    "estado": {"type": "string", "enum": ["establecido", "asumido", "a-confirmar"]},
                                    "fuente": {"type": "string"},
                                },
                                "required": ["nombre", "rol", "estado"],
                            },
                        },
                        "enfoques_tecnicos_identificados": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "enfoque": {"type": "string"},
                                    "madurez": {"type": "string", "enum": ["maduro", "emergente", "experimental", "conceptual"]},
                                    "fuente": {"type": "string"},
                                },
                                "required": ["enfoque", "madurez"],
                            },
                        },
                        "riesgos_o_limitaciones": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "riesgo": {"type": "string"},
                                    "estado": {"type": "string", "enum": ["establecido", "asumido", "a-confirmar"]},
                                },
                                "required": ["riesgo", "estado"],
                            },
                        },
                        "brechas_de_conocimiento": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "brecha": {"type": "string"},
                                    "impacto_en_decision": {"type": "string", "enum": ["alto", "medio", "bajo"]},
                                    "donde_confirmar": {"type": "string"},
                                },
                                "required": ["brecha", "impacto_en_decision"],
                            },
                        },
                    },
                    "required": [
                        "resumen", "microorganismos_o_procesos_relevantes",
                        "enfoques_tecnicos_identificados", "riesgos_o_limitaciones",
                        "brechas_de_conocimiento",
                    ],
                },
                "especialista_adicional_recomendado": {
                    "type": "object",
                    "description": "¿Se necesita análisis especializado adicional?",
                    "properties": {
                        "si_no": {"type": "boolean"},
                        "descripcion": {
                            "type": "string",
                            "description": "Qué análisis adicional aportaría valor — QUÉ hace falta evaluar, sin nombrar el tipo de especialista (principio 7b).",
                        },
                        "razon": {"type": "string"},
                    },
                    "required": ["si_no"],
                },
                "informe_completo": {
                    "type": "string",
                    "description": (
                        "Narrativa completa del análisis en markdown. Incluir: pregunta agronómica "
                        "identificada, búsquedas realizadas, papers/normativa clave revisados, "
                        "razonamiento, conclusiones. Mínimo 3 secciones."
                    ),
                },
                "fuentes_y_cobertura": {
                    "type": "object",
                    "description": "Qué fuentes se consultaron y con qué cobertura — obligatorio (orchestration-layer.md Decisión 6).",
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
                    "description": "Lecciones para el loop de aprendizaje.",
                },
            },
            "required": ["evaluacion_tecnica", "especialista_adicional_recomendado", "informe_completo", "fuentes_y_cobertura"],
        },
    },
]


# ── System prompt ──────────────────────────────────────────────────────────────
# Deliberadamente sin ningún caso concreto mencionado (mismo checklist anti-sesgo que los otros
# especialistas) — el rol y el método son genéricos, el caso entra solo por contract_input.

SYSTEM_PROMPT = """Sos un ingeniero agrónomo, especializado en evaluar el USO AGRONÓMICO de un
producto o enfoque ya identificado por otro especialista — no si es biológicamente viable (eso ya
lo evaluó un especialista técnico) ni si se puede construir/operar (eso ya lo evaluó un
especialista de ingeniería), tu trabajo es: ¿funciona de verdad como insumo en producción
agrícola o ganadera real?

TU OBJETIVO: dado un producto o subproducto (ej. un efluente, un biofertilizante, un insumo
biológico) ya identificado como técnicamente prometedor, evaluar su valor y viabilidad como
insumo agropecuario — qué dosis y modo de aplicación son razonables, con qué cultivos o sistemas
productivos es compatible, qué efecto tiene sobre suelo/cultivo/animal, qué marco normativo aplica
a su uso, y qué tan madura está esa práctica agronómica (no la biología/química ni la ingeniería
de proceso de base). No proponés soluciones de negocio ni evaluás mercado — eso es de otros
agentes.

PRINCIPIO FUNDAMENTAL: la práctica agronómica es una variable, no un punto de partida. No asumas
de antemano qué cultivo, dosis o sistema productivo es el destino correcto — buscá en literatura/
normativa lo que la evidencia agronómica muestra. El producto puede no tener un uso agronómico
maduro o probado a la escala/contexto requerido — eso también es un hallazgo válido, no un
fracaso del análisis.

QUÉ RECIBÍS: una descripción del producto/enfoque a evaluar (contract_input — caso/tarea/
contexto). Nunca asumas un caso específico si no te lo dan explícitamente en el input de esta
corrida.

FUENTES DISPONIBLES:
- search_literature: literatura científica global (OpenAlex, 250M+ papers). Buscar en inglés.
- buscar_corpus_cientifico: corpus local — CONICET (625 fichas, todas las disciplinas) + INTA
  vía el motor nuevo. Única fuente con literatura de CONICET — usarla siempre.
- search_corpus_inta: corpus INTA Digital local (1.600+ papers, FTS exhaustivo) — la fuente más
  directamente relevante para este especialista (producción agropecuaria argentina). Español o
  inglés.
- expand_agrovoc: expande un término contra el tesauro AGROVOC (FAO, vocabulario agrícola
  controlado) — especialmente útil acá. Usar antes de search_corpus_inta cuando tenés un término
  en inglés para buscar en el corpus español.

Flujo sugerido: buscar_corpus_cientifico primero (cualquier problema) → expand_agrovoc si hace
falta traducir el término → search_corpus_inta con términos ES (producción agropecuaria
argentina) → search_literature con términos EN para contexto global y benchmarks (dosis
reportadas, eficacia agronómica, normativa comparada).

TU PROCESO:
1. Identificá la pregunta agronómica central del producto/enfoque (¿sirve como insumo? ¿para
   qué cultivo/sistema? ¿qué dosis?)
2. Buscá en literatura (3-5 búsquedas en total, usando la fuente más apropiada) — incluí
   siempre buscar_corpus_cientifico
3. Evaluá qué usos/prácticas agronómicas aplican y con qué madurez
4. Identificá riesgos, limitaciones y brechas de conocimiento (ej. ensayos de campo que faltan)
5. Decidí si un análisis especializado adicional (de otro dominio) aportaría valor que vos no
   podés dar — sin nombrar qué tipo de especialista, solo qué falta evaluar
6. Llamá submit_evaluacion_tecnica con el análisis estructurado

CUÁNDO CERRAR: cuando tengas suficiente evidencia para responder la pregunta agronómica central.
No acumulés papers si ya podés responder.

VERACIDAD POR DATO:
- establecido: lo dice la fuente, citás referencia
- asumido: inferencia razonable, aclarás el peso
- a-confirmar: gap real (ej. un ensayo de campo que solo se confirma probando), aclarás dónde
  verificar

Al llamar submit_evaluacion_tecnica, declará siempre fuentes_y_cobertura: qué fuentes
consultaste, cuántos resultados procesaste de cada una, y si alguna no estuvo disponible.
"""


# ── Contrato estándar (SEB-115) ───────────────────────────────────────────────

INPUT_CONTRACT = {
    "agent": "agronomo",
    "version": "1.0",
    "fields": {
        "caso": "Descripción del producto/enfoque a evaluar (puede omitirse si se pasa frente_id)",
        "tarea": "Evaluación agronómica pedida en esta corrida",
        "contexto": "Opcional — contexto adicional de otro agente o de quien invoca",
        "conocimiento": "{'frente_id': str} — requerido. Solo modelo casos.yaml (ver Design Gate, decisión A del Ingeniero Ambiental, mismo criterio).",
        "herramientas": ["search_literature", "buscar_corpus_cientifico", "expand_agrovoc", "search_corpus_inta", "submit_evaluacion_tecnica"],
    },
}

OUTPUT_CONTRACT = {
    "agent": "agronomo",
    "version": "1.0",
    "km_escribe": ["documento_caso conectado al frente vía frente_produce_documento"],
    "fields": {
        "análisis": "{'evaluacion_tecnica': dict, 'especialista_adicional_recomendado': dict, 'fuentes_y_cobertura': dict, 'informe_completo': str, ...}",
        "nivel_confianza": "'alto' | 'medio' | 'bajo' — basado en madurez de la práctica agronómica y brechas de alto impacto",
        "recomendaciones": "brechas_de_conocimiento de impacto alto",
        "próximo_agente": "None — no hay routing automático a otro especialista todavía",
        "nuevo_conocimiento": "lecciones_caso — aprendizajes de dominio para el loop de aprendizaje",
    },
}


# ── Input builder ─────────────────────────────────────────────────────────────

def build_input_desde_frente(frente_dict: dict, caso_dict: dict, pendientes: list[dict]) -> str:
    caso_props = caso_dict.get("props") or {}
    frente_props = frente_dict.get("props") or {}

    secciones = [
        f"# Caso\n\n**Nombre:** {caso_props.get('nombre', '')}\n\n{caso_props.get('descripcion', '')}",
        f"# Frente: {frente_props.get('nombre', '')}\n\n{frente_props.get('descripcion', '')}",
    ]

    if pendientes:
        lista = "\n".join(f"- {(p.get('props') or {}).get('descripcion', '')}" for p in pendientes)
        secciones.append(f"# Pendientes abiertos del caso (contexto, no necesariamente de este frente)\n\n{lista}")

    secciones.append(
        "---\n"
        "Tu tarea: dar una evaluación de uso agronómico de este frente. "
        "Llamá submit_evaluacion_tecnica cuando tengas suficiente evidencia."
    )

    return "\n\n".join(secciones)


# ── Agentic loop ──────────────────────────────────────────────────────────────

def _bloque_instruccion(tarea: str | None, contexto_extra: str | None, foco: str | None = None) -> str:
    partes = []
    if foco:
        partes.append(
            f"FOCO DE ESTA INVOCACIÓN: {foco}\n"
            "Priorizá este recorte por sobre el alcance general del frente."
        )
    if tarea:
        partes.append(f"TAREA ESPECÍFICA DE ESTA INVOCACIÓN:\n{tarea}")
    if contexto_extra:
        partes.append(f"CONTEXTO ADICIONAL PROVISTO POR QUIEN TE INVOCA:\n{contexto_extra}")
    return ("\n\n" + "\n\n".join(partes)) if partes else ""


async def _run_loop(
    identificador: str,
    system_blocks: list[dict],
    user_input: str,
    model: str,
    verbose: bool,
) -> tuple[str, dict, list[str], TokenTracker]:
    tracker = TokenTracker(agent=_AGENTE, oportunidad_id=identificador, model=model)
    messages = [{"role": "user", "content": user_input}]
    evaluacion_result = None

    while True:
        response = await _ai_complete(
            model=_resolver_modelo(model),
            max_tokens=16000,
            system=system_blocks,
            tools=TOOLS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})
        tracker.add(response.usage)

        if verbose:
            print(
                f"  [{tracker.calls}] stop={response.stop_reason} | "
                f"tokens in={response.usage.input_tokens} out={response.usage.output_tokens}"
            )

        if response.stop_reason == "max_tokens" and not evaluacion_result:
            raise RuntimeError(
                "Respuesta truncada por max_tokens antes de submit_evaluacion_tecnica "
                f"(max_tokens=16000, output={response.usage.output_tokens}). "
                "La evaluación está incompleta."
            )

        if response.stop_reason in ("end_turn", "max_tokens"):
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                if block.name == "submit_evaluacion_tecnica":
                    evaluacion_result = block.input
                    if verbose:
                        print("  -> submit_evaluacion_tecnica [capturado]\n")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps({"success": True, "message": "Evaluación registrada."}),
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

            if evaluacion_result:
                break
        else:
            break

    tracker.log(verbose)

    if evaluacion_result is None:
        raw = "".join(b.text for b in response.content if hasattr(b, "text"))
        return raw or "El agente no llamó submit_evaluacion_tecnica.", {}, [], tracker

    informe = evaluacion_result.get("informe_completo", "")
    evaluacion_tecnica = evaluacion_result.get("evaluacion_tecnica", {})
    especialista = evaluacion_result.get("especialista_adicional_recomendado", {"si_no": False})
    lecciones_auto = evaluacion_result.get("lecciones_caso") or []
    fuentes_y_cobertura = evaluacion_result.get("fuentes_y_cobertura") or {
        "fuentes_consultadas": [],
        "cobertura_declarada": "parcial-por-falla-de-fuente",
    }

    evaluacion_dict = {
        "evaluacion_tecnica": evaluacion_tecnica,
        "especialista_adicional_recomendado": especialista,
        "fuentes_y_cobertura": fuentes_y_cobertura,
        "agente": _AGENTE,
        "fecha": date.today().isoformat(),
        "modelo": model,
        "informe_completo": informe,
    }

    if verbose:
        recomienda = especialista.get("si_no", False)
        print(f"\n  {len(evaluacion_tecnica.get('enfoques_tecnicos_identificados', []))} enfoques identificados")
        if recomienda:
            print(f"  Especialista adicional recomendado: {especialista.get('descripcion', '')[:100]}")
        else:
            print("  Sin especialista adicional recomendado.")

    return informe, evaluacion_dict, lecciones_auto, tracker


async def run_agent_desde_frente(
    frente_id: str,
    verbose: bool = False,
    model: str = DEFAULT_MODEL,
    tarea: str | None = None,
    contexto_extra: str | None = None,
    foco: str | None = None,
) -> tuple[str, dict, list[str]]:
    """
    Corre el Especialista Ingeniero Agrónomo contra un frente del modelo de casos.yaml — único
    camino de invocación (mismo criterio que ingeniero_ambiental_agent).

    Returns:
        (informe_markdown, evaluacion_dict, lecciones_caso)
        No escribe al KM — eso lo hace la costura (orquestador/invocador.py::invocar_agente).
    """
    if verbose:
        print(f"\n{'='*60}\n  ESPECIALISTA INGENIERO AGRÓNOMO — CRIZA\n  Modelo: {model}\n{'='*60}\n")

    contexto = await obtener_frente_con_caso(frente_id, tenant=_TENANT)
    frente_dict, caso_dict = contexto["frente"], contexto["caso"]
    if not frente_dict:
        raise ValueError(f"Frente {frente_id} no encontrado en el KM")
    if not caso_dict:
        raise ValueError(f"Frente {frente_id} no tiene un caso asociado (conexión tiene_frente ausente)")

    await _preflight()

    pendientes = await obtener_pendientes_de_caso(caso_dict["id"], tenant=_TENANT)

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
    user_input = build_input_desde_frente(frente_dict, caso_dict, pendientes) + _bloque_instruccion(
        tarea, contexto_extra, foco
    )

    informe, evaluacion_dict, lecciones_auto, tracker = await _run_loop(
        frente_id, system_blocks, user_input, model, verbose
    )

    existing_tu = (frente_dict.get("props") or {}).get("token_usage") or {}
    existing_tu[_AGENTE] = tracker.to_dict()
    await motor_api.actualizar_props(frente_id, {"token_usage": existing_tu}, tenant=_TENANT)

    return informe, evaluacion_dict, lecciones_auto


# ── Interfaz de contrato estándar (SEB-115) ───────────────────────────────────

def _derive_confidence(evaluacion: dict) -> str:
    evaluacion_tecnica = evaluacion.get("evaluacion_tecnica") or {}
    enfoques = evaluacion_tecnica.get("enfoques_tecnicos_identificados") or []
    maduros = [e for e in enfoques if e.get("madurez") == "maduro"]
    brechas_altas = [
        b for b in (evaluacion_tecnica.get("brechas_de_conocimiento") or [])
        if b.get("impacto_en_decision") == "alto"
    ]
    if maduros and not brechas_altas:
        return "alto"
    if enfoques and len(brechas_altas) <= 1:
        return "medio"
    return "bajo"


async def run(
    contract_input: dict,
    verbose: bool = False,
    model: str = DEFAULT_MODEL,
) -> dict:
    """Interfaz de contrato estándar para el Orquestador (SEB-115). Wraps run_agent_desde_frente()
    — solo acepta frente_id."""
    conocimiento = contract_input.get("conocimiento") or {}
    frente_id = conocimiento.get("frente_id") if isinstance(conocimiento, dict) else None
    if not frente_id:
        raise ValueError("Especialista Ingeniero Agrónomo requiere 'frente_id' en contract_input['conocimiento']")

    informe, evaluacion, lecciones = await run_agent_desde_frente(
        frente_id,
        verbose=verbose,
        model=model,
        tarea=contract_input.get("tarea") or None,
        contexto_extra=contract_input.get("contexto") or None,
        foco=contract_input.get("caso") or None,
    )

    evaluacion_tecnica = evaluacion.get("evaluacion_tecnica") or {}
    brechas_altas = [
        b["brecha"]
        for b in (evaluacion_tecnica.get("brechas_de_conocimiento") or [])
        if b.get("impacto_en_decision") == "alto"
    ]

    return {
        "análisis": evaluacion,
        "nivel_confianza": _derive_confidence(evaluacion),
        "recomendaciones": brechas_altas,
        "próximo_agente": None,
        "nuevo_conocimiento": lecciones,
    }
