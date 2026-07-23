"""
Tools de escritura: guardar corridas, oportunidades, aprendizajes y fuentes externas.
Todas retornan dict estándar: {success, data, error}
"""

import json
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, text

from km_models import (
    Aprendizaje, CorridaDocumento, CorridaOportunidad,
    Corrida, Documento, Oportunidad,
)
from knowledge_module.db import get_session_factory
from knowledge_module.embeddings import get_embedder


async def store_corrida(
    sector: str,
    agente: str,
    modo: str,
    fecha: str,              # ISO format: "2026-06-08"
    modelo: str,
    tokens_input: Optional[int] = None,
    tokens_output: Optional[int] = None,
    costo_usd: Optional[float] = None,
    notas: Optional[str] = None,
) -> dict:
    """Guarda el registro de una ejecución del agente divergente o convergente."""
    try:
        async with get_session_factory()() as session:
            corrida = Corrida(
                sector=sector,
                agente=agente,
                modo=modo,
                fecha=date.fromisoformat(fecha),
                modelo=modelo,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                costo_usd=costo_usd,
                notas=notas,
            )
            session.add(corrida)
            await session.commit()
            await session.refresh(corrida)
            return {
                "success": True,
                "data": {"id": str(corrida.id), "sector": corrida.sector},
                "error": None,
            }
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}


async def store_opportunity(
    sector: str,
    idea: str,
    prioridad: str,
    origen: str = "agente",
    corrida_id: Optional[str] = None,
    gaps_pendientes: Optional[str] = None,
) -> dict:
    """
    Guarda una oportunidad nueva o incrementa veces_detectada si ya existe
    (misma idea en el mismo sector, detectada por similitud semántica ≥ 0.92).

    Si se pasa corrida_id, crea la arista PRODUCE entre la corrida y la oportunidad.
    """
    try:
        embedder = get_embedder()
        embedding = embedder.embed(f"{sector}: {idea}")

        async with get_session_factory()() as session:
            # ── Buscar duplicado semántico ───────────────────────────────
            from pgvector.sqlalchemy import Vector
            from sqlalchemy import cast, func, text

            # cosine distance < 0.08 ≈ similitud > 0.92
            existing = await session.execute(
                select(Oportunidad)
                .where(Oportunidad.sector == sector)
                .order_by(
                    Oportunidad.embedding.cosine_distance(embedding)
                )
                .limit(1)
            )
            existing_op = existing.scalar_one_or_none()

            # Verificar si el más cercano supera el umbral
            if existing_op is not None and existing_op.embedding is not None:
                import numpy as np
                v1 = np.array(existing_op.embedding)
                v2 = np.array(embedding)
                cosine_sim = float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
                if cosine_sim >= 0.92:
                    # Incrementar contador de detecciones
                    existing_op.veces_detectada += 1
                    if gaps_pendientes:
                        existing_op.gaps_pendientes = gaps_pendientes
                    await session.commit()
                    await session.refresh(existing_op)

                    # Crear arista si se pasa corrida_id
                    if corrida_id:
                        await _link_corrida(session, corrida_id, str(existing_op.id), prioridad)

                    return {
                        "success": True,
                        "data": {
                            "id": str(existing_op.id),
                            "action": "incremented",
                            "veces_detectada": existing_op.veces_detectada,
                            "similitud": round(cosine_sim, 3),
                        },
                        "error": None,
                    }

            # ── Oportunidad nueva ────────────────────────────────────────
            op = Oportunidad(
                sector=sector,
                idea=idea,
                prioridad=prioridad,
                origen=origen,
                gaps_pendientes=gaps_pendientes,
                embedding=embedding,
            )
            session.add(op)
            await session.commit()
            await session.refresh(op)

            if corrida_id:
                await _link_corrida(session, corrida_id, str(op.id), prioridad)

            return {
                "success": True,
                "data": {"id": str(op.id), "action": "created"},
                "error": None,
            }

    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}


