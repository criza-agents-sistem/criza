"""
Conductor — CRIZA

Agente conversacional — el punto de entrada con el que Sebas decide qué hacer a continuación
sobre un caso. Arquitectónicamente distinto a los demás agentes de CRIZA (todos de un solo
turno, contrato SEB-115): este es multi-turno, sin `submit_*` que marque el final — termina
cuando Sebas lo corta, no cuando "terminó de pensar". Por eso no tiene INPUT_CONTRACT/
OUTPUT_CONTRACT ni se registra en orquestador/agents_registry.yaml — no es un step de flow.

Arma el briefing de un caso según docs/PROTOCOLO_LECTURA_CONDUCTOR.md (Etapa 3), adaptado al
modelo de casos.yaml (Etapa 4) — es el modelo real que usa Helios/MicroBigs hoy, no
oportunidad+flow (que las primitivas de Etapa 2 asumen y que ningún caso real usa todavía).

Nunca bypasea la costura (PROPUESTA_CONDUCTOR.md §3.1, "otra puerta de entrada, nunca un
bypass") — invocar un especialista siempre pasa por orquestador/invocador.py::invocar_agente,
igual que cualquier otro cliente.

Ver docs/DESIGN_GATE.md — decisiones A-D (2026-08-16).
"""

import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

_AGENT_DIR = Path(__file__).parent
_CRIZA_DIR = _AGENT_DIR.parent
sys.path.insert(0, str(_CRIZA_DIR))
sys.path.insert(0, str(_AGENT_DIR))

from utils.ai_client import complete as _ai_complete, resolver_modelo as _resolver_modelo, ContentBlock
from utils.casos import (
    listar_casos as _listar_casos_fn,
    obtener_frentes_de_caso as _obtener_frentes_fn,
    obtener_documentos_de_frente as _obtener_documentos_fn,
    obtener_pendientes_de_caso as _obtener_pendientes_fn,
)
from knowledge_module.motor import api as motor_api
import knowledge_module.aprendizaje as aprendizaje
from scripts.km_decisiones import listar_decisiones_vigentes
from orquestador.registry import get_registry
from orquestador.invocador import invocar_agente
from utils.token_tracker import TokenTracker

DEFAULT_MODEL = os.getenv("CONDUCTOR_MODEL", "claude-sonnet-4-6")
_TENANT = "criza"

# Especialistas conectados al modelo de casos.yaml (invocables vía frente_id) — lista explícita,
# no inferida del registry, porque los 4 agentes viejos (mercado/evidencia/investigacion_amplia/
# armador) siguen solo en el modelo oportunidad_id y NO deben poder invocarse desde acá (fallarían
# con un error confuso dentro de su propio run() en vez de uno claro del Conductor). Etapa 7 sumó
# el segundo (ingeniero_ambiental) — de acá en más, sumar un especialista nuevo a esta lista es
# todo lo que hace falta para que el Conductor lo pueda invocar, sin tocar TOOLS ni el dispatch.
_ESPECIALISTAS_CASOS = {
    "microbiologo": "Especialista Microbiólogo",
    "ingeniero_ambiental": "Especialista Ingeniero Ambiental",
    "agronomo": "Especialista Ingeniero Agrónomo",
}


# ── Resolución de identificadores (Sebas habla por nombre, no por UUID) ────────

async def _resolver_caso(identificador: str) -> dict | None:
    """El id puede ser un UUID real o un nombre/fragmento — Sebas no memoriza UUIDs."""
    try:
        caso = await motor_api.obtener(identificador, tenant=_TENANT)
        if caso and caso.get("tipo") == "caso":
            return caso
    except Exception:
        pass  # no era un UUID válido — cae a búsqueda por nombre

    casos = await _listar_casos_fn(tenant=_TENANT)
    ident_lower = identificador.lower()
    return next(
        (c for c in casos if ident_lower in (c.get("props") or {}).get("nombre", "").lower()),
        None,
    )


async def _resolver_frente(caso: dict, identificador: str) -> dict | None:
    frentes = await _obtener_frentes_fn(caso["id"], tenant=_TENANT)
    ident_lower = identificador.lower()
    por_id = next((f for f in frentes if f["id"] == identificador), None)
    if por_id:
        return por_id
    return next(
        (f for f in frentes if ident_lower in (f.get("props") or {}).get("nombre", "").lower()),
        None,
    )


