"""
Investigación Amplia v2.0 — CRIZA

Análisis EXHAUSTIVO del sector para identificar blue oceans.
Diferencia clave vs v1.0:
  - Lee TODO el corpus INTA del sector (sin límite de 10), no muestrea
  - Lee corpus CONICET (semantic search, limit=100)
  - Usa texto completo para determinar TRL de candidatos
  - Aborta si fuentes críticas no están disponibles (objective-first)
  - Demanda es primary source; web scraping es solo para actores comerciales

Ver docs/DESIGN_GATE.md para decisiones de diseño.
"""

import asyncio
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
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
from tools.search import get_paper_full_text as _get_paper_full_text_fn
from tools.search import get_ficha_full_text as _get_ficha_full_text_fn
from utils.agrovoc import expand_term as _expand_agrovoc_fn
from motor import api as motor_api
import aprendizaje
from utils.token_tracker import TokenTracker
from preflight import FuenteCheck, FuenteCheckResult, run_preflight
from db import get_session_factory
from sqlalchemy import text as _sql_text

DEFAULT_MODEL = os.getenv("INVESTIGACION_MODEL", "claude-sonnet-4-6")
_AGENTE = "investigacion_amplia"
_TENANT = "criza"
_FETCH_TIMEOUT = 10
_CONICET_MIN_FICHAS = 100

# Documentos compartidos — cargados en runtime para que cualquier cambio en el archivo
# se aplique automáticamente sin modificar código (mismo patrón que el Armador con el spec).
_MARCO = (_CRIZA_DIR / "docs" / "marco_blue_ocean_CRIZA.md").read_text(encoding="utf-8")
_METODOLOGIA = (_CRIZA_DIR / "docs" / "metodologia_busqueda_AGENTE.md").read_text(encoding="utf-8")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fetch_page_text(url: str, max_chars: int = 8000) -> dict:
    """Descarga una URL y retorna el texto plano (sin HTML)."""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; CRIZA-bot/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT) as resp:
            raw = resp.read(max_chars * 4).decode("utf-8", errors="replace")
        import re
        text = re.sub(r"<[^>]+>", " ", raw)
        text = re.sub(r"\s{3,}", "\n\n", text)
        return {"success": True, "url": url, "text": text[:max_chars]}
    except Exception as exc:
        return {"success": False, "url": url, "error": str(exc)}


async def _search_corpus_cientifico_fn(
    consulta: str, repositorio: list[str] | None = None, limit: int = 100
) -> dict:
    """Busca semánticamente en corpus_cientifico (CONICET, INTA y futuras fuentes).
    repositorio: opcional, acota a uno o más repositorios (ej. ["INTA"])."""
    try:
        filtro = {"repositorio": repositorio} if repositorio else None
        resultados = await motor_api.buscar(
            area="corpus_cientifico",
            consulta=consulta,
            tipo="fuente",
            limit=limit,
            tenant=_TENANT,
            filtro=filtro,
        )
        papers = []
        repos_encontrados = set()
        for r in resultados:
            props = r.get("props", {})
            repo = props.get("repositorio", "")
            repos_encontrados.add(repo)
            papers.append({
                "titulo": props.get("titulo", ""),
                "abstract": (props.get("abstract", "") or "")[:1000],
                "autores": props.get("autores", ""),
                "anio": props.get("anio", ""),
                "url": props.get("url", ""),
                "repositorio": repo,
            })
        return {
            "success": True,
            "total": len(papers),
            "papers": papers,
            "source": f"corpus_cientifico ({', '.join(sorted(repos_encontrados)) or 'sin resultados'})",
        }
    except Exception as exc:
        return {"success": False, "total": 0, "papers": [], "error": str(exc)}


async def _fetch_full_text_fn(doc_id: str, tenant_id: str = "criza") -> dict:
    """
    Texto completo por ID, sin importar de qué tabla salió — el agente puede recibir IDs
    de get_sector_corpus (documento, INTA legacy) o de search_corpus_cientifico
    (ficha/corpus_cientifico, CONICET+INTA nuevo) y no tiene por qué saber cuál es cuál.
    Prueba documento primero (INTA), después ficha (CONICET+INTA vía download_corpus_pdfs.py).
    """
    result = await _get_paper_full_text_fn(doc_id=doc_id, tenant_id=tenant_id)
    if result.get("success"):
        return result
    return await _get_ficha_full_text_fn(ficha_id=doc_id, tenant_id=tenant_id)


# ── Pre-flight check ──────────────────────────────────────────────────────────
#
# Usa el módulo genérico knowledge_module/preflight.py — generalizado en 2026-07-02 a
# partir de la versión inline que tenía este mismo agente (era el origen del patrón, pero
# había quedado sin migrar cuando market_agent/evidence_generalista/armador sí lo adoptaron
# — gap encontrado por el auditor, ver knowledge_module/docs/AUDITOR_DESIGN_GATE.md).

