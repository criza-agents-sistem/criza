"""
Capa de abstracción de proveedor de modelo por agente — CRIZA.

PROPUESTA_DESTINO.md §8: elegir modelo y proveedor de IA por agente, no solo Anthropic. Mismo
patrón que EMBEDDING_PROVIDER en knowledge_module.embeddings — una variable de entorno por
agente selecciona el modelo/proveedor, el resto del código del agente no cambia.

Por qué la interfaz pública es la forma nativa de Anthropic (bloques de contenido, tool_use/
tool_result, stop_reason, usage.input_tokens/output_tokens): los 5 agentes de CRIZA ya están
escritos contra esa forma — es la que menos riesgo tiene de migrar (cero diff en el loop
agéntico de cada uno, solo cambia el client/la llamada). Por debajo, todo pasa por LiteLLM
(litellm.acompletion, formato OpenAI — decisión de plataforma, ver platform-boundary.md "Stack
base... LiteLLM"), que sí sabe hablar con múltiples proveedores. Este módulo traduce en las dos
direcciones: Anthropic -> OpenAI antes de llamar, OpenAI -> Anthropic al volver.

Convención del modelo: "<proveedor>/<modelo>", ej. "anthropic/claude-sonnet-4-6",
"openai/gpt-4o". Si no trae "/", se asume "anthropic/" — así ningún .env existente
(MARKET_MODEL=claude-sonnet-4-6, etc.) necesita tocarse para seguir usando Claude.

Verificado con llamadas reales contra la API (no mockeado) — ver docs/progress/2026-08-15.md:
tool-use de varios turnos, truncado por max_tokens, y prompt caching (cache_control) con
Anthropic como proveedor.
"""

import asyncio
import json
from dataclasses import dataclass, field

import litellm

# LiteLLM normaliza distinto los "no terminó por texto" — mapeo de vuelta al vocabulario
# nativo de Anthropic que ya usan los 5 agentes (`stop_reason == "..."`).
_FINISH_REASON_A_STOP_REASON = {
    "stop": "end_turn",
    "tool_calls": "tool_use",
    "length": "max_tokens",
}


def resolver_modelo(valor: str) -> str:
    """'claude-sonnet-4-6' -> 'anthropic/claude-sonnet-4-6'. Ya tiene proveedor -> se deja igual."""
    return valor if "/" in valor else f"anthropic/{valor}"


# Etapa 15 (2026-08-17) — Sebas pidió poder elegir modelo desde la web. Lista curada (no texto
# libre) para que la UI no ofrezca un ID inválido — hoy solo hay ANTHROPIC_API_KEY configurada
# (verificado en .env antes de construir esto), así que aunque `resolver_modelo` acepta cualquier
# "<proveedor>/<modelo>" de LiteLLM, ofrecer proveedores sin credenciales sería una opción que
# rompe al elegirla. Cuando se sume otra credencial (OpenAI, etc.), esta lista es el único lugar
# a tocar — la UI la lee de acá, no la duplica (`GET /modelos` en api/main.py).
MODELOS_DISPONIBLES = [
    {"id": "claude-sonnet-4-6", "nombre": "Sonnet 4.6", "nota": "el default actual del sistema — balance costo/calidad probado en esta sesión"},
    {"id": "claude-opus-5", "nombre": "Opus 5", "nota": "el más capaz — más lento y más caro, para análisis que lo ameriten"},
    {"id": "claude-sonnet-5", "nombre": "Sonnet 5", "nota": "el más nuevo de gama media — no probado todavía en este proyecto"},
    {"id": "claude-haiku-4-5-20251001", "nombre": "Haiku 4.5", "nota": "el más rápido y barato — para consultas simples"},
]


@dataclass
class Usage:
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass
class ContentBlock:
    type: str
    text: str | None = None
    id: str | None = None
    name: str | None = None
    input: dict | None = None


@dataclass
class AIResponse:
    content: list[ContentBlock]
    stop_reason: str
    usage: Usage