# ── Tools ────────────────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "listar_casos",
        "description": "Lista los casos existentes (nombre, estadío, descripción breve). Usar cuando Sebas no especificó de qué caso está hablando.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "ver_caso",
        "description": (
            "Trae el briefing completo de un caso — identidad, cada frente con si ya tiene "
            "documentos producidos o no, pendientes abiertos, lecciones relevantes, y decisiones "
            "de sistema vigentes. Es la fuente de verdad para responder '¿cómo viene X?' — nunca "
            "inventar el estado de un caso, siempre llamar esto primero."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"caso": {"type": "string", "description": "Nombre (o fragmento) del caso, o su UUID."}},
            "required": ["caso"],
        },
    },
    {
        "name": "correr_especialista",
        "description": (
            "Invoca a un especialista de la biblioteca contra un frente de un caso, vía la "
            "costura (nunca directo). Especialistas disponibles hoy: "
            + ", ".join(f"'{k}' ({v})" for k, v in _ESPECIALISTAS_CASOS.items())
            + ". Gasta tokens reales y escribe al KM — no lo llames sin que Sebas lo haya pedido "
              "o aprobado explícitamente en la conversación."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "especialista": {"type": "string", "enum": list(_ESPECIALISTAS_CASOS.keys())},
                "caso": {"type": "string", "description": "Nombre (o fragmento) del caso, o su UUID."},
                "frente": {"type": "string", "description": "Nombre (o fragmento) del frente, o su UUID."},
                "tarea": {"type": "string", "description": "Opcional — instrucción específica para esta corrida."},
                "contexto": {"type": "string", "description": "Opcional — contexto adicional para esta corrida."},
            },
            "required": ["especialista", "caso", "frente"],
        },
    },
    {
        "name": "ver_documento",
        "description": "Trae el contenido completo de un documento_caso puntual (por su id) — usar cuando Sebas quiere profundizar en algo que ver_caso solo resumió.",
        "input_schema": {
            "type": "object",
            "properties": {"documento_id": {"type": "string"}},
            "required": ["documento_id"],
        },
    },
]


# ── Implementación de tools ─────────────────────────────────────────────────

async def _tool_listar_casos() -> dict:
    casos = await _listar_casos_fn(tenant=_TENANT)
    return {
        "casos": [
            {"id": c["id"], "nombre": (c.get("props") or {}).get("nombre"), "estadio": (c.get("props") or {}).get("estadio")}
            for c in casos
        ]
    }


async def _tool_ver_caso(identificador: str) -> dict:
    caso = await _resolver_caso(identificador)
    if not caso:
        return {"error": f"No se encontró ningún caso que coincida con '{identificador}'. Usar listar_casos primero."}

    caso_props = caso.get("props") or {}
    frentes = await _obtener_frentes_fn(caso["id"], tenant=_TENANT)
    frentes_briefing = []
    for f in frentes:
        docs = await _obtener_documentos_fn(f["id"], tenant=_TENANT)
        frentes_briefing.append({
            "id": f["id"],
            "nombre": (f.get("props") or {}).get("nombre"),
            "estado": (f.get("props") or {}).get("estado"),
            "documentos_producidos": len(docs),
            "ultimo_documento": (docs[-1].get("props") or {}).get("titulo") if docs else None,
        })

    pendientes = await _obtener_pendientes_fn(caso["id"], tenant=_TENANT)
    pendientes_briefing = [(p.get("props") or {}).get("descripcion") for p in pendientes]

    await aprendizaje.ensure_area(tenant=_TENANT)
    lecciones = await aprendizaje.leer_lecciones_caso(
        consulta=caso_props.get("descripcion") or caso_props.get("nombre") or caso["id"],
        tenant=_TENANT,
    )
    lecciones_briefing = [l.get("props", {}).get("contenido") for l in lecciones]

    decisiones = await listar_decisiones_vigentes()
    decisiones_briefing = [
        {"titulo": d.get("titulo"), "fecha": d.get("fecha"), "componente": d.get("componente")}
        for d in decisiones[:8]
    ]

    return {
        "identidad": {"id": caso["id"], "nombre": caso_props.get("nombre"), "descripcion": caso_props.get("descripcion"), "estadio": caso_props.get("estadio")},
        "frentes": frentes_briefing,
        "pendientes_abiertos": pendientes_briefing,
        "lecciones_relevantes": lecciones_briefing,
        "decisiones_de_sistema_vigentes": decisiones_briefing,
        "nota": "Sanity check: 'documentos_producidos' > 0 significa que ya se corrió un especialista sobre ese frente — no asumir que 'estado: activo' implica trabajo pendiente sin chequear esto.",
    }