async def store_document(
    corrida_id: str,
    contenido: str,
    sector: str,
    agente: str,
    fecha: str,
    modelo: str,
    tipo: str = "analisis",
    titulo: Optional[str] = None,
    tenant_id: str = "criza",
) -> dict:
    """
    Guarda el output completo de una corrida como nodo Documento.
    Crea la arista GENERA (Corrida → Documento) automáticamente.

    Permite recuperar el análisis completo si las Oportunidades extraídas pierden contexto.
    """
    try:
        async with get_session_factory()() as session:
            doc = Documento(
                tenant_id=tenant_id,
                tipo=tipo,
                titulo=titulo,
                contenido=contenido,
                agente=agente,
                sector=sector,
                fecha=date.fromisoformat(fecha),
                modelo=modelo,
            )
            session.add(doc)
            await session.commit()
            await session.refresh(doc)

            # Arista GENERA
            edge = CorridaDocumento(
                corrida_id=UUID(corrida_id),
                documento_id=doc.id,
            )
            session.add(edge)
            await session.commit()

            return {
                "success": True,
                "data": {"id": str(doc.id), "tipo": doc.tipo, "sector": doc.sector},
                "error": None,
            }
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}


async def store_fuente_externa(
    titulo: str,
    contenido: str,                     # abstract / resumen
    fuente_url: str,                    # handle URL — clave de dedup
    sector: str,
    fecha: str,                         # año de publicación, ej. "2023"
    tipo: str = "paper",
    autores: Optional[list[str]] = None,
    subjects: Optional[list[str]] = None,
    texto_completo: Optional[str] = None,
    doi: Optional[str] = None,
    tenant_id: str = "criza",
) -> dict:
    """
    Guarda un documento de fuente externa (paper INTA, norma DPN, etc.) en el KM.

    Idempotente: si ya existe un documento con el mismo fuente_url retorna
    {action: "skipped"} sin insertar duplicado.

    Args:
        titulo:          Título del documento.
        contenido:       Abstract o resumen — lo que el agente lee para evaluar relevancia.
        fuente_url:      URL canónica del documento (handle, URL de norma, etc.). Clave de dedup.
        sector:          Sector temático (ej. "Biotecnología agrícola").
        fecha:           Año de publicación como string ISO (ej. "2023" o "2023-06-01").
        tipo:            "paper" | "reporte" | "norma" | "patente" | "otro".
        autores:         Lista de autores.
        subjects:        Lista de keywords/subjects (idealmente términos AGROVOC).
        texto_completo:  Texto extraído del PDF (opcional).
        doi:             DOI del documento (opcional).
        tenant_id:       Instancia del KM ("criza", "dpn", etc.).

    Returns:
        dict con {success, data: {id, action}, error}
        action: "created" | "skipped"
    """
    try:
        from sqlalchemy import select

        async with get_session_factory()() as session:
            # Dedup por fuente_url
            existing = await session.execute(
                select(Documento).where(Documento.fuente_url == fuente_url)
            )
            existing_doc = existing.scalar_one_or_none()
            if existing_doc is not None:
                return {
                    "success": True,
                    "data": {"id": str(existing_doc.id), "action": "skipped"},
                    "error": None,
                }

            # Normalizar fecha: "2023" → "2023-01-01"
            fecha_normalizada = fecha.strip()
            if len(fecha_normalizada) == 4:
                fecha_normalizada = f"{fecha_normalizada}-01-01"
            elif len(fecha_normalizada) == 7:
                fecha_normalizada = f"{fecha_normalizada}-01"

            doc = Documento(
                tenant_id=tenant_id,
                tipo=tipo,
                titulo=titulo,
                contenido=contenido or "",
                texto_completo=texto_completo,
                autores=json.dumps(autores or [], ensure_ascii=False),
                subjects=json.dumps(subjects or [], ensure_ascii=False),
                agente="harvest",
                sector=sector,
                fecha=date.fromisoformat(fecha_normalizada),
                modelo="n/a",
                fuente_url=fuente_url,
                doi=doi,
            )
            session.add(doc)
            await session.commit()
            await session.refresh(doc)

            return {
                "success": True,
                "data": {"id": str(doc.id), "action": "created"},
                "error": None,
            }

    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}