def _system_a_texto(system) -> str:
    """Concatena los bloques de `system` (ignora cache_control) para proveedores sin ese param."""
    if isinstance(system, str):
        return system
    return "\n".join(b.get("text", "") if isinstance(b, dict) else b.text for b in system)


def _mensajes_a_formato_openai(messages: list[dict]) -> list[dict]:
    """Traduce `messages` en forma nativa Anthropic (bloques tool_use/tool_result) a OpenAI."""
    openai_messages = []
    for m in messages:
        role, content = m["role"], m["content"]
        if isinstance(content, str):
            openai_messages.append({"role": role, "content": content})
            continue

        text_parts, tool_calls, tool_results = [], [], []
        for block in content:
            b = block if isinstance(block, dict) else block.__dict__
            btype = b["type"]
            if btype == "text":
                text_parts.append(b["text"])
            elif btype == "tool_use":
                tool_calls.append({
                    "id": b["id"], "type": "function",
                    "function": {"name": b["name"], "arguments": json.dumps(b["input"])},
                })
            elif btype == "tool_result":
                tool_results.append({
                    "role": "tool", "tool_call_id": b["tool_use_id"], "content": b["content"],
                })

        if tool_results:
            # Un mensaje "user" con N bloques tool_result (Anthropic) -> N mensajes "tool" (OpenAI)
            openai_messages.extend(tool_results)
        else:
            msg = {"role": role, "content": "\n".join(text_parts) or None}
            if tool_calls:
                msg["tool_calls"] = tool_calls
            openai_messages.append(msg)
    return openai_messages


def _tools_a_formato_openai(tools: list[dict] | None) -> list[dict] | None:
    if not tools:
        return None
    return [
        {"type": "function", "function": {
            "name": t["name"], "description": t.get("description", ""),
            "parameters": t.get("input_schema", {}),
        }}
        for t in tools
    ]


def _respuesta_a_formato_anthropic(resp) -> AIResponse:
    choice = resp.choices[0]
    msg = choice.message
    blocks = []
    if msg.content:
        blocks.append(ContentBlock(type="text", text=msg.content))
    for tc in (msg.tool_calls or []):
        blocks.append(ContentBlock(
            type="tool_use", id=tc.id, name=tc.function.name,
            input=json.loads(tc.function.arguments),
        ))

    u = resp.usage
    usage = Usage(
        input_tokens=u.prompt_tokens,
        output_tokens=u.completion_tokens,
        cache_creation_input_tokens=getattr(u, "cache_creation_input_tokens", 0) or 0,
        cache_read_input_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
    )
    stop_reason = _FINISH_REASON_A_STOP_REASON.get(choice.finish_reason, choice.finish_reason)
    return AIResponse(content=blocks, stop_reason=stop_reason, usage=usage)


def _preparar_kwargs(*, model: str, system, tools: list[dict] | None, messages: list[dict],
                      max_tokens: int, stream: bool = False) -> dict:
    """Arma los kwargs de `litellm.acompletion(...)` — compartido entre `complete()` y
    `complete_streaming()`, ambos traducen desde la misma forma nativa de Anthropic."""
    openai_messages = _mensajes_a_formato_openai(messages)
    kwargs = dict(model=model, max_tokens=max_tokens, messages=openai_messages)
    if stream:
        kwargs["stream"] = True
        kwargs["stream_options"] = {"include_usage": True}

    tools_openai = _tools_a_formato_openai(tools)
    if tools_openai:
        kwargs["tools"] = tools_openai

    if system:
        if model.startswith("anthropic/"):
            kwargs["system"] = system  # pass-through nativo, preserva cache_control
        else:
            kwargs["messages"] = [{"role": "system", "content": _system_a_texto(system)}] + openai_messages
    return kwargs


