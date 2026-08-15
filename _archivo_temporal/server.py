"""
KM de CRIZA — MCP Server (Capa 2).

Expone las tools del KM legacy de CRIZA (tablas corrida/oportunidad/documento) como servidor
MCP. Movido de knowledge_module/ a criza/ al empaquetar el KM (2026-07-22): las tools que
expone son CRIZA-específicas, no de plataforma. Cada instancia futura arma su propio server
sobre el motor genérico si lo necesita.

Correr (desde criza/):
    python server.py
"""

from mcp.server.fastmcp import FastMCP
from km_tools import (
    get_opportunity_history,
    search_fuentes_externas,
    search_knowledge,
    store_corrida,
    store_learning,
    store_opportunity,
    update_opportunity,
)

mcp = FastMCP("knowledge-module")


# ─────────────────────────────────────────
# TOOLS
# ─────────────────────────────────────────

@mcp.tool()
async def km_store_corrida(
    sector: str,
    agente: str,
    modo: str,
    fecha: str,
    modelo: str,
    tokens_input: int = None,
    tokens_output: int = None,
    costo_usd: float = None,
    notas: str = None,
) -> str:
    """
    Guarda el registro de una ejecución del agente divergente o convergente.

    - sector: sector analizado (ej. "Ganadería bovina, Córdoba")
    - agente: "divergente" o "convergente"
    - modo: "A" (producto fijado), "B" (capacidad fijada), "C" (abierta)
    - fecha: fecha de la corrida en formato ISO (ej. "2026-06-08")
    - modelo: nombre del modelo usado (ej. "claude-sonnet-4-6")

    Retorna el ID de la corrida guardada — usarlo para asociar oportunidades.
    """
    result = await store_corrida(
        sector=sector, agente=agente, modo=modo, fecha=fecha, modelo=modelo,
        tokens_input=tokens_input, tokens_output=tokens_output,
        costo_usd=costo_usd, notas=notas,
    )
    if result["success"]:
        return f"Corrida guardada. ID: {result['data']['id']}"
    return f"Error al guardar corrida: {result['error']}"


@mcp.tool()
async def km_store_opportunity(
    sector: str,
    idea: str,
    prioridad: str,
    origen: str = "agente",
    corrida_id: str = None,
    gaps_pendientes: str = None,
) -> str:
    """
    Guarda una oportunidad de blue ocean detectada por el agente.

    Si ya existe una oportunidad muy similar (misma idea en el mismo sector),
    incrementa su contador de veces_detectada en lugar de crear un duplicado.
    Esto permite saber cuántas corridas independientes encontraron la misma oportunidad.

    - sector: sector al que pertenece la oportunidad
    - idea: descripción del dolor y la vía biotech propuesta
    - prioridad: "alta", "media" o "baja"
    - origen: "agente" (default), "equipo" o "externo"
    - corrida_id: ID de la corrida que la generó (opcional, para trazar el origen)
    - gaps_pendientes: qué falta saber para decidir (opcional)
    """
    result = await store_opportunity(
        sector=sector, idea=idea, prioridad=prioridad, origen=origen,
        corrida_id=corrida_id, gaps_pendientes=gaps_pendientes,
    )
    if result["success"]:
        action = result["data"]["action"]
        oid = result["data"]["id"]
        if action == "created":
            return f"Oportunidad nueva guardada. ID: {oid}"
        else:
            veces = result["data"]["veces_detectada"]
            sim = result["data"]["similitud"]
            return f"Oportunidad existente reforzada (similitud: {sim}). Veces detectada: {veces}. ID: {oid}"
    return f"Error al guardar oportunidad: {result['error']}"


