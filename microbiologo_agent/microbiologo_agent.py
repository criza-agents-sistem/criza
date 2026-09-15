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
       search_bacdive (fenotipo de cepas), search_pubmed (literatura biomédica MeSH, nuevo
       2026-09-14), analizar_estabilidad_serie/detectar_cambios_de_regimen/
       correlacion_con_desfase/comparar_fuentes_de_datos (cómputo real vía
       utils/estadistica.py, nuevo 2026-09-14), submit_evaluacion_tecnica.
Ver docs/DESIGN_GATE.md — decisiones A-F (2026-08-16). BRENDA (cinética de enzimas, requiere
SOAP) queda deliberadamente afuera — ver Etapa 8 del plan de construcción.

El input entra SOLO por contract_input (caso/tarea/contexto) — el SYSTEM_PROMPT no menciona
ningún caso concreto, a propósito (ver decisión A del Design Gate: specialist_proteins.py quedó
sesgado a un caso cancelado por hacer exactamente lo contrario).
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
from utils.uniprot import search_uniprot as _search_uniprot_fn
from utils.bacdive import search_bacdive as _search_bacdive_fn
from utils.pubmed import search_pubmed as _search_pubmed_fn
from utils.estadistica import (
    analizar_estabilidad as _analizar_estabilidad_fn,
    detectar_cambios_de_regimen as _detectar_cambios_de_regimen_fn,
    correlacion_con_desfase as _correlacion_con_desfase_fn,
    comparar_fuentes as _comparar_fuentes_fn,
)
from utils.archivos import leer_serie_de_excel as _leer_serie_de_excel_fn
from utils.casos import (
    obtener_frente_con_caso, obtener_pendientes_de_caso, obtener_documentos_aportados_de_frente,
    obtener_documentos_de_frente, obtener_documento_por_id,
    obtener_archivo_original_de_documento_aportado,
)
from knowledge_module.motor import api as motor_api
import knowledge_module.aprendizaje as aprendizaje
from utils.token_tracker import TokenTracker
from knowledge_module.preflight import FuenteCheck, FuenteCheckResult, run_preflight
from knowledge_module.db import get_session_factory
from sqlalchemy import text as _sql_text