async def _tool_correr_especialista(nombre_especialista: str, caso_ident: str, frente_ident: str, tarea: str | None, contexto: str | None, verbose: bool) -> dict:
    if nombre_especialista not in _ESPECIALISTAS_CASOS:
        return {"error": f"'{nombre_especialista}' no es un especialista disponible. Opciones: {list(_ESPECIALISTAS_CASOS.keys())}."}

    caso = await _resolver_caso(caso_ident)
    if not caso:
        return {"error": f"No se encontró ningún caso que coincida con '{caso_ident}'."}
    frente = await _resolver_frente(caso, frente_ident)
    if not frente:
        return {"error": f"No se encontró ningún frente que coincida con '{frente_ident}' dentro de '{caso_ident}'."}

    registry = get_registry()
    spec = registry.get(nombre_especialista)
    if spec is None or spec.run_fn is None:
        return {"error": f"El especialista '{nombre_especialista}' no está disponible (inactivo o sin cargar)."}

    output = await invocar_agente(
        spec=spec,
        contract_input={
            "tarea": tarea,
            "contexto": contexto,
            "conocimiento": {"frente_id": frente["id"]},
        },
        tenant=_TENANT,
        frente_id=frente["id"],
        verbose=verbose,
    )

    analisis = output.get("análisis") or {}
    evaluacion_tecnica = analisis.get("evaluacion_tecnica") or {}
    especialista = analisis.get("especialista_adicional_recomendado") or {}

    return {
        "frente": (frente.get("props") or {}).get("nombre"),
        "nivel_confianza": output.get("nivel_confianza"),
        "enfoques_identificados": len(evaluacion_tecnica.get("enfoques_tecnicos_identificados") or []),
        "brechas_de_alto_impacto": output.get("recomendaciones"),
        "especialista_adicional_recomendado": especialista.get("si_no", False),
        "descripcion_especialista_adicional": especialista.get("descripcion"),
        "informe_resumen": (analisis.get("informe_completo") or "")[:600],
        "nota": "Informe completo guardado como documento_caso conectado al frente — usar ver_documento si Sebas pide el texto entero.",
    }


async def _tool_ver_documento(documento_id: str) -> dict:
    doc = await motor_api.obtener(documento_id, tenant=_TENANT)
    if not doc or doc.get("tipo") != "documento_caso":
        return {"error": f"No se encontró ningún documento con id '{documento_id}'."}
    props = doc.get("props") or {}
    return {
        "titulo": props.get("titulo"),
        "modo": props.get("modo"),
        "estado": props.get("estado"),
        "agente": props.get("agente"),
        "contenido": props.get("contenido"),
    }


# ── System prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Sos el Conductor de CRIZA — el punto de entrada conversacional con el que Sebas
decide qué hacer a continuación sobre un caso real que CRIZA acompaña.

TU ROL (PROPUESTA_CONDUCTOR.md §3):
- SOS: quien lee el estado real, arma la decisión masticada (qué falta, qué cuesta, qué riesgo),
  invoca especialistas cuando Sebas lo pide, y ayuda a decidir qué sigue.
- NO SOS: un planificador autónomo. No corrés nada de punta a punta sin que Sebas lo pida. La
  decisión final siempre es de Sebas.

PRINCIPIO CENTRAL — nunca inventes el estado de un caso. Siempre llamá ver_caso antes de opinar
sobre cómo viene un caso, aunque creas que ya lo sabés de un mensaje anterior — el estado puede
haber cambiado. Un Conductor que confía en lo que recuerda en vez de re-consultar el KM es
exactamente el bug que este sistema viene evitando (docs/PROTOCOLO_LECTURA_CONDUCTOR.md §2:
"derivado, nunca cacheado en prosa").

TOOLS DISPONIBLES:
- listar_casos: cuando no sepas de qué caso habla Sebas.
- ver_caso: el briefing completo — identidad, frentes (y si cada uno ya tiene documentos
  producidos), pendientes abiertos, lecciones relevantes, decisiones de sistema vigentes.
- correr_especialista: invoca a un especialista de la biblioteca (microbiólogo, ingeniero
  ambiental) contra un frente. GASTA TOKENS REALES Y ESCRIBE AL KM — no lo llames sin que Sebas
  lo haya pedido o aprobado explícitamente. Antes de sugerirlo, chequeá con ver_caso si ese
  frente ya tiene un documento producido — no re-correr un análisis que ya existe sin decírselo
  a Sebas primero (puede que igual quiera reintentar, pero es su decisión, no la tuya). Elegí el
  especialista según qué pregunta hay que responder — el microbiólogo evalúa si un enfoque es
  biológica/químicamente viable, el ingeniero ambiental evalúa si ese enfoque ya identificado se
  puede construir y operar de verdad (balances de masa/energía, dimensionamiento), el ingeniero
  agrónomo evalúa si un producto/enfoque funciona de verdad como insumo agrícola/ganadero (dosis,
  compatibilidad de cultivo/suelo, normativa de aplicación).