async def batch_store_fuentes_externas(
    records: list[dict],
    tenant_id: str = "criza",
) -> dict:
    """
    Persiste múltiples documentos usando INSERT ... ON CONFLICT DO NOTHING (atómico).

    Cada record en la lista debe tener:
      titulo, contenido, fuente_url, sector, fecha (str ISO o año)
    Campos opcionales: tipo, autores (list), subjects (list), texto_completo, doi.

    Returns:
        {success, data: {created, skipped, errors}, error}
    """
    if not records:
        return {"success": True, "data": {"created": 0, "skipped": 0, "errors": 0}, "error": None}

    try:
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from uuid import uuid4

        # 1 — Dedup intra-batch (INTA incluye el mismo handle en múltiples sets del CICVyA umbrella)
        seen: dict = {}
        for r in records:
            url = r.get("fuente_url")
            if url and url not in seen:
                seen[url] = r

        # 2 — Preparar rows
        rows = []
        errors = 0
        for r in seen.values():
            try:
                fecha_str = str(r["fecha"]).strip()
                if len(fecha_str) == 4:
                    fecha_str = f"{fecha_str}-01-01"
                elif len(fecha_str) == 7:
                    fecha_str = f"{fecha_str}-01"
                rows.append({
                    "id": uuid4(),
                    "tenant_id": tenant_id,
                    "tipo": r.get("tipo", "paper"),
                    "titulo": r["titulo"],
                    "contenido": r.get("contenido") or "",
                    "texto_completo": r.get("texto_completo"),
                    "autores": json.dumps(r.get("autores") or [], ensure_ascii=False),
                    "subjects": json.dumps(r.get("subjects") or [], ensure_ascii=False),
                    "agente": "harvest",
                    "sector": r["sector"],
                    "fecha": date.fromisoformat(fecha_str),
                    "modelo": "n/a",
                    "fuente_url": r["fuente_url"],
                    "doi": r.get("doi"),
                })
            except Exception:
                errors += 1

        if not rows:
            return {"success": True, "data": {"created": 0, "skipped": len(records), "errors": errors}, "error": None}

        # 3 — INSERT ON CONFLICT DO NOTHING: atómico, idempotente, sin race conditions
        #     El índice parcial uq_documento_fuente_url cubre (fuente_url) WHERE fuente_url IS NOT NULL
        async with get_session_factory()() as session:
            stmt = (
                pg_insert(Documento)
                .values(rows)
                .on_conflict_do_nothing(
                    index_elements=["fuente_url"],
                    index_where=text("fuente_url IS NOT NULL"),
                )
                .returning(Documento.id)
            )
            result = await session.execute(stmt)
            await session.commit()
            created = len(result.fetchall())

        skipped = len(records) - created - errors
        return {
            "success": True,
            "data": {"created": created, "skipped": skipped, "errors": errors},
            "error": None,
        }

    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}


async def _link_corrida(session, corrida_id: str, oportunidad_id: str, prioridad: str):
    """Crea la arista PRODUCE si no existe."""
    link = CorridaOportunidad(
        corrida_id=UUID(corrida_id),
        oportunidad_id=UUID(oportunidad_id),
        prioridad_corrida=prioridad,
    )
    session.add(link)
    try:
        await session.commit()
    except Exception:
        await session.rollback()  # ya existe el link (UNIQUE constraint) — ok


async def store_learning(
    contenido: str,
    tipo: str,
    fuente: str = "agente_destilacion",
    nivel_confianza: float = 0.5,
    origen_nombre: Optional[str] = None,
) -> dict:
    """
    Guarda un aprendizaje (patrón, error, señal de decisión).
    Si ya existe uno muy similar (similitud ≥ 0.92), incrementa su nivel de confianza.
    """
    try:
        embedder = get_embedder()
        embedding = embedder.embed(contenido)

        async with get_session_factory()() as session:
            # Buscar duplicado semántico
            existing = await session.execute(
                select(Aprendizaje)
                .where(Aprendizaje.tipo == tipo)
                .order_by(Aprendizaje.embedding.cosine_distance(embedding))
                .limit(1)
            )
            existing_ap = existing.scalar_one_or_none()

            if existing_ap is not None and existing_ap.embedding is not None:
                import numpy as np
                v1 = np.array(existing_ap.embedding)
                v2 = np.array(embedding)
                cosine_sim = float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
                if cosine_sim >= 0.92:
                    existing_ap.veces_confirmado += 1
                    existing_ap.nivel_confianza = min(
                        1.0, existing_ap.nivel_confianza + 0.1
                    )
                    existing_ap.ultima_vez_relevante = date.today()
                    await session.commit()
                    return {
                        "success": True,
                        "data": {
                            "id": str(existing_ap.id),
                            "action": "reinforced",
                            "nivel_confianza": existing_ap.nivel_confianza,
                            "veces_confirmado": existing_ap.veces_confirmado,
                        },
                        "error": None,
                    }

            ap = Aprendizaje(
                contenido=contenido,
                tipo=tipo,
                fuente=fuente,
                nivel_confianza=nivel_confianza,
                origen_nombre=origen_nombre,
                ultima_vez_relevante=date.today(),
                embedding=embedding,
            )
            session.add(ap)
            await session.commit()
            await session.refresh(ap)
            return {
                "success": True,
                "data": {"id": str(ap.id), "action": "created"},
                "error": None,
            }

    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
