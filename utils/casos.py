"""
Helpers de lectura del modelo de `casos.yaml` — CRIZA (Capa 2).

El mecanismo (área/tipo_ficha/conexion) es genérico del KM; el modelo concreto de "caso"/
"frente"/"pendiente" es específico de CRIZA (config/plantillas/casos.yaml) — por eso este
helper vive acá y no en knowledge_module.

Un `frente` no tiene su propio `caso_id` en props — la relación vive en la conexión
`tiene_frente` (desde=caso, hacia=frente). Para ir de frente → caso hace falta la dirección
"entrantes" de `conexiones_de`.
"""

from sqlalchemy import text

from knowledge_module.db import get_session_factory
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
    ambos modelos coexisten, no hay una sola función que vea los dos).

    Ordenados por fecha de creación (ascendente) — a diferencia de `motor_api.conexiones_de`
    (que no ordena ni expone `created_at`), acá hace falta el orden real para poder identificar
    "el último informe de cada especialista" (Etapa 19, 2026-08-18: Sebas no podía saber cuál de
    los 13 documentos del Frente técnico de Helios era el más reciente por agente). La consulta
    SQL duplica el patrón de `conexiones_de` con `created_at` sumado — candidato a promover a
    `knowledge_module.motor.api.conexiones_de` como parámetro `order_by` genérico si otra
    instancia lo necesita; no se movió ahí todavía porque solo CRIZA lo pidió hasta ahora."""
    async with get_session_factory()() as s:
        r = await s.execute(
            text("""SELECT f2.id, tf2.nombre AS tipo, f2.props, f2.created_at
                     FROM conexion c
                     JOIN tipo_conexion tc ON tc.id = c.tipo_conexion_id
                     JOIN ficha f2 ON f2.id = c.hacia_ficha_id
                     JOIN tipo_ficha tf2 ON tf2.id = f2.tipo_ficha_id
                     WHERE c.desde_ficha_id = :id AND c.tenant_id = :t
                           AND tc.nombre = 'frente_produce_documento'
                     ORDER BY f2.created_at ASC"""),
            {"id": frente_id, "t": tenant},
        )
        return [
            {"id": str(x.id), "tipo": x.tipo, "props": x.props, "creado_en": x.created_at.isoformat()}
            for x in r.fetchall()
        ]


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


async def crear_caso(
    nombre: str,
    descripcion: str,
    tenant: str,
    estadio: str | None = None,
    fecha_inicio: str | None = None,
    participantes: list[dict] | None = None,
    notas: str | None = None,
) -> dict:
    """
    Crea un caso nuevo (Etapa 13, 2026-08-17) — hasta acá, los 2 casos reales del sistema
    (MicroBigs, Helios) se habían cargado por script directo al KM, sin ningún camino desde la
    app. `texto_busqueda` (el campo vectorizado, ver config/plantillas/casos.yaml) se computa
    acá — es derivado de nombre+descripción, no algo que aporte quien llama.

    Un caso puede crearse sin frentes todavía (`casos.yaml`: "un caso puede no tener frentes
    todavía definidos") — sumarlos es un paso aparte, no parte de esta función.

    Returns: {"success": bool, "caso_id": str | None, "error": str | None}
    """
    resultado = await motor_api.guardar_ficha(
        area=_AREA, tipo="caso", tenant=tenant,
        campos={
            "nombre": nombre,
            "descripcion": descripcion,
            "estadio": estadio,
            "fecha_inicio": fecha_inicio,
            "participantes": participantes or [],
            "notas": notas,
            "texto_busqueda": f"{nombre}. {descripcion}",
        },
    )
    if not resultado.get("success"):
        return {"success": False, "caso_id": None, "error": resultado.get("error")}
    return {"success": True, "caso_id": resultado["id"], "error": None}


async def obtener_documentos_aportados_de_frente(frente_id: str, tenant: str) -> list[dict]:
    """Documentos (`documento_aportado`) que Sebas subió y conectó a este frente — Etapa 17b,
    2026-08-17. Distinto de `obtener_documentos_de_frente` (esos los PRODUCE un especialista)."""
    return await motor_api.conexiones_de(
        frente_id, tipo_conexion="frente_tiene_documento_aportado", direccion="salientes", tenant=tenant
    )


async def guardar_documento_aportado(
    frente_id: str,
    titulo: str,
    contenido: str,
    tenant: str,
    fuente: str = "archivo_subido",
) -> dict:
    """
    Persiste un documento que Sebas aporta al caso (no producido por un agente), conectado al
    frente vía `frente_tiene_documento_aportado` — Etapa 17b, 2026-08-17. A diferencia del
    upload original (Etapa 17), esto SÍ persiste: cualquier conversación futura del Conductor
    sobre este caso, y cualquier corrida formal de un especialista sobre este frente, lo tienen
    disponible, no solo la conversación en la que se subió.

    Returns: {"success": bool, "documento_id": str | None, "error": str | None}
    """
    doc = await motor_api.guardar_ficha(
        area=_AREA, tipo="documento_aportado", tenant=tenant,
        campos={"titulo": titulo, "contenido": contenido, "fuente": fuente},
    )
    if not doc.get("success"):
        return {"success": False, "documento_id": None, "error": doc.get("error")}

    conexion = await motor_api.guardar_conexion(
        area=_AREA, tipo="frente_tiene_documento_aportado",
        desde_ficha_id=frente_id, hacia_ficha_id=doc["id"], tenant=tenant,
    )
    if not conexion.get("success"):
        return {"success": False, "documento_id": doc["id"], "error": conexion.get("error")}

    return {"success": True, "documento_id": doc["id"], "error": None}


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
