"""
Especialista Microbiólogo — CRIZA

Evalúa qué microorganismos, procesos y enfoques técnicos aplican a un problema de tratamiento
biológico de efluentes/aguas residuales. Primer especialista de la "biblioteca de especialistas"
(docs/PROPUESTA_DESTINO.md §5) más allá de los 4 agentes del expediente viejo — no evalúa
condiciones de blue ocean (por eso NO carga marco_blue_ocean_CRIZA.md, a diferencia de
evidence_generalista/investigacion_amplia/armador: ese marco define qué es un blue ocean para
CRIZA, y este agente da una evaluación técnica, no esa evaluación).

Tools: search_literature (OpenAlex), buscar_corpus_cientifico (CONICET+INTA),
       search_corpus_inta (INTA legacy, exhaustivo), expand_agrovoc,
       search_kegg (rutas metabólicas), search_rhea (reacciones/EC), search_uniprot (enzimas),
       search_bacdive (fenotipo de cepas), submit_evaluacion_tecnica.
Ver docs/DESIGN_GATE.md — decisiones A-F (2026-08-16). BRENDA (cinética de enzimas, requiere
SOAP) queda deliberadamente afuera — ver Etapa 8 del plan de construcción.

El input entra SOLO por contract_input (caso/tarea/contexto) — el SYSTEM_PROMPT no menciona
ningún caso concreto, a propósito (ver decisión A del Design Gate: specialist_proteins.py quedó
sesgado a un caso cancelado por hacer exactamente lo contrario).
"""

import asyncio
import json
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
from utils.uniprot import search_uniprot as _search_uniprot_fn
from utils.bacdive import search_bacdive as _search_bacdive_fn
from knowledge_module.motor import api as motor_api
import knowledge_module.aprendizaje as aprendizaje
from utils.token_tracker import TokenTracker
from knowledge_module.preflight import FuenteCheck, FuenteCheckResult, run_preflight
from knowledge_module.db import get_session_factory
from sqlalchemy import text as _sql_text

