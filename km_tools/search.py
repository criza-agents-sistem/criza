"""
Tools de búsqueda sobre el Knowledge Module:
  - search_knowledge: búsqueda semántica (oportunidades + aprendizajes)
  - search_fuentes_externas: búsqueda FTS sobre documentos cosechados (papers INTA, normas, etc.)
  - get_sector_corpus: OR FTS exhaustivo (sin límite) para análisis de sector completo
  - get_paper_full_text: texto completo de un paper del corpus INTA por ID
"""

import json
import re
import unicodedata
from typing import Optional

from sqlalchemy import select, or_, text

from km_models import Aprendizaje, Documento, Oportunidad
from knowledge_module.db import get_session_factory
from knowledge_module.embeddings import get_embedder


def _build_or_tsquery(terminos: list[str]) -> str | None:
    """
    Convierte lista de términos en un OR tsquery para PostgreSQL 'simple' config.
    Por cada término con acento agrega también la versión sin acento (simple dict es
    sensible a acentos). Filtra tokens de ≤2 chars.
    """
    tokens: set[str] = set()
    for term in terminos:
        for word in re.split(r"\s+", term.lower().strip()):
            clean = re.sub(r"[^\w]", "", word, flags=re.UNICODE)
            if len(clean) <= 2:
                continue
            tokens.add(clean)
            stripped = "".join(
                c for c in unicodedata.normalize("NFD", clean)
                if unicodedata.category(c) != "Mn"
            )
            if stripped != clean and len(stripped) > 2:
                tokens.add(stripped)
    if not tokens:
        return None
    return " | ".join(sorted(tokens))


async def search_knowledge(
    query: str,
    tipo: str = "all",        # "oportunidades" | "aprendizajes" | "all"
    sector: Optional[str] = None,
    limit: int = 5,
) -> dict:
    """
    Busca en el Knowledge Module por similitud semántica.

    - query: texto libre (dolor, sector, concepto)
    - tipo: qué buscar — oportunidades, aprendizajes, o ambos
    - sector: filtro opcional por sector
    - limit: máximo de resultados por tipo

    Retorna los resultados más relevantes con su similitud y contexto.
    """
    try:
        embedder = get_embedder()
        embedding = embedder.embed(query)

        results = []

        async with get_session_factory()() as session:

            # ── Oportunidades ───────────────────────────────────────────
            if tipo in ("oportunidades", "all"):
                q = (
                    select(Oportunidad)
                    .where(Oportunidad.embedding.is_not(None))
                    .where(Oportunidad.estado_analisis != "descartada")
                )
                if sector:
                    q = q.where(Oportunidad.sector.ilike(f"%{sector}%"))

                q = q.order_by(Oportunidad.embedding.cosine_distance(embedding)).limit(limit)

                rows = (await session.execute(q)).scalars().all()
                for op in rows:
                    import numpy as np
                    v1 = np.array(op.embedding)
                    v2 = np.array(embedding)
                    sim = float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
                    results.append({
                        "tipo": "oportunidad",
                        "id": str(op.id),
                        "sector": op.sector,
                        "idea": op.idea,
                        "prioridad": op.prioridad,
                        "estado": op.estado_analisis,
                        "veces_detectada": op.veces_detectada,
                        "gaps_pendientes": op.gaps_pendientes,
                        "similitud": round(sim, 3),
                    })

            # ── Aprendizajes ────────────────────────────────────────────
            if tipo in ("aprendizajes", "all"):
                q = (
                    select(Aprendizaje)
                    .where(Aprendizaje.embedding.is_not(None))
                    .order_by(Aprendizaje.embedding.cosine_distance(embedding))
                    .limit(limit)
                )
                rows = (await session.execute(q)).scalars().all()
                for ap in rows:
                    import numpy as np
                    v1 = np.array(ap.embedding)
                    v2 = np.array(embedding)
                    sim = float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
                    results.append({
                        "tipo": "aprendizaje",
                        "id": str(ap.id),
                        "contenido": ap.contenido,
                        "tipo_aprendizaje": ap.tipo,
                        "nivel_confianza": ap.nivel_confianza,
                        "veces_confirmado": ap.veces_confirmado,
                        "similitud": round(sim, 3),
                    })

        # Ordenar todos los resultados por similitud
        results.sort(key=lambda x: x["similitud"], reverse=True)

        return {
            "success": True,
            "data": {
                "query": query,
                "total": len(results),
                "results": results,
            },
            "error": None,
        }

    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}