@mcp.tool()
async def km_store_learning(
    contenido: str,
    tipo: str,
    fuente: str = "agente_destilacion",
    nivel_confianza: float = 0.5,
    origen_nombre: str = None,
) -> str:
    """
    Guarda un aprendizaje destilado del proceso de búsqueda.

    - contenido: el aprendizaje redactado como afirmación clara
    - tipo: "patron_dominio" | "patron_error" | "analogia" | "senal_decision"
    - fuente: "agente_destilacion" (default) | "socio_externo" | "articulador"
    - nivel_confianza: 0.0 a 1.0 (default 0.5)

    Si ya existe un aprendizaje muy similar, refuerza su nivel de confianza
    en lugar de duplicarlo.
    """
    result = await store_learning(
        contenido=contenido, tipo=tipo, fuente=fuente,
        nivel_confianza=nivel_confianza, origen_nombre=origen_nombre,
    )
    if result["success"]:
        action = result["data"]["action"]
        if action == "created":
            return f"Aprendizaje guardado. ID: {result['data']['id']}"
        else:
            return (
                f"Aprendizaje existente reforzado. "
                f"Confianza: {result['data']['nivel_confianza']:.2f}, "
                f"veces confirmado: {result['data']['veces_confirmado']}. "
                f"ID: {result['data']['id']}"
            )
    return f"Error al guardar aprendizaje: {result['error']}"


@mcp.tool()
async def km_search(
    query: str,
    tipo: str = "all",
    sector: str = None,
    limit: int = 5,
) -> str:
    """
    Busca en el Knowledge Module por similitud semántica.

    Úsalo al inicio de una corrida para recuperar oportunidades y aprendizajes
    relevantes de corridas anteriores — evita repetir análisis ya hechos y
    aprovecha los sesgos ya documentados.

    - query: texto libre (dolor, sector, idea, concepto)
    - tipo: "oportunidades" | "aprendizajes" | "all" (default)
    - sector: filtro opcional por sector
    - limit: máximo de resultados por tipo (default 5)
    """
    result = await search_knowledge(query=query, tipo=tipo, sector=sector, limit=limit)
    if not result["success"]:
        return f"Error en búsqueda: {result['error']}"

    data = result["data"]
    if not data["results"]:
        return f"No se encontraron resultados para: '{query}'"

    lines = [f"Resultados para '{query}' ({data['total']} encontrados):\n"]
    for r in data["results"]:
        if r["tipo"] == "oportunidad":
            lines.append(
                f"[OPORTUNIDAD] {r['sector']} — {r['idea'][:120]}...\n"
                f"  Prioridad: {r['prioridad']} | Estado: {r['estado']} | "
                f"Veces detectada: {r['veces_detectada']} | Similitud: {r['similitud']}\n"
                f"  Gaps: {r.get('gaps_pendientes', 'N/A')}\n"
                f"  ID: {r['id']}\n"
            )
        else:
            lines.append(
                f"[APRENDIZAJE/{r['tipo_aprendizaje'].upper()}] {r['contenido'][:150]}...\n"
                f"  Confianza: {r['nivel_confianza']:.2f} | "
                f"Confirmado: {r['veces_confirmado']}x | Similitud: {r['similitud']}\n"
                f"  ID: {r['id']}\n"
            )
    return "\n".join(lines)


@mcp.tool()
async def km_get_opportunity(oportunidad_id: str) -> str:
    """
    Devuelve el historial completo de una oportunidad:
    en qué corridas apareció, con qué prioridad en cada una,
    validaciones del equipo y gaps pendientes.

    - oportunidad_id: UUID de la oportunidad
    """
    result = await get_opportunity_history(oportunidad_id)
    if not result["success"]:
        return f"Error: {result['error']}"

    d = result["data"]
    lines = [
        f"OPORTUNIDAD: {d['sector']}",
        f"Idea: {d['idea']}",
        f"Prioridad: {d['prioridad']} | Estado: {d['estado_analisis']} | "
        f"Veces detectada: {d['veces_detectada']}",
    ]
    if d["validaciones"]:
        lines.append(f"Validaciones del equipo: {d['validaciones']}")
    if d["gaps_pendientes"]:
        lines.append(f"Gaps pendientes: {d['gaps_pendientes']}")
    if d["razon_descarte"]:
        lines.append(f"Razón de descarte: {d['razon_descarte']}")
    if d["corridas"]:
        lines.append(f"\nApareció en {len(d['corridas'])} corrida(s):")
        for c in d["corridas"]:
            lines.append(
                f"  - {c['fecha']} | {c['sector']} | modo {c['modo']} | "
                f"prioridad en esa corrida: {c['prioridad_en_corrida']}"
            )
    return "\n".join(lines)


