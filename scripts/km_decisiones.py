"""
Decisiones de sistema — CRIZA (Capa 2)

Helper para registrar y leer decisiones de arquitectura/desarrollo de CRIZA en el KM
(área `decisiones_sistema`, ver config/plantillas/decisiones_sistema.yaml).

Nunca lo llaman los agentes especialistas — es de la capa Sebas+Claude construyendo CRIZA
(PROPUESTA_DESTINO.md §4), no de la capa de asesoramiento de casos.

Uso:
    from scripts.km_decisiones import registrar_decision, listar_decisiones_vigentes

    await registrar_decision(
        componente="orquestador",
        titulo="Registry data-driven + la costura",
        decision="...",
        alternativas_consideradas=["...", "..."],
        motivo="...",
        quien="Sebas + Claude",
    )
"""

from datetime import date, datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", override=True)

from knowledge_module.motor import api as motor_api

_TENANT = "criza"
_AREA = "decisiones_sistema"


async def registrar_decision(
    *,
    componente: str,
    titulo: str,
    decision: str,
    motivo: str,
    quien: str,
    alternativas_consideradas: list[str] | None = None,
    fecha: str | None = None,
    supera_id: str | None = None,
) -> dict:
    """
    Registra una decisión nueva. Si `supera_id` se pasa, la decisión vieja se marca
    `estado=superada` y queda conectada (tipo_conexion `supera`) — nunca se edita in-place.

    Returns: {"success": bool, "id": str, "error": str | None}.
    """
    alternativas = alternativas_consideradas or []
    fecha = fecha or date.today().isoformat()
    texto_busqueda = f"{titulo}. {decision}. {motivo}"

    campos = {
        "componente": componente,
        "titulo": titulo,
        "decision": decision,
        "alternativas_consideradas": alternativas,
        "motivo": motivo,
        "quien": quien,
        "estado": "vigente",
        "fecha": fecha,
        "texto_busqueda": texto_busqueda,
    }

    resultado = await motor_api.guardar_ficha(
        area=_AREA, tipo="decision", campos=campos, tenant=_TENANT,
    )
    if not resultado.get("success"):
        return resultado
    nueva_id = resultado["id"]

    if supera_id and nueva_id:
        await motor_api.actualizar_props(supera_id, {"estado": "superada"}, tenant=_TENANT)
        await motor_api.guardar_conexion(
            area=_AREA, tipo="supera",
            desde_ficha_id=nueva_id, hacia_ficha_id=supera_id,
            tenant=_TENANT,
        )

    return {"success": True, "id": nueva_id, "error": None}


async def listar_decisiones_vigentes(componente: str | None = None) -> list[dict]:
    """Todas las decisiones con estado=vigente, opcionalmente filtradas por componente."""
    contiene = {"estado": "vigente"}
    if componente:
        contiene["componente"] = componente
    fichas = await motor_api.listar(area=_AREA, tipo="decision", contiene=contiene, limit=500, tenant=_TENANT)
    decisiones = [f["props"] for f in fichas]
    decisiones.sort(key=lambda d: d.get("fecha", ""), reverse=True)
    return decisiones