async def _check_inta_corpus_sector(terminos_sector: list[str]) -> FuenteCheckResult:
    """INTA corpus para el sector — bloqueante: nuestra fuente primaria."""
    inta = await _get_sector_corpus_fn(terminos_sector, tenant_id=_TENANT)
    inta_total = inta.get("data", {}).get("total", 0) if inta.get("success") else 0
    if inta_total == 0:
        return FuenteCheckResult(
            ok=False,
            detalle=(
                f"0 documentos para términos {terminos_sector[:5]}. "
                "Posible causa: términos incorrectos o sector sin cobertura en CICVyA."
            ),
        )
    return FuenteCheckResult(ok=True, detalle=f"{inta_total} documentos", conteo=inta_total)


async def _check_corpus_cientifico() -> FuenteCheckResult:
    """corpus_cientifico (CONICET+INTA) — bloqueante: requerimiento explícito."""
    async with get_session_factory()() as s:
        r = await s.execute(_sql_text(
            "SELECT COUNT(*) FROM ficha f "
            "JOIN tipo_ficha tf ON tf.id = f.tipo_ficha_id "
            "JOIN area a ON a.id = tf.area_id "
            "WHERE a.nombre = 'corpus_cientifico' AND a.tenant_id = :t"
        ), {"t": _TENANT})
        conicet_count = r.scalar() or 0
    if conicet_count < _CONICET_MIN_FICHAS:
        return FuenteCheckResult(
            ok=False,
            detalle=(
                f"{conicet_count} fichas (mínimo {_CONICET_MIN_FICHAS}). Harvest en progreso o "
                "no ejecutado. Ejecutar: cd knowledge_module && python ingesta/ingest_corpus.py "
                "--config ../criza/config/connectors/conicet.yaml"
            ),
            conteo=conicet_count,
        )
    return FuenteCheckResult(ok=True, detalle=f"{conicet_count} fichas", conteo=conicet_count)


async def _check_openalex() -> FuenteCheckResult:
    """OpenAlex — no bloqueante (servicio externo, puede volver)."""
    try:
        test = _search_literature_fn("cattle bovine Argentina", max_results=1)
        if isinstance(test, dict) and test.get("error"):
            return FuenteCheckResult(ok=False, detalle=str(test["error"])[:120])
        return FuenteCheckResult(ok=True, detalle="reachable")
    except Exception as exc:
        return FuenteCheckResult(ok=False, detalle=str(exc)[:120])


