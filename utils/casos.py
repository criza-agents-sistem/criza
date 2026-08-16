"""
Helpers de lectura del modelo de `casos.yaml` — CRIZA (Capa 2).

El mecanismo (área/tipo_ficha/conexion) es genérico del KM; el modelo concreto de "caso"/
"frente"/"pendiente" es específico de CRIZA (config/plantillas/casos.yaml) — por eso este
helper vive acá y no en knowledge_module.

Un `frente` no tiene su propio `caso_id` en props — la relación vive en la conexión
`tiene_frente` (desde=caso, hacia=frente). Para ir de frente → caso hace falta la dirección
"entrantes" de `conexiones_de`.
"""

from knowledge_module.motor import api as motor_api

_AREA = "casos"


async def obtener_frente_con_caso(frente_id: str, tenant: str) -> dict:
    """
    Trae un frente + el caso al que pertenece.

    Returns:
        {"frente": {...} | None, "caso": {...} | None}
        Ambos None si el frente no existe. `caso` None si el frente existe pero (estado
        inconsistente) no tiene conexión `tiene_frente` entrante — no debería pasar en uso
        normal, pero no se asume.
    """
    frente = await motor_api.obtener(frente_id, tenant=tenant)
    if not frente:
        return {"frente": None, "caso": None}

    entrantes = await motor_api.conexiones_de(
        frente_id, tipo_conexion="tiene_frente", direccion="entrantes", tenant=tenant
    )
    caso = entrantes[0] if entrantes else None
    return {"frente": frente, "caso": caso}


async def listar_casos(tenant: str, limit: int = 20) -> list[dict]:
    """Lista los casos existentes — para que un cliente (ej. el Conductor) pueda listar sin
    conocer IDs de antemano."""
    return await motor_api.listar(area=_AREA, tipo="caso", tenant=tenant, limit=limit)


async def obtener_frentes_de_caso(caso_id: str, tenant: str) -> list[dict]:
    return await motor_api.conexiones_de(
        caso_id, tipo_conexion="tiene_frente", direccion="salientes", tenant=tenant
    )


async def obtener_documentos_de_frente(frente_id: str, tenant: str) -> list[dict]:
    """Documentos (`documento_caso`) que un frente ya produjo — el análogo, para el modelo de
    `casos.yaml`, de "¿este step ya corrió?" que `orquestador.motor.inspeccionar_caso` responde
    para el modelo `oportunidad`+flow (ver docs/PROTOCOLO_LECTURA_CONDUCTOR.md, nota del paso 2:
    ambos modelos coexisten, no hay una sola función que vea los dos)."""
    return await motor_api.conexiones_de(
        frente_id, tipo_conexion="frente_produce_documento", direccion="salientes", tenant=tenant
    )


async def obtener_pendientes_de_caso(caso_id: str, tenant: str, solo_abiertos: bool = True) -> list[dict]:
    """
    Pendientes de un caso — cuelgan del caso completo, no de un frente específico
    (config/plantillas/casos.yaml, nota de diseño).
    """
    pendientes = await motor_api.conexiones_de(
        caso_id, tipo_conexion="tiene_pendiente", direccion="salientes", tenant=tenant
    )
    if solo_abiertos:
        pendientes = [p for p in pendientes if (p.get("props") or {}).get("estado") != "resuelto"]
    return pendientes


async def guardar_documento_de_frente(
    frente_id: str,
    titulo: str,
    contenido: str,
    tenant: str,
    analisis_estructurado: dict | None = None,
    agente: str | None = None,
    modo: str = "chat",
    estado: str = "borrador",
) -> dict:
    """
    Persiste el resultado de un especialista como `documento_caso`, conectado al frente que lo
    originó (`frente_produce_documento`). `analisis_estructurado`/`agente` no son campos
    declarados en la plantilla de `documento_caso` (solo titulo/modo/contenido/version/estado) —
    se guardan igual porque `props` es JSONB libre, mismo patrón que `token_usage` en
    `oportunidad` (tampoco declarado, siempre soportado).

    Returns: {"success": bool, "documento_id": str | None, "error": str | None}
    """
    doc = await motor_api.guardar_ficha(
        area=_AREA, tipo="documento_caso", tenant=tenant,
        campos={
            "titulo": titulo,
            "modo": modo,
            "contenido": contenido,
            "version": 1,
            "estado": estado,
            "analisis_estructurado": analisis_estructurado or {},
            "agente": agente,
        },
    )
    if not doc.get("success"):
        return {"success": False, "documento_id": None, "error": doc.get("error")}

    conexion = await motor_api.guardar_conexion(
        area=_AREA, tipo="frente_produce_documento",
        desde_ficha_id=frente_id, hacia_ficha_id=doc["id"], tenant=tenant,
    )
    if not conexion.get("success"):
        return {"success": False, "documento_id": doc["id"], "error": conexion.get("error")}

    return {"success": True, "documento_id": doc["id"], "error": None}
