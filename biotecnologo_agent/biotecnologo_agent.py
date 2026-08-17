"""
Especialista Biotecnólogo — CRIZA

Evalúa qué producto de valor se puede construir vía bioprocesos a partir de un material
biológico/subproducto ya identificado en un caso, y con qué ruta metabólica/biotecnológica —
distinto de los otros 3 especialistas: el Microbiólogo diagnostica el proceso biológico DEL
MATERIAL EN SÍ (¿cómo tratarlo?), el Ingeniero Ambiental evalúa factibilidad de ingeniería del
tratamiento, el Agrónomo evalúa uso agronómico del resultado. Este agente responde una pregunta
distinta: "¿qué se puede FABRICAR a partir de esto, con qué ruta, y qué tan madura/libre está esa
ruta?" (docs/DESIGN_GATE.md decisión B).

Tools: search_literature (OpenAlex), buscar_corpus_cientifico (CONICET+INTA),
       search_corpus_inta (INTA legacy, exhaustivo), expand_agrovoc,
       search_kegg (rutas metabólicas de biosíntesis, reusado de microbiologo_agent),
       search_rhea (reacciones/EC, reusado de microbiologo_agent),
       search_pubchem (identidad química del producto candidato, nuevo),
       search_chebi (clasificación química/biológica, nuevo), submit_evaluacion_tecnica.
Ver docs/DESIGN_GATE.md — decisiones A-D (2026-08-17). Búsqueda de patentes queda
deliberadamente afuera (requiere API key que nadie consiguió todavía) — ver Scope §4.

El input entra SOLO por contract_input (caso/tarea/contexto) — el SYSTEM_PROMPT no menciona
ningún caso concreto, a propósito (mismo checklist anti-sesgo que los otros 3 especialistas).
"""

import asyncio
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
from utils.kegg import search_kegg as _search_kegg_fn
from utils.rhea import search_rhea as _search_rhea_fn
from utils.pubchem import search_pubchem as _search_pubchem_fn
from utils.chebi import search_chebi as _search_chebi_fn
from utils.casos import obtener_frente_con_caso, obtener_pendientes_de_caso, obtener_documentos_aportados_de_frente
from knowledge_module.motor import api as motor_api
import knowledge_module.aprendizaje as aprendizaje
from utils.token_tracker import TokenTracker
from knowledge_module.preflight import FuenteCheck, FuenteCheckResult, run_preflight
from knowledge_module.db import get_session_factory
from sqlalchemy import text as _sql_text

DEFAULT_MODEL = os.getenv("BIOTECNOLOGO_MODEL", "claude-sonnet-4-6")
_AGENTE = "biotecnologo"
_TENANT = "criza"


