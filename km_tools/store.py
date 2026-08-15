"""
Tools de escritura: guardar fuentes externas (papers INTA/CONICET, normas, etc.).
Todas retornan dict estándar: {success, data, error}

`store_corrida`/`store_opportunity`/`store_document`/`store_learning` (pipeline scout/agente
divergente/convergente) se archivaron el 2026-08-15 — ver `_archivo_temporal/` y
`docs/progress/2026-08-15.md`.
"""

import json
from datetime import date
from typing import Optional

from sqlalchemy import select, text

from km_models import Documento
from knowledge_module.db import get_session_factory


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