DEFAULT_MODEL = os.getenv("MICROBIOLOGO_MODEL", "claude-sonnet-4-6")
_AGENTE = "microbiologo"
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
        test = _search_literature_fn("microbial treatment wastewater", max_results=1)
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
            "Usar para: evaluar qué microorganismos/procesos/mecanismos aplican a un problema\n"
            "dado, entender madurez de un enfoque, identificar alternativas. Siempre en inglés.\n"
            "max_results=10 por defecto."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Búsqueda en inglés, focalizada en el mecanismo o proceso buscado."},
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
            "Soporta español e inglés. Operadores: 'efluente biodigestor', 'metano AND digestión'."
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
            "literatura académica argentina sobre el mecanismo/proceso buscado, cualquier disciplina."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "consulta": {"type": "string", "description": "Términos a buscar — mecanismo o proceso buscado. ES o EN."},
                "limit": {"type": "integer", "description": "Máximo de papers (default 100).", "default": 100},
            },
            "required": ["consulta"],
        },
    },
    {
        "name": "search_kegg",
        "description": (
            "Busca en KEGG (rutas metabólicas, módulos, compuestos, ortólogos, genomas).\n"
            "Usar para: identificar la ruta metabólica/proceso bioquímico exacto que explica un\n"
            "mecanismo (ej. metanogénesis, degradación de un compuesto), o qué genes/enzimas la\n"
            "componen. Trae el detalle completo de los primeros 3 resultados automáticamente.\n"
            "Query en inglés."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Búsqueda en inglés (proceso, compuesto u organismo)."},
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
            "y ChEBI. Usar para confirmar la reacción exacta (con EC number) que media una\n"
            "transformación química específica (ej. 'methane' -> reacciones de oxidación de\n"
            "metano con su EC number). Complementa search_kegg (rutas) con el detalle de\n"
            "reacción individual. Query en inglés, nombre de compuesto, EC number o RHEA:ID."
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
        "name": "search_uniprot",
        "description": (
            "Busca proteínas/enzimas en UniProt por nombre. Trae función, organismo, EC number\n"
            "(si aplica) y longitud. Usar para identificar qué enzima específica media un\n"
            "proceso y en qué organismo está documentada. Complementa search_rhea (reacción) y\n"
            "search_kegg (ruta) con la identidad de la proteína. Query en inglés."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Nombre de la proteína/enzima en inglés."},
                "organism": {"type": "string", "description": "Organismo opcional, en latín (ej. 'Methylococcus capsulatus')."},
                "max_results": {"type": "integer", "description": "Cantidad de resultados (default 5).", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_bacdive",
        "description": (
            "Busca cepas bacterianas por género/especie en BacDive (DSMZ) — la mayor base de\n"
            "fenotipos bacterianos: metabolismo, tolerancia a oxígeno, rango de temperatura,\n"
            "hábitat. Usar para confirmar si una bacteria candidata tiene el fenotipo que el\n"
            "problema requiere (ej. anaerobia estricta, termófila). Requiere credenciales\n"
            "BacDive configuradas — si no están, devuelve error explícito, no fallar en silencio."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "organism": {"type": "string", "description": "Género o especie, en latín (ej. 'Methanosarcina')."},
                "max_results": {"type": "integer", "description": "Cantidad de cepas a detallar (default 5).", "default": 5},
            },
            "required": ["organism"],
        },
    },
    {
        "name": "submit_evaluacion_tecnica",
        "description": (
            "ÚNICO output del agente. Llamar cuando tengas suficiente evidencia para responder:\n"
            "¿qué microorganismos/procesos aplican? ¿qué tan maduro está el enfoque? ¿qué falta\n"
            "confirmar? No esperes certeza total — declarar el estado epistémico es suficiente."
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

SYSTEM_PROMPT = """Sos un especialista en microbiología aplicada al tratamiento biológico de efluentes y aguas residuales.

TU OBJETIVO: Dado un problema técnico, evaluar qué microorganismos, procesos biológicos o enfoques
técnicos aplican — con qué madurez científica, qué riesgos y qué queda sin confirmar. No proponés
soluciones de negocio ni evaluás mercado — eso es de otros agentes. Tu trabajo es la evidencia
técnica: ¿qué dice la ciencia sobre esto?

PRINCIPIO FUNDAMENTAL: la tecnología/el microorganismo es una variable, no un punto de partida.
No asumas de antemano qué microorganismo o proceso resuelve el problema — buscá en literatura lo
que la evidencia muestra. El problema puede no tener solución conocida madura — eso también es
un hallazgo válido, no un fracaso del análisis.

QUÉ RECIBÍS: una descripción del problema técnico (contract_input — caso/tarea/contexto). Nunca
asumas un caso específico si no te lo dan explícitamente en el input de esta corrida.

FUENTES DISPONIBLES:
- search_literature: literatura científica global (OpenAlex, 250M+ papers). Buscar en inglés.
- buscar_corpus_cientifico: corpus local — CONICET (625 fichas, todas las disciplinas) + INTA
  vía el motor nuevo. Única fuente con literatura de CONICET — usarla siempre.
- search_corpus_inta: corpus INTA Digital local (1.600+ papers, FTS exhaustivo). Español o
  inglés. Útil para problemas ligados a producción agropecuaria argentina.
- expand_agrovoc: expande un término contra el tesauro AGROVOC (FAO). Usar antes de
  search_corpus_inta cuando tenés un término en inglés para buscar en el corpus español.
- search_kegg: rutas metabólicas/módulos/compuestos/genes KEGG. Usar cuando necesites precisar
  la ruta bioquímica exacta detrás de un proceso (ej. qué ruta metaboliza un compuesto dado).
- search_rhea: reacciones bioquímicas individuales con su EC number. Usar para confirmar la
  reacción exacta (y la enzima que la cataliza, por EC number) detrás de una transformación.
- search_uniprot: identidad de una enzima/proteína específica — función, organismo, EC number.
  Usar cuando ya identificaste una enzima candidata (por nombre o por EC number de Rhea/KEGG)
  y necesitás confirmar en qué organismo está documentada y con qué evidencia.
- search_bacdive: fenotipo de cepas bacterianas — metabolismo, tolerancia a oxígeno, temperatura,
  hábitat. Usar para confirmar si una bacteria candidata tiene el fenotipo que el problema
  requiere (ej. anaerobia estricta, termófila, halotolerante).

Flujo sugerido: buscar_corpus_cientifico primero (cualquier problema) → expand_agrovoc si hace
falta traducir el término → search_corpus_inta con términos ES → search_literature con términos
EN para contexto global. Si el problema requiere precisión bioquímica (qué microorganismo/enzima
exacta, qué ruta): search_kegg (ruta) → search_rhea (reacción/EC) → search_uniprot (proteína) →
search_bacdive (fenotipo de la cepa candidata) — en ese orden, solo hasta donde la evidencia lo
justifique, no es obligatorio agotar los cuatro.

TU PROCESO:
1. Identificá la pregunta técnica central del problema
2. Buscá en literatura (3-5 búsquedas en total, usando la fuente más apropiada) — incluí
   siempre buscar_corpus_cientifico
3. Si la pregunta requiere precisión bioquímica (microorganismo/enzima/ruta exacta), sumá
   search_kegg/search_rhea/search_uniprot/search_bacdive según haga falta
4. Evaluá qué microorganismos/procesos/enfoques aplican y con qué madurez
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
    "agent": "microbiologo",
    "version": "1.0",
    "fields": {
        "caso": "Descripción del problema técnico (puede omitirse si se pasa oportunidad_id)",
        "tarea": "Evaluación técnica pedida en esta corrida",
        "contexto": "Opcional — contexto adicional de otro agente o de quien invoca",
        "conocimiento": "{'oportunidad_id': str} — requerido para leer el KM y persistir resultados",
        "herramientas": [
            "search_literature", "buscar_corpus_cientifico", "expand_agrovoc", "search_corpus_inta",
            "search_kegg", "search_rhea", "search_uniprot", "search_bacdive",
            "submit_evaluacion_tecnica",
        ],
    },
}

OUTPUT_CONTRACT = {
    "agent": "microbiologo",
    "version": "1.0",
    "km_escribe": ["props.microbiologo"],
    "fields": {
        "análisis": "{'evaluacion_tecnica': dict, 'especialista_adicional_recomendado': dict, 'fuentes_y_cobertura': dict, 'informe_completo': str, ...}",
        "nivel_confianza": "'alto' | 'medio' | 'bajo' — basado en madurez de enfoques y brechas de alto impacto",
        "recomendaciones": "brechas_de_conocimiento de impacto alto",
        "próximo_agente": "None — no hay routing automático a otro especialista todavía (ver Design Gate, ninguno registrado)",
        "nuevo_conocimiento": "lecciones_caso — aprendizajes de dominio para el loop de aprendizaje",
    },
}


# ── Input builder ─────────────────────────────────────────────────────────────

def build_input(oportunidad_id: str, oportunidad_dict: dict) -> str:
    props = oportunidad_dict.get("props") or {}
    nombre = oportunidad_dict.get("nombre") or props.get("nombre") or oportunidad_id
    descripcion = props.get("descripcion") or ""

    secciones = [
        f"# Oportunidad\n\n**ID:** {oportunidad_id}\n**Nombre:** {nombre}\n\n{descripcion}",
    ]

    secciones.append(
        "---\n"
        "Tu tarea: dar una evaluación técnica microbiológica de este problema. "
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


async def run_agent(
    oportunidad_id: str,
    verbose: bool = False,
    model: str = DEFAULT_MODEL,
    tarea: str | None = None,
    contexto_extra: str | None = None,
    foco: str | None = None,
) -> tuple[str, dict, list[str]]:
    """
    Corre el Especialista Microbiólogo.

    Returns:
        (informe_markdown, evaluacion_dict, lecciones_caso)
        No escribe al KM — eso lo hace la costura (orquestador/invocador.py).
    """
    if verbose:
        print(f"\n{'='*60}\n  ESPECIALISTA MICROBIÓLOGO — CRIZA\n  Modelo: {model}\n{'='*60}\n")

    oportunidad_dict = await motor_api.obtener(oportunidad_id, tenant=_TENANT)
    if not oportunidad_dict:
        raise ValueError(f"Oportunidad {oportunidad_id} no encontrada en el KM")

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
            "Pre-flight bloqueante — Especialista Microbiólogo no puede continuar:\n"
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
    system_blocks = [{
        "type": "text",
        "text": effective_system,
        "cache_control": {"type": "ephemeral"},
    }]

    user_input = build_input(oportunidad_id, oportunidad_dict) + _bloque_instruccion(
        tarea, contexto_extra, foco
    )
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
                elif block.name == "search_kegg":
                    query = block.input.get("query", "")
                    if verbose:
                        print(f"  -> search_kegg: {query[:80]}")
                    try:
                        result = _search_kegg_fn(
                            query=query,
                            database=block.input.get("database", "pathway"),
                            max_results=block.input.get("max_results", 10),
                        )
                    except Exception as exc:
                        result = {"error": str(exc), "query": query}
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False, indent=2),
                    })
                elif block.name == "search_rhea":
                    query = block.input.get("query", "")
                    if verbose:
                        print(f"  -> search_rhea: {query[:80]}")
                    try:
                        result = _search_rhea_fn(query=query, max_results=block.input.get("max_results", 10))
                    except Exception as exc:
                        result = {"error": str(exc), "query": query}
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False, indent=2),
                    })
                elif block.name == "search_uniprot":
                    query = block.input.get("query", "")
                    if verbose:
                        print(f"  -> search_uniprot: {query[:80]}")
                    try:
                        result = _search_uniprot_fn(
                            query=query,
                            organism=block.input.get("organism"),
                            max_results=block.input.get("max_results", 5),
                        )
                    except Exception as exc:
                        result = {"error": str(exc), "query": query}
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False, indent=2),
                    })
                elif block.name == "search_bacdive":
                    organism = block.input.get("organism", "")
                    if verbose:
                        print(f"  -> search_bacdive: {organism[:80]}")
                    try:
                        result = _search_bacdive_fn(organism=organism, max_results=block.input.get("max_results", 5))
                    except Exception as exc:
                        result = {"error": str(exc), "organism": organism}
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
    existing_tu = (oportunidad_dict.get("props") or {}).get("token_usage") or {}
    existing_tu[_AGENTE] = tracker.to_dict()
    await motor_api.actualizar_props(oportunidad_id, {"token_usage": existing_tu}, tenant=_TENANT)

    if evaluacion_result is None:
        raw = "".join(b.text for b in response.content if hasattr(b, "text"))
        return raw or "El agente no llamó submit_evaluacion_tecnica.", {}, []

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

    # El write-back de props.microbiologo NO es responsabilidad de este agente — lo hace la
    # costura (orquestador/invocador.py::invocar_agente), siempre. Ver agents_registry.yaml.

    if verbose:
        recomienda = especialista.get("si_no", False)
        print(f"\n  KM actualizado — {len(evaluacion_tecnica.get('enfoques_tecnicos_identificados', []))} enfoques identificados")
        if recomienda:
            print(f"  Especialista adicional recomendado: {especialista.get('descripcion', '')[:100]}")
        else:
            print("  Sin especialista adicional recomendado.")

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
    """Interfaz de contrato estándar para el Orquestador (SEB-115). Wraps run_agent()."""
    conocimiento = contract_input.get("conocimiento") or {}
    oportunidad_id = conocimiento.get("oportunidad_id") if isinstance(conocimiento, dict) else None
    if not oportunidad_id:
        raise ValueError("Especialista Microbiólogo requiere 'oportunidad_id' en contract_input['conocimiento']")

    informe, evaluacion, lecciones = await run_agent(
        oportunidad_id,
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