async def _search_inta_fn(query: str, tipo: str | None = None, limit: int = 1000, tenant_id: str = "criza") -> dict:
    """Búsqueda exhaustiva sobre el corpus INTA — ver evidence_generalista._search_inta_fn,
    mismo patrón (OR sobre términos vía get_sector_corpus, sin muestrear por default)."""
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
        test = _search_literature_fn("bioprocess engineering fermentation", max_results=1)
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
            "Busca en literatura científica vía OpenAlex (250M+ papers).\n"
            "Usar para: evaluar qué productos/rutas de bioproceso aplican a un material dado,\n"
            "entender madurez de una ruta biotecnológica, identificar alternativas. Siempre en\n"
            "inglés. max_results=10 por defecto."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Búsqueda en inglés, focalizada en el producto o ruta de bioproceso buscada."},
                "max_results": {"type": "integer", "description": "Número de resultados (5-15 recomendado).", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "expand_agrovoc",
        "description": (
            "Expande un término de búsqueda contra el tesauro AGROVOC de la FAO.\n"
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
            "Áreas cubiertas: biotecnología agropecuaria, virología, patobiología animal,\n"
            "sanidad vegetal, inocuidad alimentaria, genómica aplicada.\n"
            "Complementa search_literature (OpenAlex global) con literatura local argentina.\n"
            "Soporta español e inglés. Operadores: 'fermentación industrial', 'bioplástico AND PHA'."
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
            "literatura académica argentina sobre el producto/ruta de bioproceso buscado."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "consulta": {"type": "string", "description": "Términos a buscar — producto o ruta de bioproceso buscada. ES o EN."},
                "limit": {"type": "integer", "description": "Máximo de papers (default 100).", "default": 100},
            },
            "required": ["consulta"],
        },
    },
    {
        "name": "search_kegg",
        "description": (
            "Busca en KEGG (rutas metabólicas, módulos, compuestos, ortólogos, genomas).\n"
            "Usar para: identificar la ruta metabólica exacta de BIOSÍNTESIS de un producto\n"
            "candidato (ej. PHA, ácido láctico), o qué genes/enzimas la componen. Trae el\n"
            "detalle completo de los primeros 3 resultados automáticamente. Query en inglés."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Búsqueda en inglés (producto, ruta u organismo)."},
                "database": {
                    "type": "string",
                    "description": "Base de KEGG a buscar.",
                    "enum": ["pathway", "module", "compound", "ko", "genome"],
                    "default": "pathway",
                },
                "max_results": {"type": "integer", "description": "Cantidad de resultados (default 10).", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_rhea",
        "description": (
            "Busca reacciones bioquímicas en Rhea — base curada cross-referenciada a EC number\n"
            "y ChEBI. Usar para confirmar la reacción exacta (con EC number) de un paso de\n"
            "biosíntesis del producto candidato. Complementa search_kegg (ruta completa) con el\n"
            "detalle de reacción individual. Query en inglés: compuesto, EC number o RHEA:ID."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Compuesto, EC number o RHEA:ID a buscar."},
                "max_results": {"type": "integer", "description": "Cantidad de resultados (default 10).", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_pubchem",
        "description": (
            "Busca un compuesto en PubChem por nombre — trae fórmula molecular, peso molecular,\n"
            "nombre IUPAC y SMILES. Usar para confirmar la identidad química exacta del producto\n"
            "candidato antes de evaluar su viabilidad de mercado o proceso. Query en inglés\n"
            "(ej. 'struvite', no 'estruvita')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Nombre del compuesto en inglés."}},
            "required": ["query"],
        },
    },
    {
        "name": "search_chebi",
        "description": (
            "Busca una entidad química en ChEBI (Chemical Entities of Biological Interest) —\n"
            "clasificación curada por rol biológico/químico, con sinónimos y definición. Usar\n"
            "para entender en qué categoría cae un producto candidato (ej. metabolito, polímero\n"
            "biodegradable) más allá de su fórmula. Complementa search_pubchem. Query en inglés."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Nombre del compuesto o entidad en inglés."},
                "max_results": {"type": "integer", "description": "Cantidad de resultados (default 5).", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "submit_evaluacion_tecnica",
        "description": (
            "ÚNICO output del agente. Llamar cuando tengas suficiente evidencia para responder:\n"
            "¿qué producto(s) se pueden fabricar y con qué ruta biotecnológica? ¿qué tan madura\n"
            "está la ruta? ¿qué falta confirmar? No esperes certeza total — declarar el estado\n"
            "epistémico es suficiente."
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
                        "Narrativa completa del análisis en markdown. Incluir: pregunta técnica "
                        "identificada, búsquedas realizadas, papers clave revisados, razonamiento, "
                        "conclusiones. Mínimo 3 secciones."
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
# Deliberadamente sin ningún caso concreto mencionado (ver Design Gate, decisión A) — el rol y
# el método son genéricos, el caso entra solo por contract_input en cada corrida.

SYSTEM_PROMPT = """Sos un especialista en biotecnología e ingeniería de bioprocesos.

TU OBJETIVO: Dado un material biológico o subproducto (ej. un residuo, un efluente, una corriente
lateral de un proceso industrial), evaluar QUÉ PRODUCTO DE VALOR se puede construir a partir de él
vía un bioproceso — con qué ruta metabólica o proceso de biosíntesis, con qué madurez científica/
tecnológica, y qué queda sin confirmar. No evaluás cómo TRATAR el material (eso es de otro
especialista, enfocado en microbiología del proceso), ni la factibilidad de ingeniería de planta,
ni el uso agronómico del resultado — vos evaluás qué se puede FABRICAR y con qué ruta
biotecnológica. Tampoco proponés soluciones de negocio ni evaluás mercado — eso es de otros
agentes. Tu trabajo es la evidencia técnica: ¿qué dice la ciencia sobre esto?

PRINCIPIO FUNDAMENTAL: el producto o la ruta biotecnológica es una variable, no un punto de
partida. No asumas de antemano qué producto conviene fabricar — buscá en literatura lo que la
evidencia muestra sobre rutas viables a partir del material dado. Priorizá rutas que generen un
producto con identidad propia y conexión no obvia al material de origen por sobre la respuesta más
convencional — si diez equipos ya llegarían a la misma conclusión obvia, esa conclusión sola no
alcanza como hallazgo diferenciador (igual hay que reportarla si es la más madura). El problema
puede no tener una ruta madura conocida — eso también es un hallazgo válido, no un fracaso del
análisis.

QUÉ RECIBÍS: una descripción del material/problema técnico (contract_input — caso/tarea/
contexto). Nunca asumas un caso específico si no te lo dan explícitamente en el input de esta
corrida.

FUENTES DISPONIBLES:
- search_literature: literatura científica global (OpenAlex, 250M+ papers). Buscar en inglés.
- buscar_corpus_cientifico: corpus local — CONICET (625 fichas, todas las disciplinas) + INTA
  vía el motor nuevo. Única fuente con literatura de CONICET — usarla siempre.
- search_corpus_inta: corpus INTA Digital local (1.600+ papers, FTS exhaustivo). Español o
  inglés. Útil para problemas ligados a producción agropecuaria/agroindustrial argentina.
- expand_agrovoc: expande un término contra el tesauro AGROVOC (FAO). Usar antes de
  search_corpus_inta cuando tenés un término en inglés para buscar en el corpus español.
- search_kegg: rutas metabólicas/módulos/compuestos/genes KEGG. Usar para precisar la ruta de
  BIOSÍNTESIS exacta detrás de un producto candidato (ej. qué ruta produce un bioplástico dado).
- search_rhea: reacciones bioquímicas individuales con su EC number. Usar para confirmar la
  reacción exacta (y la enzima que la cataliza) detrás de un paso de biosíntesis.
- search_pubchem: identidad química de un producto candidato — fórmula, peso molecular, SMILES.
  Usar para confirmar exactamente qué es el compuesto que estás evaluando. Query en inglés.
- search_chebi: clasificación química/biológica curada de una entidad, con sinónimos y
  definición. Complementa search_pubchem con el rol biológico/químico del compuesto.

Flujo sugerido: buscar_corpus_cientifico primero (cualquier problema) → expand_agrovoc si hace
falta traducir el término → search_corpus_inta con términos ES → search_literature con términos
EN para contexto global y madurez de la ruta. Cuando ya tengas un producto candidato: search_kegg
(ruta de biosíntesis) → search_rhea (reacción/EC específica) → search_pubchem (identidad química
exacta) → search_chebi (clasificación/rol) — en ese orden, solo hasta donde la evidencia lo
justifique, no es obligatorio agotar las cuatro.

TU PROCESO:
1. Identificá la pregunta central: qué producto(s) de valor son candidatos a partir del material
2. Buscá en literatura (3-5 búsquedas en total, usando la fuente más apropiada) — incluí
   siempre buscar_corpus_cientifico
3. Para cada producto candidato con evidencia real, sumá search_kegg/search_rhea/search_pubchem/
   search_chebi según haga falta para precisar la ruta y la identidad química
4. Evaluá qué rutas biotecnológicas aplican y con qué madurez
5. Identificá riesgos, limitaciones y brechas de conocimiento
6. Decidí si un análisis especializado adicional (de otro dominio) aportaría valor que vos no
   podés dar — sin nombrar qué tipo de especialista, solo qué falta evaluar
7. Llamá submit_evaluacion_tecnica con el análisis estructurado

CUÁNDO CERRAR: cuando tengas suficiente evidencia para responder la pregunta técnica central. No
acumulés papers si ya podés responder.

VERACIDAD POR DATO:
- establecido: lo dice la fuente, citás referencia
- asumido: inferencia razonable, aclarás el peso
- a-confirmar: gap real, aclarás dónde verificar

Al llamar submit_evaluacion_tecnica, declará siempre fuentes_y_cobertura: qué fuentes
consultaste, cuántos resultados procesaste de cada una, y si alguna no estuvo disponible.
"""


# ── Contrato estándar (SEB-115) ───────────────────────────────────────────────

INPUT_CONTRACT = {
    "agent": "biotecnologo",
    "version": "1.0",
    "fields": {
        "caso": "Descripción del material/problema técnico",
        "tarea": "Evaluación técnica pedida en esta corrida",
        "contexto": "Opcional — contexto adicional de otro agente o de quien invoca",
        "conocimiento": "{'frente_id': str} (modelo de casos.yaml) — único camino soportado, ver Design Gate decisión C del contrato.",
        "herramientas": [
            "search_literature", "buscar_corpus_cientifico", "expand_agrovoc", "search_corpus_inta",
            "search_kegg", "search_rhea", "search_pubchem", "search_chebi",
            "submit_evaluacion_tecnica",
        ],
    },
}

OUTPUT_CONTRACT = {
    "agent": "biotecnologo",
    "version": "1.0",
    "km_escribe": [
        "documento_caso conectado al frente vía frente_produce_documento",
    ],
    "fields": {
        "análisis": "{'evaluacion_tecnica': dict, 'especialista_adicional_recomendado': dict, 'fuentes_y_cobertura': dict, 'informe_completo': str, ...}",
        "nivel_confianza": "'alto' | 'medio' | 'bajo' — basado en madurez de enfoques y brechas de alto impacto",
        "recomendaciones": "brechas_de_conocimiento de impacto alto",
        "próximo_agente": "None — no hay routing automático a otro especialista todavía",
        "nuevo_conocimiento": "lecciones_caso — aprendizajes de dominio para el loop de aprendizaje",
    },
}


# ── Input builder ─────────────────────────────────────────────────────────────

def build_input_desde_frente(
    frente_dict: dict, caso_dict: dict, pendientes: list[dict],
    documentos_aportados: list[dict] | None = None,
) -> str:
    """Construye el input contra el modelo de casos.yaml (frente_id) — ver
    utils/casos.py::obtener_frente_con_caso/obtener_pendientes_de_caso.

    `documentos_aportados` (Etapa 17b): archivos que Sebas subió desde el chat y quedaron
    conectados a este frente — se suman al input para que también una corrida formal los tenga
    disponibles, no solo el Conductor."""
    caso_props = caso_dict.get("props") or {}
    frente_props = frente_dict.get("props") or {}

    secciones = [
        f"# Caso\n\n**Nombre:** {caso_props.get('nombre', '')}\n\n{caso_props.get('descripcion', '')}",
        f"# Frente: {frente_props.get('nombre', '')}\n\n{frente_props.get('descripcion', '')}",
    ]

    if pendientes:
        lista = "\n".join(f"- {(p.get('props') or {}).get('descripcion', '')}" for p in pendientes)
        secciones.append(f"# Pendientes abiertos del caso (contexto, no necesariamente de este frente)\n\n{lista}")

    if documentos_aportados:
        bloques = "\n\n".join(
            f"## {(d.get('props') or {}).get('titulo', '')}\n\n{(d.get('props') or {}).get('contenido', '')}"
            for d in documentos_aportados
        )
        secciones.append(f"# Documentos aportados por Sebas para este frente\n\n{bloques}")

    secciones.append(
        "---\n"
        "Tu tarea: evaluar qué producto(s) de valor se pueden construir vía bioprocesos a partir "
        "del material de este frente, y con qué ruta biotecnológica. "
        "Llamá submit_evaluacion_tecnica cuando tengas suficiente evidencia."
    )

    return "\n\n".join(secciones)


# ── Agentic loop ──────────────────────────────────────────────────────────────

def _bloque_instruccion(tarea: str | None, contexto_extra: str | None, foco: str | None = None) -> str:
    """Instrucción propia de ESTA invocación — ver market_agent._bloque_instruccion."""
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
        FuenteCheck("INTA corpus", bloqueante=True, check_fn=_check_inta_corpus),
        FuenteCheck("corpus_cientifico (CONICET+INTA)", bloqueante=True, check_fn=_check_corpus_cientifico),
        FuenteCheck("OpenAlex", bloqueante=False, check_fn=_check_openalex),
    ])
    for adv in preflight.advertencias:
        logging.getLogger(__name__).warning(adv)
    if not preflight.ok:
        raise RuntimeError(
            "Pre-flight bloqueante — Especialista Biotecnólogo no puede continuar:\n"
            + "\n".join(preflight.bloqueantes)
        )


async def _despachar_tool(nombre: str, tool_input: dict, verbose: bool) -> dict:
    """Todas las tools EXCEPTO submit_evaluacion_tecnica — esa queda especial-casada en
    `_run_loop`. Reusada por `enviar_mensaje` (chat) sin duplicar el dispatch — mismo patrón que
    los otros 3 especialistas."""
    if nombre == "expand_agrovoc":
        term = tool_input.get("term", "")
        if verbose:
            print(f"  -> expand_agrovoc: {term[:60]}")
        try:
            expanded = _expand_agrovoc_fn(term)
            return expanded if expanded else {"found": False, "term": term}
        except Exception as exc:
            return {"error": str(exc), "term": term}
    if nombre == "search_corpus_inta":
        query = tool_input.get("query", "")
        if verbose:
            print(f"  -> search_corpus_inta: {query[:80]}")
        return await _search_inta_fn(
            query=query, tipo=tool_input.get("tipo"), limit=tool_input.get("limit", 1000), tenant_id=_TENANT,
        )
    if nombre == "search_literature":
        query = tool_input.get("query", "")
        if verbose:
            print(f"  -> search_literature: {query[:80]}")
        return _search_literature_fn(query=query, max_results=tool_input.get("max_results", 10))
    if nombre == "buscar_corpus_cientifico":
        consulta = tool_input.get("consulta", "")
        if verbose:
            print(f"  -> buscar_corpus_cientifico: {consulta[:80]}")
        return await _buscar_corpus_cientifico_fn(consulta=consulta, limit=tool_input.get("limit", 100))
    if nombre == "search_kegg":
        query = tool_input.get("query", "")
        if verbose:
            print(f"  -> search_kegg: {query[:80]}")
        try:
            return _search_kegg_fn(query=query, database=tool_input.get("database", "pathway"), max_results=tool_input.get("max_results", 10))
        except Exception as exc:
            return {"error": str(exc), "query": query}
    if nombre == "search_rhea":
        query = tool_input.get("query", "")
        if verbose:
            print(f"  -> search_rhea: {query[:80]}")
        try:
            return _search_rhea_fn(query=query, max_results=tool_input.get("max_results", 10))
        except Exception as exc:
            return {"error": str(exc), "query": query}
    if nombre == "search_pubchem":
        query = tool_input.get("query", "")
        if verbose:
            print(f"  -> search_pubchem: {query[:80]}")
        try:
            return _search_pubchem_fn(query=query)
        except Exception as exc:
            return {"error": str(exc), "query": query}
    if nombre == "search_chebi":
        query = tool_input.get("query", "")
        if verbose:
            print(f"  -> search_chebi: {query[:80]}")
        try:
            return _search_chebi_fn(query=query, max_results=tool_input.get("max_results", 5))
        except Exception as exc:
            return {"error": str(exc), "query": query}
    if verbose:
        print(f"  -> [tool desconocido: {nombre}]")
    return {"error": f"Tool '{nombre}' no implementado."}


async def _run_loop(
    identificador: str,
    system_blocks: list[dict],
    user_input: str,
    model: str,
    verbose: bool,
) -> tuple[str, dict, list[str], TokenTracker]:
    """Loop agéntico — mismo patrón que microbiologo_agent._run_loop. No persiste nada al KM,
    eso lo hace la costura (orquestador/invocador.py)."""
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
                    continue

                resultado = await _despachar_tool(block.name, block.input, verbose)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(resultado, ensure_ascii=False, indent=2, default=str),
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
    Corre el Especialista Biotecnólogo contra un frente del modelo de casos.yaml — único camino
    de invocación (ver docs/DESIGN_GATE.md decisión C del contrato).

    Returns:
        (informe_markdown, evaluacion_dict, lecciones_caso)
        No escribe al KM — eso lo hace la costura (orquestador/invocador.py::invocar_agente).
    """
    if verbose:
        print(f"\n{'='*60}\n  ESPECIALISTA BIOTECNÓLOGO — CRIZA (frente)\n  Modelo: {model}\n{'='*60}\n")

    contexto = await obtener_frente_con_caso(frente_id, tenant=_TENANT)
    frente_dict, caso_dict = contexto["frente"], contexto["caso"]
    if not frente_dict:
        raise ValueError(f"Frente {frente_id} no encontrado en el KM")
    if not caso_dict:
        raise ValueError(f"Frente {frente_id} no tiene un caso asociado (conexión tiene_frente ausente)")

    await _preflight()

    pendientes = await obtener_pendientes_de_caso(caso_dict["id"], tenant=_TENANT)
    documentos_aportados = await obtener_documentos_aportados_de_frente(frente_id, tenant=_TENANT)

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
    user_input = build_input_desde_frente(frente_dict, caso_dict, pendientes, documentos_aportados) + _bloque_instruccion(
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
    """Interfaz de contrato estándar para el Orquestador (SEB-115). Solo acepta frente_id — ver
    INPUT_CONTRACT."""
    conocimiento = contract_input.get("conocimiento") or {}
    frente_id = conocimiento.get("frente_id") if isinstance(conocimiento, dict) else None
    oportunidad_id = conocimiento.get("oportunidad_id") if isinstance(conocimiento, dict) else None

    if oportunidad_id:
        raise ValueError("Especialista Biotecnólogo solo acepta 'frente_id' en contract_input['conocimiento'] — no soporta 'oportunidad_id'")
    if not frente_id:
        raise ValueError("Especialista Biotecnólogo requiere 'frente_id' en contract_input['conocimiento']")

    kwargs = dict(
        verbose=verbose,
        model=model,
        tarea=contract_input.get("tarea") or None,
        contexto_extra=contract_input.get("contexto") or None,
        foco=contract_input.get("caso") or None,
    )
    informe, evaluacion, lecciones = await run_agent_desde_frente(frente_id, **kwargs)

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


# ── Chat conversacional (mismo patrón que los otros 3 especialistas) ───────────
#
# Distinto de run()/run_agent_desde_frente() (contrato SEB-115, un turno, termina en
# submit_evaluacion_tecnica, la costura persiste un documento_caso) — esto es para que Sebas
# pueda CONVERSAR con el especialista sin que cada intercambio dispare una evaluación formal.
# TOOLS_CHAT excluye submit_evaluacion_tecnica a propósito.

TOOLS_CHAT = [t for t in TOOLS if t["name"] != "submit_evaluacion_tecnica"]


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
    user_input = build_input_desde_frente(frente_dict, caso_dict, pendientes, documentos_aportados)
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
    Un turno de chat con el Especialista Biotecnólogo. `messages` se muta y se devuelve, mismo
    patrón que `conductor.enviar_mensaje()`.

    `frente_id=None` es el modo "consulta libre" — Sebas puede hacerle una pregunta puntual al
    especialista sin necesitar un caso/frente ya creado.
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
        response = await _ai_complete(
            model=_resolver_modelo(model), max_tokens=4096,
            system=system_blocks, tools=TOOLS_CHAT, messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})
        tracker.add(response.usage)

        if response.stop_reason != "tool_use":
            texto = "".join(b.text for b in response.content if hasattr(b, "text"))
            return texto, messages

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            if verbose:
                print(f"  -> {block.name}({block.input})")
            resultado = await _despachar_tool(block.name, block.input, verbose)
            tool_results.append({
                "type": "tool_result", "tool_use_id": block.id,
                "content": json.dumps(resultado, ensure_ascii=False, indent=2, default=str),
            })
        messages.append({"role": "user", "content": tool_results})