@mcp.tool()
async def km_update_opportunity(
    oportunidad_id: str,
    estado_analisis: str = None,
    validaciones: str = None,
    gaps_pendientes: str = None,
    prioridad: str = None,
    razon_descarte: str = None,
) -> str:
    """
    Actualiza el estado o la información de una oportunidad.
    Solo actualiza los campos que se pasan — el resto queda igual.

    - estado_analisis: "detectada" | "en_analisis" | "validada" | "descartada"
    - validaciones: qué confirmó el equipo con gente del sector
    - gaps_pendientes: qué falta saber para decidir
    - razon_descarte: solo si se marca como descartada
    """
    result = await update_opportunity(
        oportunidad_id=oportunidad_id,
        estado_analisis=estado_analisis,
        validaciones=validaciones,
        gaps_pendientes=gaps_pendientes,
        prioridad=prioridad,
        razon_descarte=razon_descarte,
    )
    if result["success"]:
        return (
            f"Oportunidad actualizada. "
            f"Estado: {result['data']['estado_analisis']} | "
            f"Prioridad: {result['data']['prioridad']}"
        )
    return f"Error al actualizar: {result['error']}"


@mcp.tool()
async def km_search_fuentes_externas(
    query: str,
    sector: str = None,
    tipo: str = None,
    limit: int = 10,
    tenant_id: str = "criza",
) -> str:
    """
    Busca en el corpus de documentos externos cosechados en el KM
    (papers INTA Digital, normas, reportes técnicos, etc.) usando
    PostgreSQL full-text search sobre título, abstract y subjects.

    - query: texto libre en español o inglés. Soporta operadores:
      'garrapata biocontrol', 'virus AND vacuna', '"influenza equina"'.
    - sector: filtro opcional por sector (ej. "Biotecnología agrícola").
    - tipo: filtro opcional — 'paper', 'reporte', 'norma', 'patente', 'otro'.
    - limit: máximo de resultados (default 10).
    - tenant_id: instancia del KM (default 'criza').

    Retorna los documentos más relevantes con título, abstract, autores,
    subjects, URL fuente, año y score de relevancia.
    """
    result = await search_fuentes_externas(
        query=query,
        sector=sector,
        tipo=tipo,
        limit=limit,
        tenant_id=tenant_id,
    )
    if not result["success"]:
        return f"Error en búsqueda: {result['error']}"

    data = result["data"]
    if not data["results"]:
        return f"Sin resultados para: '{query}'"

    lines = [f"Resultados para '{query}' ({data['total']} encontrados):\n"]
    for r in data["results"]:
        autores_str = ", ".join(r["autores"][:3]) if r["autores"] else "Autores no disponibles"
        if len(r["autores"]) > 3:
            autores_str += " et al."
        subjects_str = ", ".join(r["subjects"][:5]) if r["subjects"] else ""
        lines.append(
            f"[{r['tipo'].upper()}/{r['año'] or '?'}] {r['titulo']}\n"
            f"  Autores: {autores_str}\n"
            f"  Subjects: {subjects_str}\n"
            f"  URL: {r['fuente_url']}\n"
            f"  Abstract: {(r['abstract'] or '')[:200]}...\n"
            f"  Relevancia: {r['rank']}\n"
        )
    return "\n".join(lines)


# ─────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────

if __name__ == "__main__":
    import asyncio
    mcp.run()