# ── Tool definitions ──────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "expand_agrovoc",
        "description": (
            "Expande un término contra el tesauro AGROVOC de la FAO.\n"
            "Retorna prefLabel ES/EN + broader/narrower/related.\n"
            "USAR PRIMERO: obtener todos los términos ES/EN del sector antes de "
            "buscar en el corpus. Los términos AGROVOC son exactamente los que "
            "INTA usa para indexar su material."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "term": {
                    "type": "string",
                    "description": "Término en español o inglés a expandir.",
                }
            },
            "required": ["term"],
        },
    },
    {
        "name": "get_sector_corpus",
        "description": (
            "Retorna TODOS los papers del corpus INTA Digital del sector (sin límite).\n"
            "Usa lógica OR: cualquier documento que contenga alguno de los términos.\n"
            "USAR DESPUÉS DE expand_agrovoc con todos los términos obtenidos.\n"
            "REGLA CRÍTICA: si total=0 → STOP, no continuás la investigación.\n"
            "Procesar TODOS los documentos retornados — nunca hacer muestras."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "terminos": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Lista de términos del sector en ES y EN "
                        "(ej: ['bovinos', 'cattle', 'bovina', 'ganado', 'vacuno']). "
                        "Términos individuales — NO frases completas."
                    ),
                }
            },
            "required": ["terminos"],
        },
    },
    {
        "name": "search_corpus_cientifico",
        "description": (
            "Busca semánticamente en corpus_cientifico: CONICET + INTA (y futuras fuentes, ej. CREA).\n"
            "Retorna papers relevantes por similitud semántica (hasta 100), cada uno con su campo "
            "'repositorio' indicando de dónde salió.\n"
            "REGLA: si total=0 → registrar como fuente no disponible y continuar.\n"
            "Complementa get_sector_corpus (FTS exhaustivo sobre INTA) con búsqueda semántica ranqueada."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "consulta": {
                    "type": "string",
                    "description": "Sector o problema a buscar. Puede ser en ES o EN.",
                },
                "repositorio": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Opcional. Acota la búsqueda a uno o más organismos (ej. [\"INTA\"] o "
                        "[\"INTA\", \"CONICET\"]). Omitir para buscar en todos."
                    ),
                },
            },
            "required": ["consulta"],
        },
    },
    {
        "name": "fetch_paper_full_text",
        "description": (
            "Retorna el texto completo de un paper — funciona con IDs de get_sector_corpus "
            "(INTA) Y de search_corpus_cientifico (CONICET+INTA), no hace falta saber de "
            "cuál de los dos salió el ID.\n"
            "OBLIGATORIO para TODO candidato de prioridad alta antes de asignarle "
            "estado_de_desarrollo — no es un paso opcional 'si el agente lo considera "
            "necesario'. TRL requiere leer Métodos y Resultados, no está en el abstracto.\n"
            "Si texto_completo no está disponible (ver error del tool), estado_de_desarrollo "
            "queda 'a-confirmar' — pero eso se declara en cobertura_texto_completo, no se omite en silencio."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "doc_id": {
                    "type": "string",
                    "description": "ID del documento (campo 'id' de get_sector_corpus o search_corpus_cientifico).",
                }
            },
            "required": ["doc_id"],
        },
    },
    {
        "name": "search_literature",
        "description": (
            "Busca en literatura científica global via OpenAlex (250M+ papers).\n"
            "Usar DESPUÉS de analizar el corpus INTA/CONICET para validar:\n"
            "  (a) si hay actividad internacional en el espacio del candidato\n"
            "  (b) qué soluciones existen globalmente (señal de competencia)\n"
            "Buscar en inglés. Si da error: registrar como no disponible y continuar."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Búsqueda en inglés."},
                "max_results": {"type": "integer", "default": 15},
            },
            "required": ["query"],
        },
    },
    {
        "name": "fetch_page_text",
        "description": (
            "Descarga el texto de una URL.\n"
            "Usar SOLO para mapear actores comerciales (SENASA, INPI, catálogos de productos).\n"
            "NO usar para descubrir candidatos — eso viene del corpus científico.\n"
            "NO usar páginas de medios de prensa. Solo fuentes institucionales."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL a descargar."},
            },
            "required": ["url"],
        },
    },
    {
        "name": "submit_investigacion_amplia",
        "description": (
            "ÚNICO output del agente. Llamar al completar el workflow.\n"
            "El informe_completo DEBE incluir:\n"
            "  - Estado de cada fuente: INTA (N papers), CONICET (M papers), OpenAlex\n"
            "  - Cobertura total: X papers leídos en el sector\n"
            "  - Para cada candidato: TRL si fue determinado con texto completo\n"
            "  - Gaps de información declarados explícitamente"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "cruce_3": {
                    "type": "object",
                    "description": "Panorama competitivo del sector/recurso.",
                    "properties": {
                        "qué_existe": {
                            "type": "string",
                            "description": "Descripción narrativa de qué soluciones/actores existen.",
                        },
                        "registros": {
                            "type": "object",
                            "properties": {
                                "SENASA": {"type": "array", "items": {"type": "string"}},
                                "patentes": {"type": "array", "items": {"type": "string"}},
                            },
                        },
                        "intensidad": {
                            "type": "string",
                            "enum": ["vacío", "débil", "fuerte"],
                        },
                        "evidencia": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "competidor": {"type": "string"},
                                    "descripción": {"type": "string"},
                                    "estado": {
                                        "type": "string",
                                        "enum": ["establecido", "asumido", "a-confirmar"],
                                    },
                                    "fuente": {"type": "string"},
                                },
                                "required": ["competidor", "descripción", "estado"],
                            },
                        },
                    },
                    "required": ["qué_existe", "intensidad"],
                },
                "mapa_candidatos": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "candidato": {"type": "string"},
                            "señal_demanda": {"type": "string"},
                            "señal_competencia": {"type": "string"},
                            "intensidad_competencia": {
                                "type": "string",
                                "enum": ["vacío", "débil", "fuerte"],
                            },
                            "estado_de_desarrollo": {
                                "type": "string",
                                "enum": ["idea", "lab", "piloto", "comercial", "a-confirmar"],
                                "description": "TRL del estado del arte: idea/lab/piloto/comercial. a-confirmar si no se pudo determinar del texto completo.",
                            },
                            "prioridad": {
                                "type": "string",
                                "enum": ["alta", "media", "baja"],
                            },
                            "estado": {
                                "type": "string",
                                "enum": ["establecido", "asumido", "a-confirmar"],
                            },
                            "papers_fuente": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "IDs o títulos de los papers que evidencian este candidato.",
                            },
                        },
                        "required": ["candidato", "señal_demanda", "intensidad_competencia", "prioridad", "estado", "estado_de_desarrollo"],
                    },
                },
                "cobertura_texto_completo": {
                    "type": "object",
                    "description": (
                        "Obligatorio — cuántos candidatos de prioridad alta tuvieron su texto completo "
                        "efectivamente leído (fetch_paper_full_text exitoso) antes de asignarles "
                        "estado_de_desarrollo. No es opcional 'si el agente lo consideró necesario' — "
                        "es la condición para que estado_de_desarrollo no sea una adivinanza sobre el "
                        "abstract (orchestration-layer.md Decisión 6)."
                    ),
                    "properties": {
                        "candidatos_alta_prioridad": {"type": "integer"},
                        "con_texto_completo_leido": {"type": "integer"},
                        "motivo_si_incompleto": {
                            "type": ["string", "null"],
                            "description": "Por qué con_texto_completo_leido < candidatos_alta_prioridad, si aplica (ej. sin PDF disponible).",
                        },
                    },
                    "required": ["candidatos_alta_prioridad", "con_texto_completo_leido"],
                },
                "gaps_prioritarios": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Gaps de información pendientes. Incluir fuentes no disponibles.",
                },
                "informe_completo": {
                    "type": "string",
                    "description": (
                        "Narrativa completa del análisis en markdown. DEBE incluir:\n"
                        "## Fuentes y cobertura\n"
                        "  - INTA: N papers analizados (de M en el corpus)\n"
                        "  - CONICET: X papers analizados / No disponible (motivo)\n"
                        "  - OpenAlex: disponible/no disponible\n"
                        "## Corpus del sector\n"
                        "  Síntesis de lo que el corpus revela sobre el sector\n"
                        "## Candidatos identificados\n"
                        "  Candidatos con evidencia, fuente, TRL cuando aplica\n"
                        "## Panorama competitivo\n"
                        "## Gaps y pendientes"
                    ),
                },
                "fuentes_y_cobertura": {
                    "type": "object",
                    "description": (
                        "Qué fuentes se consultaron y con qué cobertura — obligatorio "
                        "(orchestration-layer.md Decisión 6). Complementa cobertura_texto_completo "
                        "(que mide lectura de texto completo de candidatos) declarando cobertura a "
                        "nivel fuente: INTA, corpus_cientifico (CONICET+INTA), OpenAlex como mínimo."
                    ),
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
                },
            },
            "required": ["cruce_3", "mapa_candidatos", "informe_completo", "cobertura_texto_completo", "fuentes_y_cobertura"],
        },
    },
]


# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    _MARCO
    + "\n\n---\n\n"
    + _METODOLOGIA
    + "\n\n"
    + "> **Nota sobre entrega:** el espíritu del análisis y los pasos 1-4 de la metodología aplican "
    + "íntegramente. El mecanismo de entrega (Paso 5) es `submit_investigacion_amplia` — no la lista "
    + "de 7 ítems del divergente. El formato de las lentes y los criterios de evaluación son los mismos.\n\n"
    + "---\n\n"
    + """Sos el Agente de Investigación Amplia de CRIZA v2.0.

TU OBJETIVO: Identificar blue oceans en un sector mediante análisis EXHAUSTIVO del corpus científico argentino (INTA + CONICET) + literatura global. Un blue ocean es raro — es una aguja en un pajar. No podés encontrarla si ves el 10% del pajar.

PRINCIPIO FUNDAMENTAL — OBJETIVO-PRIMERO:
Si no tenés datos, no analizás. Si una fuente crítica falla o retorna vacío → STOP, reportás el bloqueo y llamás submit_investigacion_amplia explicando por qué no pudiste completar el análisis. Un expediente vacío con motivo claro es mejor que un análisis basado en información insuficiente.

PRINCIPIO SECUNDARIO — TECNOLOGÍA ES UNA VARIABLE:
Describí soluciones en términos de qué hacen (mecanismo, resultado), nunca en términos de qué tecnología usan. No asumas qué tecnología resuelve el problema.

═══════════════════════════════════════════════════════════
WORKFLOW OBLIGATORIO — seguir en este orden exacto
═══════════════════════════════════════════════════════════

PASO 1 — EXPANSIÓN AGROVOC (1-2 llamadas a expand_agrovoc)
  Expandí el sector recibido + 1-2 sinónimos obvios en ES/EN.
  Objetivo: construir la lista completa de términos ES/EN que INTA usa para indexar.
  Ejemplo para "ganadería bovina": expandir "bovinos" y "cattle" por separado.
  Armá una lista de términos INDIVIDUALES (no frases) para el paso siguiente.

PASO 2 — CORPUS INTA COMPLETO (1 llamada a get_sector_corpus)
  Llamá con la lista completa de términos individuales de AGROVOC.
  La respuesta incluye TODOS los papers del sector — leélos TODOS sin excepción.
  ▶ Si total=0 → STOP inmediato. Llamá submit_investigacion_amplia reportando el bloqueo.
  ▶ Si total>0 → procesá todos los documentos antes de continuar al paso 3.
    Anotá: cuántos hay, cuántos tienen texto completo, qué tipo de material son.

PASO 3 — CORPUS CIENTÍFICO COMPLEMENTARIO (1 llamada a search_corpus_cientifico)
  El paso 2 ya cubrió INTA exhaustivamente — NO lo repitas acá.
  Llamá con repositorio=["CONICET"] (u otras fuentes que se sumen a futuro, ej. CREA) para
  traer literatura que get_sector_corpus no cubre. Evita releer los mismos papers dos veces
  y evita costo de búsqueda innecesario sobre una fuente ya agotada.
  ▶ Si total=0 → registrá "CONICET no disponible" en gaps_prioritarios y continuá.
  ▶ Si total>0 → procesá todos los papers retornados.

PASO 4 — ANÁLISIS INTEGRAL DEL CORPUS (sin tools, solo razonamiento)
  Con todos los abstracts de INTA y CONICET leídos:
  a) Identificá DOLORES RECURRENTES: problemas que aparecen en múltiples papers sin solución publicada
  b) Identificá ESTADO DEL ARTE: qué está investigado, en qué TRL (idea/lab/piloto/comercial)
  c) Identificá AUSENCIAS: temas del sector que NO aparecen en el corpus (señal de gap real o falta de interés científico)
  d) Identificá CANDIDATOS POTENCIALES: dolores con señal de demanda + gap en solución
  NO impongas categorías previas. Los patrones emergen de los datos.

PASO 5 — TEXTO COMPLETO PARA TODOS LOS CANDIDATOS DE PRIORIDAD ALTA (obligatorio, no selectivo)
  Esto NO es "si te parece necesario" — es un paso obligatorio del workflow, igual que
  leer el corpus completo en el paso 2. El abstract no alcanza para decidir TRL — confiar
  en él para un candidato de prioridad alta es la misma sesgo de muestreo que ya se
  corrigió en la búsqueda del corpus.
  Para CADA candidato que vaya a quedar con prioridad="alta":
    1. Llamá fetch_paper_full_text sobre el/los paper(s) que lo evidencian (papers_fuente).
    2. Leé el texto completo para determinar estado_de_desarrollo:
       idea = hipótesis sin experimento validado
       lab = validado en laboratorio/in vitro
       piloto = escala piloto / ensayo de campo
       comercial = producto/servicio en el mercado
    3. Si fetch_paper_full_text falla (texto no disponible) → estado_de_desarrollo =
       "a-confirmar", PERO tenés que haber intentado la llamada — no es válido asumir
       que no está disponible sin pedirlo.
  Al final de este paso, contá candidatos_alta_prioridad y con_texto_completo_leido —
  van directo a cobertura_texto_completo en submit_investigacion_amplia. Si no coinciden,
  declará motivo_si_incompleto — no lo dejes en silencio.

PASO 6 — LITERATURA GLOBAL (2-4 llamadas a search_literature)
  Para cada candidato identificado, buscá en inglés:
    - Actividad internacional (¿hay grupos investigando lo mismo?)
    - Soluciones existentes globalmente (señal de competencia)
  ▶ Si OpenAlex da error → registrá "OpenAlex no disponible" y continuá.

PASO 7 — ACTORES COMERCIALES (1-3 llamadas a fetch_page_text, solo si necesario)
  Solo para verificar existencia de competidores formales: SENASA, INPI, catálogos.
  No para descubrir candidatos — ese trabajo ya está hecho con el corpus.

PASO 8 — SUBMIT (1 llamada a submit_investigacion_amplia)
  El informe_completo DEBE declarar:
  - Estado de cada fuente (disponible/no disponible + N papers procesados)
  - Cobertura total del corpus
  - Para cada candidato: evidencia del corpus, TRL cuando determinado, fuente
  - Gaps explícitos con instrucción de dónde confirmar
  Además del informe narrativo, declará SIEMPRE fuentes_y_cobertura como campo estructurado
  (obligatorio, orchestration-layer.md Decisión 6): INTA, corpus_cientifico (CONICET+INTA) y
  OpenAlex como mínimo, con unidades_procesadas y de_un_total. No es redundante con el texto
  del informe — el informe es para lectura humana, fuentes_y_cobertura es lo que lee el
  Armador para calcular cobertura_global sin tener que parsear markdown.

═══════════════════════════════════════════════════════════
VERACIDAD POR DATO (obligatorio en cada afirmación)
═══════════════════════════════════════════════════════════
  establecido: lo dice la fuente, citás título/ID de paper o URL
  asumido: inferencia razonable del corpus, aclarás el peso
  a-confirmar: gap real, aclarás exactamente dónde confirmar

SOBRE PRIORIDAD ALTA:
Un candidato es alta prioridad si cumple las condiciones del marco blue ocean (cargado arriba).
Para evaluar con el corpus disponible:
  ✓ El corpus evidencia un dolor real del cliente (condición 1 del marco)
  ✓ Competencia vacía o débil — nadie lo resuelve bien en el mercado objetivo (condición 11)
  ✓ TRL = idea o lab — hay actividad científica pero sin solución comercial accesible (condición 5)
  ✗ Sustitución de importación → DESCARTAR siempre, sin excepción (condición 12)
Las 12 condiciones must son el filtro completo. Para cada candidato declarar:
  - Cuáles se verificaron con el corpus (establecido + fuente)
  - Cuáles quedan a-confirmar (con dónde confirmar)
  - Si alguna falla con evidencia → el candidato se descarta, no se prioriza bajo.
"""
)