- ver_documento: el texto completo de un documento puntual, cuando Sebas quiere profundizar.

CÓMO RESPONDER (PROPUESTA_CONDUCTOR.md §3.2 — la atención de Sebas es el recurso escaso):
Llegá con la decisión masticada — qué falta, qué ya está, qué recomendás y por qué — no le
devuelvas a Sebas un volcado crudo de todo lo que leíste. Si detectás algo inconsistente (ej. un
frente que un especialista marcó como necesitando ayuda adicional y nadie lo siguió) — decilo,
es exactamente el tipo de cosa que solo vos podés ver.

LÍMITES EXPLÍCITOS DE ESTA VERSIÓN (no prometas lo que no hacés todavía):
- Solo podés invocar los especialistas conectados al modelo de casos.yaml (hoy: microbiólogo,
  ingeniero ambiental, ingeniero agrónomo) — los 4 agentes del expediente viejo (mercado,
  evidencia, investigación amplia, armador) todavía no están conectados a este modelo.
- Esta conversación SÍ queda guardada (el historial completo vive en el KM, sobrevive a un
  reinicio del servidor) — podés decirle a Sebas que si vuelve a esta misma sesión más tarde vas
  a recordar lo que se habló. Lo que todavía NO hacés es destilar una lección reusable a partir
  de la charla (eso es un paso aparte, todavía no construido) — si Sebas te pide "anotá esto como
  lección", avisale que ese gap sigue abierto, no lo inventes ni finjas que lo guardaste como tal.
"""


# ── Loop conversacional ──────────────────────────────────────────────────────

async def _despachar_tool(nombre: str, tool_input: dict, verbose: bool) -> dict:
    if nombre == "listar_casos":
        return await _tool_listar_casos()
    if nombre == "ver_caso":
        return await _tool_ver_caso(tool_input.get("caso", ""))
    if nombre == "correr_especialista":
        return await _tool_correr_especialista(
            tool_input.get("especialista", ""), tool_input.get("caso", ""), tool_input.get("frente", ""),
            tool_input.get("tarea"), tool_input.get("contexto"), verbose,
        )
    if nombre == "ver_documento":
        return await _tool_ver_documento(tool_input.get("documento_id", ""))
    return {"error": f"Tool '{nombre}' no implementado."}


async def enviar_mensaje(
    messages: list[dict],
    texto_usuario: str,
    model: str = DEFAULT_MODEL,
    verbose: bool = False,
    tracker: TokenTracker | None = None,
) -> tuple[str, list[dict]]:
    """
    Un turno de la conversación: agrega el mensaje de Sebas, corre el loop de tools hasta que
    el modelo termina de responder (end_turn), devuelve el texto de la respuesta.

    `messages` se muta y se devuelve — el caller (run.py, o un test) lo mantiene entre turnos
    para que el Conductor tenga memoria de la conversación.
    """
    messages.append({"role": "user", "content": texto_usuario})
    tracker = tracker or TokenTracker(agent="conductor", oportunidad_id="", model=model)

    while True:
        response = await _ai_complete(
            model=_resolver_modelo(model),
            max_tokens=4096,
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            tools=TOOLS,
            messages=messages,
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
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(resultado, ensure_ascii=False, default=str),
            })
        messages.append({"role": "user", "content": tool_results})


def serializar_mensajes(messages: list[dict]) -> list[dict]:
    """
    Convierte `messages` a JSON-safe para persistir (ver docs/DESIGN_GATE.md decisión E) —
    los turnos assistant traen `ContentBlock` (utils/ai_client.py, dataclass simple, no un tipo
    opaco de SDK), que `json.dumps` no serializa sin ayuda.

    No hace falta una función inversa: `utils/ai_client.py::_mensajes_a_formato_openai` ya
    acepta indistintamente `ContentBlock` o dict plano (`b = block if isinstance(block, dict)
    else block.__dict__`) — un mensaje recién cargado de storage se re-envía tal cual al
    próximo turno, sin reconstruir nada.
    """
    out = []
    for m in messages:
        content = m["content"]
        if isinstance(content, str):
            out.append(m)
        else:
            out.append({
                "role": m["role"],
                "content": [asdict(b) if isinstance(b, ContentBlock) else b for b in content],
            })
    return out