async def complete(*, model: str, messages: list[dict], max_tokens: int,
                    system=None, tools: list[dict] | None = None, retries: int = 4) -> AIResponse:
    """
    Reemplazo de `client.messages.create(...)` de Anthropic — misma forma de argumentos y de
    respuesta (bloques de contenido, stop_reason, usage.input_tokens/output_tokens), pero
    `model` puede ser de cualquier proveedor soportado por LiteLLM (ver `resolver_modelo`).
    Reintenta en rate limit (mismo criterio que ya tenían los 5 agentes cada uno por su cuenta —
    movido acá para no duplicar el loop 5 veces).
    """
    kwargs = _preparar_kwargs(model=model, system=system, tools=tools, messages=messages,
                               max_tokens=max_tokens)
    for attempt in range(retries):
        try:
            resp = await litellm.acompletion(**kwargs)
            return _respuesta_a_formato_anthropic(resp)
        except litellm.RateLimitError:
            if attempt == retries - 1:
                raise
            await asyncio.sleep(20 * (attempt + 1))


async def _acumular_stream(stream) -> AIResponse:
    """
    Consume un stream de LiteLLM y arma el mismo AIResponse que `complete()` — equivalente a
    `stream.get_final_message()` del SDK nativo de Anthropic (Armador la usa así: no consume
    eventos incrementales, solo evita el timeout de una respuesta no-streaming muy larga).
    Texto: se concatena. Tool calls: llegan fragmentadas — id/nombre solo en el primer
    fragmento de cada `index`, `arguments` se concatena por índice.
    """
    texto = ""
    tool_calls: dict[int, dict] = {}
    finish_reason = None
    usage_raw = None

    async for chunk in stream:
        choice = chunk.choices[0] if chunk.choices else None
        if choice:
            if choice.finish_reason:
                finish_reason = choice.finish_reason
            delta = choice.delta
            if delta and delta.content:
                texto += delta.content
            if delta and delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    entry = tool_calls.setdefault(idx, {"id": None, "name": None, "arguments": ""})
                    if tc.id:
                        entry["id"] = tc.id
                    if tc.function and tc.function.name:
                        entry["name"] = tc.function.name
                    if tc.function and tc.function.arguments:
                        entry["arguments"] += tc.function.arguments
        if getattr(chunk, "usage", None):
            usage_raw = chunk.usage

    blocks = []
    if texto:
        blocks.append(ContentBlock(type="text", text=texto))
    for idx in sorted(tool_calls):
        tc = tool_calls[idx]
        blocks.append(ContentBlock(
            type="tool_use", id=tc["id"], name=tc["name"],
            input=json.loads(tc["arguments"]) if tc["arguments"] else {},
        ))

    usage = Usage(
        input_tokens=getattr(usage_raw, "prompt_tokens", 0) or 0,
        output_tokens=getattr(usage_raw, "completion_tokens", 0) or 0,
        cache_creation_input_tokens=getattr(usage_raw, "cache_creation_input_tokens", 0) or 0,
        cache_read_input_tokens=getattr(usage_raw, "cache_read_input_tokens", 0) or 0,
    )
    stop_reason = _FINISH_REASON_A_STOP_REASON.get(finish_reason, finish_reason)
    return AIResponse(content=blocks, stop_reason=stop_reason, usage=usage)


async def complete_streaming(*, model: str, messages: list[dict], max_tokens: int,
                              system=None, tools: list[dict] | None = None,
                              retries: int = 5) -> AIResponse:
    """
    Variante en streaming de `complete()` — mismos argumentos, mismo AIResponse de vuelta.
    Usar cuando la respuesta puede ser muy larga (ej. Armador, hasta 64000 tokens) y una
    llamada no-streaming arriesga el timeout de lectura del cliente HTTP.
    """
    kwargs = _preparar_kwargs(model=model, system=system, tools=tools, messages=messages,
                               max_tokens=max_tokens, stream=True)
    for attempt in range(retries):
        try:
            stream = await litellm.acompletion(**kwargs)
            return await _acumular_stream(stream)
        except litellm.RateLimitError:
            if attempt == retries - 1:
                raise
            await asyncio.sleep(min(30 * (attempt + 1), 90))