# ── Contrato estándar (SEB-115) ───────────────────────────────────────────────

INPUT_CONTRACT = {
    "agent": "investigacion_amplia",
    "version": "2.1",
    "fields": {
        "caso": "Sector o planta/recurso a mapear (texto libre, ej: 'porcicultura', 'semillas de girasol')",
        "tarea": "Análisis exhaustivo del corpus científico del sector para identificar blue oceans.",
        "contexto": "Opcional — outputs de agentes anteriores para orientar el mapeo",
        "conocimiento": "Opcional — {'oportunidad_id': str} para linkear el análisis al KM",
        "herramientas": [
            "expand_agrovoc",
            "get_sector_corpus",
            "search_corpus_cientifico",
            "fetch_paper_full_text",
            "search_literature",
            "fetch_page_text",
            "submit_investigacion_amplia",
        ],
    },
}

OUTPUT_CONTRACT = {
    "agent": "investigacion_amplia",
    "version": "2.1",
    # Ver market_agent.OUTPUT_CONTRACT — contrato de conexión verificado por el auditor.
    "km_escribe": ["props.investigacion_amplia", "props.investigacion_amplia_informe"],
    "fields": {
        "análisis": "{'informe': str, 'resultado': {'cruce_3': dict, 'mapa_candidatos': list, 'gaps_prioritarios': list, 'fuentes_y_cobertura': dict}}",
        "nivel_confianza": "'alto' | 'medio' | 'bajo'",
        "recomendaciones": "mapa_candidatos ordenados por prioridad (alta → baja)",
        "próximo_agente": "'mercado' si hay ≥1 candidato alta-prioridad, else None",
        "nuevo_conocimiento": "lecciones_caso",
    },
}


