"""
Tools de lectura: historial de oportunidades y actualización de estado.
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from km_models import CorridaOportunidad, Corrida, Oportunidad
from knowledge_module.db import get_session_factory


async def get_opportunity_history(oportunidad_id: str) -> dict:
    """
    Devuelve toda la historia de una oportunidad:
    en qué corridas apareció, con qué prioridad, y su estado actual.
    """
    try:
        async with get_session_factory()() as session:
            op = await session.get(Oportunidad, UUID(oportunidad_id))
            if not op:
                return {"success": False, "data": None, "error": "Oportunidad no encontrada"}

            # Corridas que la generaron
            links = (await session.execute(
                select(CorridaOportunidad)
                .where(CorridaOportunidad.oportunidad_id == UUID(oportunidad_id))
            )).scalars().all()

            corridas = []
            for link in links:
                corrida = await session.get(Corrida, link.corrida_id)
                if corrida:
                    corridas.append({
                        "corrida_id": str(corrida.id),
                        "sector": corrida.sector,
                        "fecha": str(corrida.fecha),
                        "agente": corrida.agente,
                        "modo": corrida.modo,
                        "prioridad_en_corrida": link.prioridad_corrida,
                    })

            return {
                "success": True,
                "data": {
                    "id": str(op.id),
                    "sector": op.sector,
                    "idea": op.idea,
                    "prioridad": op.prioridad,
                    "estado_analisis": op.estado_analisis,
                    "origen": op.origen,
                    "veces_detectada": op.veces_detectada,
                    "validaciones": op.validaciones,
                    "gaps_pendientes": op.gaps_pendientes,
                    "razon_descarte": op.razon_descarte,
                    "corridas": corridas,
                    "created_at": str(op.created_at),
                },
                "error": None,
            }
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}


async def update_opportunity(
    oportunidad_id: str,
    estado_analisis: Optional[str] = None,
    validaciones: Optional[str] = None,
    gaps_pendientes: Optional[str] = None,
    prioridad: Optional[str] = None,
    razon_descarte: Optional[str] = None,
) -> dict:
    """
    Actualiza el estado o datos de una oportunidad.
    Solo actualiza los campos que se pasan explícitamente.
    """
    try:
        async with get_session_factory()() as session:
            op = await session.get(Oportunidad, UUID(oportunidad_id))
            if not op:
                return {"success": False, "data": None, "error": "Oportunidad no encontrada"}

            if estado_analisis is not None:
                op.estado_analisis = estado_analisis
            if validaciones is not None:
                op.validaciones = validaciones
            if gaps_pendientes is not None:
                op.gaps_pendientes = gaps_pendientes
            if prioridad is not None:
                op.prioridad = prioridad
            if razon_descarte is not None:
                op.razon_descarte = razon_descarte

            await session.commit()
            await session.refresh(op)

            return {
                "success": True,
                "data": {
                    "id": str(op.id),
                    "estado_analisis": op.estado_analisis,
                    "prioridad": op.prioridad,
                },
                "error": None,
            }
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}