DEFAULT_MODEL = os.getenv("MICROBIOLOGO_MODEL", "claude-sonnet-5")
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
            "problema requiere (ej. anaerobia estricta, termófila)."
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
        "name": "search_pubmed",
        "description": (
            "Busca en PubMed (NCBI) — literatura biomédica con vocabulario MeSH, más preciso que\n"
            "OpenAlex para temas de microbiología/bioquímica/salud (ej. patógenos, toxicidad,\n"
            "mecanismos de degradación). Complementa search_literature, no lo reemplaza.\n"
            "Query en inglés."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Búsqueda en inglés, sintaxis PubMed o texto libre."},
                "max_results": {"type": "integer", "description": "Cantidad de resultados (default 20).", "default": 20},
            },
            "required": ["query"],
        },
    },
    {
        "name": "analizar_estabilidad_serie",
        "description": (
            "Cálculo real (no estimado a ojo) de estabilidad de una serie temporal de datos que\n"
            "Sebas aportó (ej. composición de un efluente en el tiempo) — media, desvío, CV%,\n"
            "tendencia real (Kendall tau) y clasificación ESTABLE/MODERADAMENTE_VARIABLE/\n"
            "NO_ESTABLE. Usar cuando necesites saber si el proceso biológico bajo evaluación es\n"
            "consistente en el tiempo. Nunca calcules esto vos mismo leyendo la tabla."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "datos": {
                    "type": "array",
                    "description": "Puntos [{'fecha': 'YYYY-MM-DD', 'valor': número}, ...], mínimo 5.",
                    "items": {
                        "type": "object",
                        "properties": {"fecha": {"type": "string"}, "valor": {"type": "number"}},
                        "required": ["fecha", "valor"],
                    },
                },
                "umbral_estable": {"type": "number", "description": "CV% por debajo del cual se clasifica ESTABLE (default 15).", "default": 15},
                "umbral_variable": {"type": "number", "description": "CV% por debajo del cual se clasifica MODERADAMENTE_VARIABLE (default 30).", "default": 30},
            },
            "required": ["datos"],
        },
    },
    {
        "name": "detectar_cambios_de_regimen",
        "description": (
            "Detecta si una serie temporal cambió de nivel de forma real y sostenida (no ruido de\n"
            "un solo punto) — ej. si el proceso biológico se movió a un nuevo régimen en algún\n"
            "momento del período. Un CV% sobre todo el período puede esconder esto (mezcla\n"
            "regímenes distintos en un solo número). Usar cuando sospeches que 'lo típico' cambió\n"
            "durante el período de datos disponible."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "datos": {
                    "type": "array",
                    "description": "Puntos [{'fecha': 'YYYY-MM-DD', 'valor': número}, ...], mínimo 10.",
                    "items": {
                        "type": "object",
                        "properties": {"fecha": {"type": "string"}, "valor": {"type": "number"}},
                        "required": ["fecha", "valor"],
                    },
                },
                "periodo": {"type": "string", "description": "Código de agrupación: 'M' mensual, 'W' semanal, 'Q' trimestral (default 'M').", "default": "M"},
            },
            "required": ["datos"],
        },
    },
    {
        "name": "correlacion_con_desfase",
        "description": (
            "Correlación real con desfase temporal entre dos series (ej. composición del\n"
            "material de entrada vs. un parámetro del proceso biológico varias semanas después).\n"
            "SIEMPRE incluye un chequeo de robustez (series diferenciadas) — si la correlación no\n"
            "lo pasa, vuelve marcada 'robusta: false' con una advertencia: puede ser una\n"
            "coincidencia de tendencias compartidas, no una relación real. Nunca reportes una\n"
            "correlación como hallazgo real sin mirar ese campo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "serie_x": {
                    "type": "array", "description": "Variable candidata a 'causa' — [{'fecha', 'valor'}, ...].",
                    "items": {"type": "object", "properties": {"fecha": {"type": "string"}, "valor": {"type": "number"}}, "required": ["fecha", "valor"]},
                },
                "serie_y": {
                    "type": "array", "description": "Variable de salida — [{'fecha', 'valor'}, ...], mínimo 10.",
                    "items": {"type": "object", "properties": {"fecha": {"type": "string"}, "valor": {"type": "number"}}, "required": ["fecha", "valor"]},
                },
                "ventana_dias": {"type": "integer", "description": "Ancho del promedio móvil de X, en días (default 7).", "default": 7},
                "lag_max_dias": {"type": "integer", "description": "Desfase máximo a probar, en días (default 90).", "default": 90},
            },
            "required": ["serie_x", "serie_y"],
        },
    },
    {
        "name": "comparar_fuentes_de_datos",
        "description": (
            "Compara dos series que deberían medir lo mismo (ej. dos laboratorios, dos métodos)\n"
            "antes de combinarlas en un solo análisis — detecta sesgo sistemático (razón\n"
            "constante entre ambas) en vez de asumir que son intercambiables. Usar antes de\n"
            "juntar datos de fuentes distintas del mismo parámetro en una sola serie temporal."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "serie_a": {
                    "type": "array", "description": "[{'fecha', 'valor'}, ...] de la fuente A.",
                    "items": {"type": "object", "properties": {"fecha": {"type": "string"}, "valor": {"type": "number"}}, "required": ["fecha", "valor"]},
                },
                "serie_b": {
                    "type": "array", "description": "[{'fecha', 'valor'}, ...] de la fuente B, mínimo 2 fechas en común con A.",
                    "items": {"type": "object", "properties": {"fecha": {"type": "string"}, "valor": {"type": "number"}}, "required": ["fecha", "valor"]},
                },
                "nombre_a": {"type": "string", "description": "Etiqueta de la fuente A (ej. nombre del laboratorio)."},
                "nombre_b": {"type": "string", "description": "Etiqueta de la fuente B."},
            },
            "required": ["serie_a", "serie_b"],
        },
    },
    {
        "name": "leer_serie_de_documento_aportado",
        "description": (
            "Lee datos reales de un Excel que Sebas aportó al caso (documento_aportado) — trae\n"
            "una serie [{'fecha','valor'}] lista para pasar a analizar_estabilidad_serie/\n"
            "correlacion_con_desfase/etc. Usá el documento_id de la lista de documentos\n"
            "aportados de tu input. Requiere el nombre EXACTO de hoja y columnas — no adivina la\n"
            "estructura del archivo. Si no sabés cuáles son, mirá primero el texto de\n"
            "previsualización de ese documento (título/contenido en tu input) para ver qué hojas\n"
            "y columnas tiene antes de llamar esta tool."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "documento_id": {"type": "string", "description": "id del documento_aportado (de la lista en tu input)."},
                "hoja": {"type": "string", "description": "Nombre exacto de la hoja del Excel."},
                "columna_fecha": {"type": "string", "description": "Nombre exacto de la columna de fecha."},
                "columna_valor": {"type": "string", "description": "Nombre exacto de la columna de valor."},
                "header_fila": {"type": "integer", "description": "Fila (0-indexed) donde está el header real, si no es la primera (default 0).", "default": 0},
                "filtro_columna": {"type": "string", "description": "Opcional — columna para filtrar filas (ej. un código de digestor/tanque, para no mezclar puntos de fuentes distintas en la misma hoja)."},
                "filtro_valor": {"type": "string", "description": "Opcional — valor exacto a filtrar en filtro_columna."},
            },
            "required": ["documento_id", "hoja", "columna_fecha", "columna_valor"],
        },
    },
    {
        "name": "ver_informe_especialista",
        "description": (
            "Trae el contenido completo de un informe puntual — ya sea uno que vos u OTRO "
            "especialista produjo antes sobre este mismo frente (ver la lista 'Informes ya "
            "producidos en este frente' en tu input), o un documento que Sebas aportó. Usala "
            "solo cuando el título de algo en esa lista es relevante para tu evaluación actual — "
            "no leas todos los informes, solo los que importan para tu tarea. Nunca inventes un "
            "id, usá el que aparece en la lista tal cual."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"documento_id": {"type": "string"}},
            "required": ["documento_id"],
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
- search_pubmed: literatura biomédica (NCBI, vocabulario MeSH) — más preciso que
  search_literature para temas de patógenos, toxicidad o mecanismos de degradación con
  relevancia en salud. Complementa search_literature, no lo reemplaza.
- analizar_estabilidad_serie / detectar_cambios_de_regimen / correlacion_con_desfase /
  comparar_fuentes_de_datos: cómputo numérico REAL (no estimado a ojo) sobre series de datos
  que Sebas aportó — ej. composición de un efluente en el tiempo. Si te dan una tabla con
  fechas y valores y te preguntan si es estable, si cambió de nivel, o si se correlaciona con
  otra variable, extraé los puntos y llamá la tool correspondiente — nunca calcules una media,
  un CV% o una correlación vos mismo leyendo la tabla, el resultado no es confiable.
  correlacion_con_desfase siempre incluye un chequeo de robustez (series diferenciadas) —
  revisá el campo 'robusta' antes de reportar una correlación como hallazgo real.
- leer_serie_de_documento_aportado: trae una serie real [{'fecha','valor'}] directo de un Excel
  que Sebas aportó (documento_aportado con archivo original guardado) — usala ANTES de pedirle a
  Sebas los números a mano si el documento ya está en la lista de "Documentos aportados" de tu
  input. Necesita el nombre exacto de hoja/columnas — si no los sabés, el título/contenido del
  documento en tu input trae una previsualización.
- ver_informe_especialista: trae el contenido completo de un informe que vos u otro especialista
  ya produjo sobre este mismo frente (tu input trae la lista de títulos disponibles, si hay
  alguno). Usala solo cuando un título de esa lista es relevante para tu evaluación actual — no
  leas todos los informes de memoria, solo los que importan para tu tarea.

Flujo sugerido: buscar_corpus_cientifico primero (cualquier problema) → expand_agrovoc si hace
falta traducir el término → search_corpus_inta con términos ES → search_literature con términos
EN para contexto global. Si el problema requiere precisión bioquímica (qué microorganismo/enzima
exacta, qué ruta): search_kegg (ruta) → search_rhea (reacción/EC) → search_uniprot (proteína) →
search_bacdive (fenotipo de la cepa candidata) → search_pubmed (literatura biomédica de
precisión, si el problema tiene relevancia en salud/toxicidad) — en ese orden, solo hasta donde
la evidencia lo justifique, no es obligatorio agotar los cinco.

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
Ese campo estructurado NO alcanza solo: el informe_completo (la narrativa que se lee, no el
JSON) tiene que incluir una sección visible "Búsquedas realizadas" que resuma lo mismo en
prosa — qué buscaste, en qué fuente, cuántos resultados, y qué encontraste de relevante en cada
una. Sin esa sección en el texto, el trabajo real que hiciste queda invisible para quien lee el
informe (encontrado real, 2026-08-19: pasó en una corrida de otro especialista).
"""


# ── Contrato estándar (SEB-115) ───────────────────────────────────────────────

INPUT_CONTRACT = {
    "agent": "microbiologo",
    "version": "1.1",
    "fields": {
        "caso": "Descripción del problema técnico (puede omitirse si se pasa oportunidad_id/frente_id)",
        "tarea": "Evaluación técnica pedida en esta corrida",
        "contexto": "Opcional — contexto adicional de otro agente o de quien invoca",
        "conocimiento": (
            "{'oportunidad_id': str} (modelo viejo, área descubrimiento) O "
            "{'frente_id': str} (modelo de casos.yaml, Etapa 4 del plan) — mutuamente "
            "excluyentes, exactamente uno de los dos requerido."
        ),
        "herramientas": [
            "search_literature", "buscar_corpus_cientifico", "expand_agrovoc", "search_corpus_inta",
            "search_kegg", "search_rhea", "search_uniprot", "search_bacdive", "search_pubmed",
            "analizar_estabilidad_serie", "detectar_cambios_de_regimen",
            "correlacion_con_desfase", "comparar_fuentes_de_datos",
            "leer_serie_de_documento_aportado", "submit_evaluacion_tecnica",
        ],
    },
}

OUTPUT_CONTRACT = {
    "agent": "microbiologo",
    "version": "1.1",
    "km_escribe": [
        "props.microbiologo (si se invocó con oportunidad_id)",
        "documento_caso conectado al frente vía frente_produce_documento (si se invocó con frente_id)",
    ],
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


def build_input_desde_frente(
    frente_dict: dict, caso_dict: dict, pendientes: list[dict],
    documentos_aportados: list[dict] | None = None,
    documentos_producidos: list[dict] | None = None,
) -> str:
    """Construye el input cuando se invoca contra el modelo de casos.yaml (frente_id) en vez de
    una oportunidad — ver utils/casos.py::obtener_frente_con_caso/obtener_pendientes_de_caso.

    `documentos_aportados` (Etapa 17b, 2026-08-17): archivos que Sebas subió desde el chat y
    quedaron conectados a este frente (`utils/casos.py::obtener_documentos_aportados_de_frente`)
    — se suman al input para que TAMBIÉN una corrida formal (no solo el Conductor) los tenga
    disponibles, cerrando el gap que Sebas señaló ("esperaba que se sintiera como con vos").

    `documentos_producidos` (Etapa 20, 2026-09-05): informes que OTROS especialistas (o vos
    mismo, en una corrida anterior) ya produjeron sobre este frente — Sebas: "estaría bueno que
    todos puedan ver qué está realizando el resto". Se suma solo la lista liviana (título +
    agente + fecha + id, vía `utils/casos.py::obtener_documentos_de_frente`) — el contenido
    completo se lee bajo demanda con la tool `ver_informe_especialista`, para no inflar el
    input con documentos que no son relevantes para esta corrida en particular."""
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
            "# Informes ya producidos en este frente (por vos u otros especialistas)\n\n"
            f"{lista}\n\n"
            "Son solo títulos — si alguno es relevante para tu evaluación, usá "
            "ver_informe_especialista(documento_id) para leer el contenido completo. No hace "
            "falta leerlos todos, solo los que importan para tu tarea."
        )

    if documentos_aportados:
        bloques = "\n\n".join(
            f"## {(d.get('props') or {}).get('titulo', '')}\n\n{(d.get('props') or {}).get('contenido', '')}"
            for d in documentos_aportados
        )
        secciones.append(f"# Documentos aportados por Sebas para este frente\n\n{bloques}")

    secciones.append(
        "---\n"
        "Tu tarea: dar una evaluación técnica microbiológica de este frente. "
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
    """Mismo pre-flight sin importar el modelo de dato de entrada (oportunidad_id o frente_id)
    — depende de fuentes externas (INTA/corpus_cientifico/OpenAlex), no del caller."""
    preflight = await run_preflight([
        FuenteCheck("INTA corpus", bloqueante=True, check_fn=_check_inta_corpus),
        FuenteCheck("corpus_cientifico (CONICET+INTA)", bloqueante=True, check_fn=_check_corpus_cientifico),
        FuenteCheck("OpenAlex", bloqueante=False, check_fn=_check_openalex),
    ])
    for adv in preflight.advertencias:
        logging.getLogger(__name__).warning(adv)
    if not preflight.ok:
        raise RuntimeError(
            "Pre-flight bloqueante — Especialista Microbiólogo no puede continuar:\n"
            + "\n".join(preflight.bloqueantes)
        )


async def _despachar_tool(nombre: str, tool_input: dict, verbose: bool) -> dict:
    """
    Todas las tools EXCEPTO submit_evaluacion_tecnica — esa queda especial-casada en `_run_loop`
    (marca el fin del análisis de un turno, no es una consulta de datos como el resto). Extraída
    a función propia (Etapa 10, 2026-08-16) para que `enviar_mensaje` (chat conversacional) la
    reuse sin duplicar el dispatch — antes vivía inline en el loop de `_run_loop`, que solo servía
    para la corrida de un turno vía `run()`/la costura.
    """
    if nombre == "ver_informe_especialista":
        documento_id = tool_input.get("documento_id", "")
        if verbose:
            print(f"  -> ver_informe_especialista: {documento_id}")
        return await obtener_documento_por_id(documento_id, tenant=_TENANT)
    if nombre == "leer_serie_de_documento_aportado":
        documento_id = tool_input.get("documento_id", "")
        if verbose:
            print(f"  -> leer_serie_de_documento_aportado: {documento_id} hoja={tool_input.get('hoja')}")
        archivo = await obtener_archivo_original_de_documento_aportado(documento_id, tenant=_TENANT)
        if "error" in archivo:
            return archivo
        return _leer_serie_de_excel_fn(
            archivo_b64=archivo["archivo_original_b64"], hoja=tool_input.get("hoja", ""),
            columna_fecha=tool_input.get("columna_fecha", ""), columna_valor=tool_input.get("columna_valor", ""),
            header_fila=tool_input.get("header_fila", 0),
            filtro_columna=tool_input.get("filtro_columna"), filtro_valor=tool_input.get("filtro_valor"),
        )
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
    if nombre == "search_uniprot":
        query = tool_input.get("query", "")
        if verbose:
            print(f"  -> search_uniprot: {query[:80]}")
        try:
            return _search_uniprot_fn(query=query, organism=tool_input.get("organism"), max_results=tool_input.get("max_results", 5))
        except Exception as exc:
            return {"error": str(exc), "query": query}
    if nombre == "search_bacdive":
        organism = tool_input.get("organism", "")
        if verbose:
            print(f"  -> search_bacdive: {organism[:80]}")
        try:
            return _search_bacdive_fn(organism=organism, max_results=tool_input.get("max_results", 5))
        except Exception as exc:
            return {"error": str(exc), "organism": organism}
    if nombre == "search_pubmed":
        query = tool_input.get("query", "")
        if verbose:
            print(f"  -> search_pubmed: {query[:80]}")
        try:
            return _search_pubmed_fn(query=query, max_results=tool_input.get("max_results", 20))
        except Exception as exc:
            return {"error": str(exc), "query": query}
    if nombre == "analizar_estabilidad_serie":
        if verbose:
            print(f"  -> analizar_estabilidad_serie: {len(tool_input.get('datos', []))} puntos")
        return _analizar_estabilidad_fn(
            datos=tool_input.get("datos", []),
            umbral_estable=tool_input.get("umbral_estable", 15.0),
            umbral_variable=tool_input.get("umbral_variable", 30.0),
        )
    if nombre == "detectar_cambios_de_regimen":
        if verbose:
            print(f"  -> detectar_cambios_de_regimen: {len(tool_input.get('datos', []))} puntos")
        return _detectar_cambios_de_regimen_fn(
            datos=tool_input.get("datos", []), periodo=tool_input.get("periodo", "M"),
        )
    if nombre == "correlacion_con_desfase":
        if verbose:
            print(f"  -> correlacion_con_desfase: x={len(tool_input.get('serie_x', []))} y={len(tool_input.get('serie_y', []))} puntos")
        return _correlacion_con_desfase_fn(
            serie_x=tool_input.get("serie_x", []), serie_y=tool_input.get("serie_y", []),
            ventana_dias=tool_input.get("ventana_dias", 7), lag_max_dias=tool_input.get("lag_max_dias", 90),
        )
    if nombre == "comparar_fuentes_de_datos":
        if verbose:
            print(f"  -> comparar_fuentes_de_datos: {tool_input.get('nombre_a', 'A')} vs {tool_input.get('nombre_b', 'B')}")
        return _comparar_fuentes_fn(
            serie_a=tool_input.get("serie_a", []), serie_b=tool_input.get("serie_b", []),
            nombre_a=tool_input.get("nombre_a", "A"), nombre_b=tool_input.get("nombre_b", "B"),
        )
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
    """
    Loop agéntico compartido entre run_agent (oportunidad) y run_agent_desde_frente (frente) —
    no sabe ni le importa cuál de los dos lo llamó, ni persiste nada al KM. `identificador` es
    solo para el TokenTracker (bookkeeping, no se persiste en to_dict()).

    Returns: (informe_markdown, evaluacion_dict, lecciones_caso, tracker)
    """
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

    # El write-back del resultado (props.microbiologo o documento_caso) NO es responsabilidad de
    # este agente — lo hace la costura (orquestador/invocador.py::invocar_agente), siempre.

    if verbose:
        recomienda = especialista.get("si_no", False)
        print(f"\n  {len(evaluacion_tecnica.get('enfoques_tecnicos_identificados', []))} enfoques identificados")
        if recomienda:
            print(f"  Especialista adicional recomendado: {especialista.get('descripcion', '')[:100]}")
        else:
            print("  Sin especialista adicional recomendado.")

    return informe, evaluacion_dict, lecciones_auto, tracker


async def run_agent(
    oportunidad_id: str,
    verbose: bool = False,
    model: str = DEFAULT_MODEL,
    tarea: str | None = None,
    contexto_extra: str | None = None,
    foco: str | None = None,
) -> tuple[str, dict, list[str]]:
    """
    Corre el Especialista Microbiólogo contra una oportunidad (modelo viejo, área
    descubrimiento).

    Returns:
        (informe_markdown, evaluacion_dict, lecciones_caso)
        No escribe al KM — eso lo hace la costura (orquestador/invocador.py).
    """
    if verbose:
        print(f"\n{'='*60}\n  ESPECIALISTA MICROBIÓLOGO — CRIZA\n  Modelo: {model}\n{'='*60}\n")

    oportunidad_dict = await motor_api.obtener(oportunidad_id, tenant=_TENANT)
    if not oportunidad_dict:
        raise ValueError(f"Oportunidad {oportunidad_id} no encontrada en el KM")

    await _preflight()

    await aprendizaje.ensure_area(tenant=_TENANT)
    bloque = await aprendizaje.bloque_lecciones_para_prompt(
        agente=_AGENTE,
        consulta=(oportunidad_dict.get("props") or {}).get("descripcion") or oportunidad_id,
        tenant=_TENANT,
    )
    system_blocks = [{
        "type": "text",
        "text": SYSTEM_PROMPT + bloque,
        "cache_control": {"type": "ephemeral"},
    }]
    user_input = build_input(oportunidad_id, oportunidad_dict) + _bloque_instruccion(
        tarea, contexto_extra, foco
    )

    informe, evaluacion_dict, lecciones_auto, tracker = await _run_loop(
        oportunidad_id, system_blocks, user_input, model, verbose
    )

    existing_tu = (oportunidad_dict.get("props") or {}).get("token_usage") or {}
    existing_tu[_AGENTE] = tracker.to_dict()
    await motor_api.actualizar_props(oportunidad_id, {"token_usage": existing_tu}, tenant=_TENANT)

    return informe, evaluacion_dict, lecciones_auto


async def run_agent_desde_frente(
    frente_id: str,
    verbose: bool = False,
    model: str = DEFAULT_MODEL,
    tarea: str | None = None,
    contexto_extra: str | None = None,
    foco: str | None = None,
) -> tuple[str, dict, list[str]]:
    """
    Corre el Especialista Microbiólogo contra un frente del modelo de casos.yaml — Etapa 4 del
    plan de construcción (2026-08-16). Ver microbiologo_agent/docs/DESIGN_GATE.md decisión G.

    Returns:
        (informe_markdown, evaluacion_dict, lecciones_caso)
        No escribe al KM — eso lo hace la costura (orquestador/invocador.py::invocar_agente),
        que para frente_id persiste un documento_caso conectado vía frente_produce_documento en
        vez de props[prop_key] (que solo existe para oportunidad).
    """
    if verbose:
        print(f"\n{'='*60}\n  ESPECIALISTA MICROBIÓLOGO — CRIZA (frente)\n  Modelo: {model}\n{'='*60}\n")

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
    user_input = build_input_desde_frente(
        frente_dict, caso_dict, pendientes, documentos_aportados, documentos_producidos
    ) + _bloque_instruccion(tarea, contexto_extra, foco)

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
    """Interfaz de contrato estándar para el Orquestador (SEB-115). Wraps run_agent() o
    run_agent_desde_frente() según qué venga en conocimiento — ver INPUT_CONTRACT."""
    conocimiento = contract_input.get("conocimiento") or {}
    oportunidad_id = conocimiento.get("oportunidad_id") if isinstance(conocimiento, dict) else None
    frente_id = conocimiento.get("frente_id") if isinstance(conocimiento, dict) else None

    if not oportunidad_id and not frente_id:
        raise ValueError(
            "Especialista Microbiólogo requiere 'oportunidad_id' o 'frente_id' en contract_input['conocimiento']"
        )
    if oportunidad_id and frente_id:
        raise ValueError(
            "Especialista Microbiólogo: 'oportunidad_id' y 'frente_id' son mutuamente excluyentes"
        )

    kwargs = dict(
        verbose=verbose,
        model=model,
        tarea=contract_input.get("tarea") or None,
        contexto_extra=contract_input.get("contexto") or None,
        foco=contract_input.get("caso") or None,
    )
    if frente_id:
        informe, evaluacion, lecciones = await run_agent_desde_frente(frente_id, **kwargs)
    else:
        informe, evaluacion, lecciones = await run_agent(oportunidad_id, **kwargs)

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


# ── Chat conversacional (Etapa 10, 2026-08-16) ─────────────────────────────────
#
# Distinto de run()/run_agent_desde_frente() (contrato SEB-115, un turno, termina en
# submit_evaluacion_tecnica, la costura persiste un documento_caso) — esto es para que Sebas
# pueda CONVERSAR con el especialista (preguntar, pedir que profundice, cuestionar un enfoque)
# sin que cada intercambio dispare una evaluación formal. TOOLS_CHAT excluye
# submit_evaluacion_tecnica a propósito: el chat da acceso al mismo conocimiento/herramientas,
# pero la evaluación formal persistida sigue siendo exclusivamente responsabilidad del camino de
# un turno vía la costura (mismo principio de "nunca bypasear la costura" que ya rige el
# Conductor) — si Sebas quiere el documento formal, se lo pide al Conductor.

TOOLS_CHAT = [t for t in TOOLS if t["name"] != "submit_evaluacion_tecnica"]


async def iniciar_sesion(frente_id: str, *, tenant: str = _TENANT) -> list[dict]:
    """Arma el primer mensaje de una sesión de chat contra un frente — mismo contexto que
    run_agent_desde_frente() arma para una corrida de un turno (build_input_desde_frente),
    pero acá arranca una conversación en vez de forzar una evaluación formal."""
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
    Un turno de chat con el Especialista Microbiólogo. `messages` se muta y se devuelve, mismo
    patrón que `conductor.enviar_mensaje()`.

    `frente_id=None` es el modo "consulta libre" (Etapa 12, 2026-08-16) — Sebas pidió poder
    hacerle una pregunta puntual al especialista sin necesitar un caso/frente ya creado (y sin
    pagar el costo de armar ese contexto). Con `frente_id`, `messages` debe arrancar con lo que
    devolvió `iniciar_sesion(frente_id)` (modo caso/frente, sin cambios).
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
        # sin caso, la pregunta en sí es la mejor consulta para lecciones análogas —
        # más específica que cualquier descripción de caso genérica.
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