# ── Input builder ─────────────────────────────────────────────────────────────

def build_input(caso: str, oportunidad_dict: dict | None) -> str:
    secciones = []
    if oportunidad_dict:
        props = oportunidad_dict.get("props") or {}
        nombre = oportunidad_dict.get("nombre") or props.get("nombre") or caso
        descripcion = props.get("descripcion") or ""
        secciones.append(
            f"# Sector / Recurso a mapear\n\n**Nombre:** {nombre}\n\n{descripcion}"
        )
    else:
        secciones.append(f"# Sector / Recurso a mapear\n\n{caso}")

    secciones.append(
        "---\n"
        "Tu tarea: análisis EXHAUSTIVO del corpus científico para identificar blue oceans.\n"
        "Seguí el workflow obligatorio en orden: AGROVOC → corpus INTA → CONICET → "
        "análisis → texto completo → literatura global → submit.\n"
        "Si get_sector_corpus retorna 0 documentos → STOP y reportá el bloqueo."
    )
    return "\n\n".join(secciones)


# ── Agentic loop ──────────────────────────────────────────────────────────────

def _bloque_instruccion(tarea: str | None, contexto_extra: str | None) -> str:
    """Instrucción propia de ESTA invocación — ver market_agent._bloque_instruccion.

    Acá no hay `foco`: para este agente el `caso` ES el input principal (el sector a
    mapear) y sí se lee. Solo faltaban `tarea` y `contexto` del contrato.
    """
    partes = []
    if tarea:
        partes.append(f"TAREA ESPECÍFICA DE ESTA INVOCACIÓN:\n{tarea}")
    if contexto_extra:
        partes.append(f"CONTEXTO ADICIONAL PROVISTO POR QUIEN TE INVOCA:\n{contexto_extra}")
    return ("\n\n" + "\n\n".join(partes)) if partes else ""