async def get_sector_corpus(
    terminos: list[str],
    tenant_id: str = "criza",
) -> dict:
    """
    Retorna TODOS los documentos del corpus INTA que matchean cualquiera de los términos
    (lógica OR, sin límite). Para análisis exhaustivo del sector — no muestrea.

    Args:
        terminos: Lista de términos del sector en ES/EN (ej: ["bovinos", "cattle", "bovina"]).
                  Se procesan como OR: cualquier documento que contenga alguno de ellos.
        tenant_id: Instancia del KM.

    Returns:
        {success, data: {terminos_buscados, total, docs_con_texto_completo,
          documentos: [{id, titulo, resumen, tipo, año, tiene_texto_completo,
          fuente_url, autores, subjects}]}, error}
    """
    tsq = _build_or_tsquery(terminos)
    if not tsq:
        return {"success": False, "data": None, "error": "Sin términos válidos para la búsqueda"}

    try:
        async with get_session_factory()() as session:
            sql = text("""
                SELECT
                    id::text,
                    titulo,
                    contenido,
                    fuente_url,
                    autores,
                    subjects,
                    fecha,
                    tipo,
                    (texto_completo IS NOT NULL AND texto_completo != '') AS tiene_texto_completo
                FROM documento
                WHERE tenant_id = :tenant
                  AND agente IN ('harvest', 'ingest')
                  AND fts_vector @@ to_tsquery('simple', :tsq)
                ORDER BY fecha DESC NULLS LAST
            """)
            rows = (await session.execute(sql, {"tenant": tenant_id, "tsq": tsq})).fetchall()

        documentos = []
        for r in rows:
            autores = []
            subjects = []
            try:
                autores = json.loads(r.autores) if r.autores else []
            except Exception:
                pass
            try:
                subjects = json.loads(r.subjects) if r.subjects else []
            except Exception:
                pass
            resumen = r.contenido or ""
            documentos.append({
                "id": r.id,
                "titulo": r.titulo,
                "resumen": resumen[:1200],
                "fuente_url": r.fuente_url,
                "autores": autores[:5],
                "subjects": subjects[:8],
                "año": r.fecha.year if r.fecha else None,
                "tipo": r.tipo,
                "tiene_texto_completo": bool(r.tiene_texto_completo),
            })

        docs_con_texto = sum(1 for d in documentos if d["tiene_texto_completo"])

        return {
            "success": True,
            "data": {
                "terminos_buscados": sorted(set(tsq.replace(" | ", "|").split("|"))),
                "total": len(documentos),
                "docs_con_texto_completo": docs_con_texto,
                "documentos": documentos,
            },
            "error": None,
        }

    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}


async def get_paper_full_text(
    doc_id: str,
    tenant_id: str = "criza",
) -> dict:
    """
    Retorna el texto completo de un paper del corpus INTA por su ID.
    Usar después de identificar candidatos en get_sector_corpus para determinar TRL.

    Args:
        doc_id: UUID del documento (campo 'id' de get_sector_corpus).
        tenant_id: Instancia del KM.

    Returns:
        {success, data: {id, titulo, fuente_url, tipo, texto_completo}, error}
    """
    try:
        async with get_session_factory()() as session:
            sql = text("""
                SELECT id::text, titulo, texto_completo, fuente_url, tipo
                FROM documento
                WHERE id::text = :doc_id AND tenant_id = :tenant
                  AND agente IN ('harvest', 'ingest')
            """)
            r = (await session.execute(sql, {"doc_id": doc_id, "tenant": tenant_id})).fetchone()

        if not r:
            return {
                "success": False,
                "data": None,
                "error": f"Documento {doc_id} no encontrado",
            }

        if not r.texto_completo:
            return {
                "success": False,
                "data": {"id": doc_id, "titulo": r.titulo, "fuente_url": r.fuente_url},
                "error": "Texto completo no disponible (PDF sin acceso abierto o no descargado)",
            }

        return {
            "success": True,
            "data": {
                "id": r.id,
                "titulo": r.titulo,
                "fuente_url": r.fuente_url,
                "tipo": r.tipo,
                "texto_completo": r.texto_completo,
            },
            "error": None,
        }

    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}