async def run_agent(
    caso: str,
    oportunidad_id: str | None = None,
    verbose: bool = False,
    model: str = DEFAULT_MODEL,
    tarea: str | None = None,
    contexto_extra: str | None = None,
) -> tuple[str, dict, list[str]]:
    """
    Corre el Agente de Investigación Amplia v2.0.

    Pre-flight check verifica fuentes antes de arrancar.
    Aborta si INTA=0 docs o CONICET<100 fichas.

    Returns: (informe_markdown, resultado_dict, lecciones_caso)
    """
    client = anthropic.Anthropic()

    if verbose:
        print(f"\n{'='*60}\n  INVESTIGACIÓN AMPLIA v2.0 — CRIZA\n  Modelo: {model}\n{'='*60}\n")

    oportunidad_dict = None
    if oportunidad_id:
        oportunidad_dict = await motor_api.obtener(oportunidad_id, tenant=_TENANT)
        if not oportunidad_dict:
            raise ValueError(f"Oportunidad {oportunidad_id} no encontrada en el KM")

    # ── Pre-flight: verificar fuentes críticas ────────────────────────────────
    sector_terminos = caso.lower().split()[:6]
    preflight = await run_preflight([
        FuenteCheck("INTA corpus", bloqueante=True,
                    check_fn=lambda: _check_inta_corpus_sector(sector_terminos)),
        FuenteCheck("corpus_cientifico (CONICET+INTA)", bloqueante=True,
                    check_fn=_check_corpus_cientifico),
        FuenteCheck("OpenAlex", bloqueante=False, check_fn=_check_openalex),
    ])

    if verbose:
        for adv in preflight.advertencias:
            print(f"  ⚠️  {adv}")
        if not preflight.ok:
            print("❌ PRE-FLIGHT FALLIDO — Fuentes bloqueantes:")
            for e in preflight.bloqueantes:
                print(f"  • {e}")
        else:
            print("  ✅ Pre-flight OK\n")

    if not preflight.ok:
        raise RuntimeError(
            "Pre-flight bloqueante — Investigación Amplia no puede continuar:\n"
            + "\n".join(preflight.bloqueantes)
        )

    # ── Tracker + aprendizaje ─────────────────────────────────────────────────
    tracker = TokenTracker(
        agent=_AGENTE,
        oportunidad_id=oportunidad_id or caso[:40],
        model=model,
    )
    await aprendizaje.ensure_area(tenant=_TENANT)
    bloque = await aprendizaje.bloque_lecciones_para_prompt(
        agente=_AGENTE,
        consulta=caso,
        tenant=_TENANT,
    )
    effective_system = SYSTEM_PROMPT + bloque
    # Prompt caching — ver market_agent.py. SYSTEM_PROMPT acá son ~18K chars (carga
    # marco_blue_ocean + metodologia_busqueda en runtime) reenviados en cada vuelta.
    system_blocks = [{
        "type": "text",
        "text": effective_system,
        "cache_control": {"type": "ephemeral"},
    }]
    user_input = build_input(caso, oportunidad_dict) + _bloque_instruccion(tarea, contexto_extra)
    messages = [{"role": "user", "content": user_input}]
    resultado_final = None

    # ── Loop agéntico ─────────────────────────────────────────────────────────
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

        if verbose:
            tool_names = [b.name for b in response.content if b.type == "tool_use"]
            print(
                f"  [{tracker.calls}] stop={response.stop_reason} | "
                f"in={response.usage.input_tokens} out={response.usage.output_tokens}"
            )
            for name in tool_names:
                print(f"  -> {name}")

        # max_tokens NO es terminación normal: la respuesta viene cortada y los
        # bloques tool_use de este turno nunca se procesan. Si todavía no capturamos
        # el resultado, fallar ruidoso — un mapa truncado no se persiste como válido.
        if response.stop_reason == "max_tokens" and not resultado_final:
            raise RuntimeError(
                "Respuesta truncada por max_tokens antes de submit_investigacion_amplia "
                f"(max_tokens=16000, output={response.usage.output_tokens}). "
                "La investigación está incompleta."
            )

        if response.stop_reason in ("end_turn", "max_tokens"):
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                if block.name == "submit_investigacion_amplia":
                    resultado_final = block.input
                    if verbose:
                        print("  -> submit_investigacion_amplia [capturado]\n")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps({"success": True, "message": "Investigación registrada."}),
                    })

                elif block.name == "expand_agrovoc":
                    term = block.input.get("term", "")
                    try:
                        expanded = _expand_agrovoc_fn(term)
                        content = (
                            json.dumps(expanded, ensure_ascii=False, indent=2)
                            if expanded
                            else json.dumps({"found": False, "term": term})
                        )
                    except Exception as exc:
                        content = json.dumps({"error": str(exc), "term": term})
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": content,
                    })

                elif block.name == "get_sector_corpus":
                    terminos = block.input.get("terminos", [])
                    result = await _get_sector_corpus_fn(terminos=terminos, tenant_id=_TENANT)
                    if verbose:
                        total = result.get("data", {}).get("total", 0) if result.get("success") else 0
                        con_texto = result.get("data", {}).get("docs_con_texto_completo", 0) if result.get("success") else 0
                        print(f"     → {total} docs ({con_texto} con texto completo)")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False, indent=2),
                    })

                elif block.name == "search_corpus_cientifico":
                    consulta = block.input.get("consulta", "")
                    repositorio = block.input.get("repositorio") or None
                    result = await _search_corpus_cientifico_fn(consulta=consulta, repositorio=repositorio)
                    if verbose:
                        total = result.get("total", 0)
                        print(f"     → {total} papers ({result.get('source', '')})")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False, indent=2),
                    })

                elif block.name == "fetch_paper_full_text":
                    doc_id = block.input.get("doc_id", "")
                    result = await _fetch_full_text_fn(doc_id=doc_id, tenant_id=_TENANT)
                    if verbose:
                        if result.get("success"):
                            chars = len(result.get("data", {}).get("texto_completo", ""))
                            print(f"     → {chars:,} chars de texto completo")
                        else:
                            print(f"     → sin texto: {result.get('error', '')[:60]}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False, indent=2),
                    })

                elif block.name == "search_literature":
                    query = block.input.get("query", "")
                    try:
                        lit_result = _search_literature_fn(
                            query=query,
                            max_results=block.input.get("max_results", 15),
                        )
                        content = json.dumps(lit_result, ensure_ascii=False, indent=2)
                    except Exception as exc:
                        content = json.dumps({"error": str(exc), "available": False})
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": content,
                    })

                elif block.name == "fetch_page_text":
                    url = block.input.get("url", "")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(
                            _fetch_page_text(url), ensure_ascii=False, indent=2
                        ),
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

            if resultado_final:
                break
        else:
            break

    # ── Persistir tokens ──────────────────────────────────────────────────────
    tracker.log(verbose)
    if oportunidad_id and oportunidad_dict is not None:
        existing_tu = (oportunidad_dict.get("props") or {}).get("token_usage") or {}
        existing_tu[_AGENTE] = tracker.to_dict()
        await motor_api.actualizar_props(oportunidad_id, {"token_usage": existing_tu}, tenant=_TENANT)

    if resultado_final is None:
        raw = "".join(b.text for b in response.content if hasattr(b, "text"))
        return raw or "El agente no llamó submit_investigacion_amplia.", {}, []

    informe = resultado_final.get("informe_completo", "")
    cruce_3 = resultado_final.get("cruce_3", {})
    mapa = resultado_final.get("mapa_candidatos", [])
    gaps = resultado_final.get("gaps_prioritarios", [])
    lecciones_auto = resultado_final.get("lecciones_caso") or []

    cobertura_texto_completo = resultado_final.get("cobertura_texto_completo") or {
        "candidatos_alta_prioridad": 0, "con_texto_completo_leido": 0,
    }
    fuentes_y_cobertura = resultado_final.get("fuentes_y_cobertura") or {
        "fuentes_consultadas": [],
        "cobertura_declarada": "parcial-por-falla-de-fuente",
    }

    resultado_dict = {
        "cruce_3": cruce_3,
        "mapa_candidatos": mapa,
        "cobertura_texto_completo": cobertura_texto_completo,
        "fuentes_y_cobertura": fuentes_y_cobertura,
        "gaps_prioritarios": gaps,
        "agente": _AGENTE,
        "version": "2.1",
        "fecha": date.today().isoformat(),
        "modelo": model,
        "informe_completo": informe,
    }

    if oportunidad_id:
        await motor_api.actualizar_props(
            oportunidad_id,
            {
                "investigacion_amplia": resultado_dict,
                "investigacion_amplia_informe": informe,
            },
            tenant=_TENANT,
        )

    if verbose:
        intensidad = cruce_3.get("intensidad", "?")
        n_candidatos = len(mapa)
        alta_prio = [c for c in mapa if c.get("prioridad") == "alta"]
        print(f"\n  KM actualizado — intensidad cruce_3: {intensidad}")
        print(f"  Candidatos: {n_candidatos} total, {len(alta_prio)} de alta prioridad")
        if alta_prio:
            top = alta_prio[0]
            trl = top.get("estado_de_desarrollo", "?")
            print(f"  Top candidato [{trl}]: {top.get('candidato', '')[:80]}")

    return informe, resultado_dict, lecciones_auto


# ── Interfaz de contrato estándar (SEB-115) ───────────────────────────────────

def _derive_confidence(resultado: dict) -> str:
    cruce_3 = resultado.get("cruce_3") or {}
    intensidad = cruce_3.get("intensidad", "a-confirmar")
    mapa = resultado.get("mapa_candidatos") or []
    establecidos = [c for c in mapa if c.get("estado") == "establecido"]

    # Si hay candidatos de prioridad alta pero ninguno tuvo su texto completo leído,
    # el TRL es una adivinanza sobre el abstract — no puede ser "alto" (Decisión 6).
    cobertura = resultado.get("cobertura_texto_completo") or {}
    alta_prio = cobertura.get("candidatos_alta_prioridad", 0)
    leidos = cobertura.get("con_texto_completo_leido", 0)
    trl_sin_sustento = alta_prio > 0 and leidos == 0

    if not trl_sin_sustento and intensidad != "a-confirmar" and len(establecidos) >= 3:
        return "alto"
    if intensidad in ("vacío", "débil", "fuerte") or len(establecidos) >= 1:
        return "medio"
    return "bajo"


async def run(
    contract_input: dict,
    verbose: bool = False,
    model: str = DEFAULT_MODEL,
) -> dict:
    """Interfaz de contrato estándar para el Orquestador (SEB-115)."""
    caso = contract_input.get("caso") or ""
    conocimiento = contract_input.get("conocimiento") or {}
    oportunidad_id = conocimiento.get("oportunidad_id") if isinstance(conocimiento, dict) else None

    if not caso and not oportunidad_id:
        raise ValueError("Investigación Amplia requiere 'caso' (texto libre) o 'oportunidad_id' en conocimiento")

    informe, resultado, lecciones = await run_agent(
        caso=caso,
        oportunidad_id=oportunidad_id,
        verbose=verbose,
        model=model,
        tarea=contract_input.get("tarea") or None,
        contexto_extra=contract_input.get("contexto") or None,
    )

    mapa = resultado.get("mapa_candidatos") or []
    alta_prio = [c["candidato"] for c in mapa if c.get("prioridad") == "alta"]

    return {
        "análisis": {
            "informe": informe,
            "resultado": {
                "cruce_3": resultado.get("cruce_3"),
                "mapa_candidatos": mapa,
                "gaps_prioritarios": resultado.get("gaps_prioritarios", []),
            },
        },
        "nivel_confianza": _derive_confidence(resultado),
        "recomendaciones": sorted(
            mapa,
            key=lambda c: {"alta": 0, "media": 1, "baja": 2}.get(c.get("prioridad", "baja"), 2),
        ),
        "próximo_agente": "mercado" if alta_prio else None,
        "nuevo_conocimiento": lecciones,
    }


# ── CLI para prueba manual ────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Investigación Amplia v2.0 — CRIZA")
    parser.add_argument("caso", help="Sector o planta/recurso a mapear")
    parser.add_argument("--oportunidad-id", help="UUID de oportunidad en el KM (opcional)")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    async def main():
        informe, resultado, lecciones = await run_agent(
            caso=args.caso,
            oportunidad_id=args.oportunidad_id,
            verbose=args.verbose,
            model=args.model,
        )
        print("\n" + "=" * 60)
        print("INFORME\n" + "=" * 60)
        print(informe)
        print("\n" + "=" * 60)
        print("CRUCE 3")
        print(json.dumps(resultado.get("cruce_3"), ensure_ascii=False, indent=2))
        print("\nCANDIDATOS")
        for c in resultado.get("mapa_candidatos", []):
            trl = c.get("estado_de_desarrollo", "?")
            print(f"  [{c.get('prioridad','?').upper()}][{trl}] {c.get('candidato','')}")

    asyncio.run(main())