async def get_ficha_full_text(
    ficha_id: str,
    tenant_id: str = "criza",
) -> dict:
    """
    Retorna el texto completo de una ficha de corpus_cientifico (CONICET + INTA vía el
    motor nuevo, ver knowledge_module/ingesta/download_corpus_pdfs.py) por su ID.
    Complementa get_paper_full_text, que solo lee de la tabla `documento` legacy (INTA).

    Args:
        ficha_id: UUID de la ficha (campo 'id' de get_sector_corpus/search_corpus_cientifico).
        tenant_id: Instancia del KM.

    Returns:
        {success, data: {id, titulo, url, repositorio, texto_completo}, error}
    """
    try:
        async with get_session_factory()() as session:
            sql = text("""
                SELECT f.id::text AS id, f.props->>'titulo' AS titulo,
                       f.props->>'url' AS url, f.props->>'repositorio' AS repositorio,
                       f.props->>'texto_completo' AS texto_completo,
                       (f.props->>'requiere_solicitud')::boolean AS requiere_solicitud,
                       f.props->>'solicitud_url' AS solicitud_url
                FROM ficha f
                JOIN tipo_ficha tf ON tf.id = f.tipo_ficha_id
                JOIN area a ON a.id = tf.area_id
                WHERE f.id::text = :ficha_id AND a.nombre = 'corpus_cientifico'
                  AND a.tenant_id = :tenant AND tf.nombre = 'fuente'
            """)
            r = (await session.execute(sql, {"ficha_id": ficha_id, "tenant": tenant_id})).fetchone()

        if not r:
            return {
                "success": False,
                "data": None,
                "error": f"Ficha {ficha_id} no encontrada en corpus_cientifico",
            }

        if not r.texto_completo:
            # Declarar SIEMPRE el estado real, no un "no disponible" genérico —
            # dónde_confirmar es parte del dato, no un detalle opcional (veracidad por
            # dato, orchestration-layer.md Decisión 6). El material puede estar
            # disponible pidiéndolo, no solo "cerrado".
            if r.requiere_solicitud:
                if r.solicitud_url:
                    motivo = f"Requiere solicitud — formulario de acceso: {r.solicitud_url}"
                else:
                    motivo = "Requiere solicitud — sin autoservicio en la página, pedir por otra vía (ej. contacto en CONICET)"
            else:
                motivo = "Texto completo no disponible (sin bitstream detectado, o pendiente de descarga)"

            return {
                "success": False,
                "data": {
                    "id": r.id, "titulo": r.titulo, "url": r.url, "repositorio": r.repositorio,
                    "requiere_solicitud": bool(r.requiere_solicitud),
                    "solicitud_url": r.solicitud_url,
                },
                "error": motivo,
            }

        return {
            "success": True,
            "data": {
                "id": r.id,
                "titulo": r.titulo,
                "url": r.url,
                "repositorio": r.repositorio,
                "texto_completo": r.texto_completo,
            },
            "error": None,
        }

    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}


async def search_fuentes_externas(
    query: str,
    sector: Optional[str] = None,
    tipo: Optional[str] = None,     # "paper" | "reporte" | "norma" | "patente" | "otro"
    agente: Optional[str] = None,   # "harvest" | "ingest" (default: todos los externos)
    limit: int = 10,
    tenant_id: str = "criza",
) -> dict:
    """
    Busca sobre documentos externos cosechados en el KM (papers INTA, normas DPN, etc.)
    usando PostgreSQL full-text search (índice GIN sobre fts_vector).

    El índice cubre título + abstract + subjects — sin necesidad de embeddings.
    Retorna resultados ordenados por relevancia (ts_rank).

    Args:
        query:     Texto libre. Soporta operadores: "garrapata biocontrol", "virus AND vacuna".
        sector:    Filtro opcional (ej. "Biotecnología agrícola").
        tipo:      Filtro opcional ("paper", "reporte", "norma", etc.).
        agente:    Filtro por origen. Default: todos (harvest + ingest).
        limit:     Máximo de resultados (default 10).
        tenant_id: Instancia del KM.

    Returns:
        {success, data: {query, total, results: [{id, titulo, abstract, fuente_url,
          autores, subjects, año, tipo, rank}]}, error}
    """
    try:
        async with get_session_factory()() as session:
            # websearch_to_tsquery soporta: "garrapata biocontrol", "control OR manejo", etc.
            # 'simple' es agnóstico al idioma (bien para mezcla ES/EN de INTA)
            params: dict = {"query": query, "tenant": tenant_id, "lim": limit}

            where_clauses = [
                "fts_vector @@ websearch_to_tsquery('simple', :query)",
                "tenant_id = :tenant",
                "agente IN ('harvest', 'ingest')",
            ]

            if sector:
                where_clauses.append("sector ILIKE :sector")
                params["sector"] = f"%{sector}%"
            if tipo:
                where_clauses.append("tipo = :tipo")
                params["tipo"] = tipo
            if agente:
                where_clauses.pop()  # remove the generic agente IN clause
                where_clauses.append("agente = :agente")
                params["agente"] = agente

            sql = text(f"""
                SELECT
                    id::text,
                    titulo,
                    contenido,
                    fuente_url,
                    autores,
                    subjects,
                    fecha,
                    tipo,
                    ts_rank(fts_vector, websearch_to_tsquery('simple', :query)) AS rank
                FROM documento
                WHERE {" AND ".join(where_clauses)}
                ORDER BY rank DESC
                LIMIT :lim
            """)

            rows = (await session.execute(sql, params)).fetchall()

        results = []
        for r in rows:
            autores = []
            subjects = []
            try:
                autores = json.loads(r.autores) if r.autores else []
            except Exception:
                pass
            try:
                subjects = json.loads(r.subjects) if r.subjects else []
            except Exception:
                pass

            results.append({
                "id": r.id,
                "titulo": r.titulo,
                "abstract": r.contenido,
                "fuente_url": r.fuente_url,
                "autores": autores,
                "subjects": subjects,
                "año": r.fecha.year if r.fecha else None,
                "tipo": r.tipo,
                "rank": round(float(r.rank), 4),
            })

        return {
            "success": True,
            "data": {
                "query": query,
                "total": len(results),
                "results": results,
            },
            "error": None,
        }

    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
