"""
Tests del Conductor — CRIZA.

Unit: resolución de identificadores, tools individuales, loop conversacional (historial +
despacho de tools).
Integration: sesión conversacional real (solo lectura — listar_casos/ver_caso, sin invocar al
microbiólogo, para no gastar tokens de más en cada corrida de la suite) contra el KM real.

Correr unit: pytest tests/ -m "not integration"
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

_CRIZA = Path(__file__).parent.parent.parent
_AGENT = Path(__file__).parent.parent
sys.path.insert(0, str(_CRIZA))
sys.path.insert(0, str(_AGENT))

import conductor as cond

CASO_HELIOS = {
    "id": "caso-helios",
    "tipo": "caso",
    "props": {"nombre": "Efluentes biogás (Helios)", "descripcion": "Biodigestor con efluente diluido.", "estadio": "desde_cero"},
}
FRENTE_TECNICO = {"id": "frente-tecnico", "tipo": "frente", "props": {"nombre": "Frente técnico", "estado": "activo"}}
FRENTE_ASOCIACION = {"id": "frente-asociacion", "tipo": "frente", "props": {"nombre": "Frente de asociación", "estado": "activo"}}


# ── TOOLS — estructura ──────────────────────────────────────────────────────

@pytest.mark.unit
def test_tools_count():
    assert len(cond.TOOLS) == 6


@pytest.mark.unit
def test_tools_names():
    nombres = {t["name"] for t in cond.TOOLS}
    assert nombres == {"listar_casos", "ver_caso", "correr_especialista", "ver_documento", "anotar_leccion", "crear_caso"}


@pytest.mark.unit
def test_correr_especialista_requiere_especialista_caso_y_frente():
    tool = next(t for t in cond.TOOLS if t["name"] == "correr_especialista")
    assert set(tool["input_schema"]["required"]) == {"especialista", "caso", "frente"}


@pytest.mark.unit
def test_correr_especialista_enum_incluye_los_especialistas_disponibles():
    tool = next(t for t in cond.TOOLS if t["name"] == "correr_especialista")
    assert set(tool["input_schema"]["properties"]["especialista"]["enum"]) == {"microbiologo", "ingeniero_ambiental", "agronomo"}


# ── _resolver_caso ───────────────────────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolver_caso_por_uuid():
    with patch("conductor.motor_api.obtener", new=AsyncMock(return_value=CASO_HELIOS)):
        result = await cond._resolver_caso("caso-helios")
    assert result == CASO_HELIOS


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolver_caso_por_nombre_fallback():
    with (
        patch("conductor.motor_api.obtener", new=AsyncMock(side_effect=Exception("no es un UUID válido"))),
        patch("conductor._listar_casos_fn", new=AsyncMock(return_value=[CASO_HELIOS])),
    ):
        result = await cond._resolver_caso("helios")
    assert result == CASO_HELIOS


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resolver_caso_no_encontrado():
    with (
        patch("conductor.motor_api.obtener", new=AsyncMock(return_value=None)),
        patch("conductor._listar_casos_fn", new=AsyncMock(return_value=[CASO_HELIOS])),
    ):
        result = await cond._resolver_caso("no existe")
    assert result is None


# ── _tool_ver_caso ────────────────────────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_tool_ver_caso_arma_briefing_completo():
    with (
        patch("conductor._resolver_caso", new=AsyncMock(return_value=CASO_HELIOS)),
        patch("conductor._obtener_frentes_fn", new=AsyncMock(return_value=[FRENTE_TECNICO, FRENTE_ASOCIACION])),
        patch("conductor._obtener_documentos_fn", new=AsyncMock(side_effect=[
            [{"props": {"titulo": "Evaluación — microbiologo"}}],  # frente técnico ya tiene 1
            [],  # frente de asociación no tiene ninguno
        ])),
        patch("conductor._obtener_pendientes_fn", new=AsyncMock(return_value=[{"props": {"descripcion": "Confirmar flete"}}])),
        patch("conductor.aprendizaje.ensure_area", new=AsyncMock()),
        patch("conductor.aprendizaje.leer_lecciones_caso", new=AsyncMock(return_value=[])),
        patch("conductor.listar_decisiones_vigentes", new=AsyncMock(return_value=[])),
    ):
        result = await cond._tool_ver_caso("helios")

    assert result["identidad"]["nombre"] == "Efluentes biogás (Helios)"
    assert len(result["frentes"]) == 2
    tecnico = next(f for f in result["frentes"] if f["nombre"] == "Frente técnico")
    assert tecnico["documentos_producidos"] == 1
    asociacion = next(f for f in result["frentes"] if f["nombre"] == "Frente de asociación")
    assert asociacion["documentos_producidos"] == 0
    assert "Confirmar flete" in result["pendientes_abiertos"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tool_ver_caso_no_encontrado_devuelve_error():
    with patch("conductor._resolver_caso", new=AsyncMock(return_value=None)):
        result = await cond._tool_ver_caso("no existe")
    assert "error" in result


# ── _tool_correr_microbiologo ───────────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_tool_correr_microbiologo_invoca_con_frente_id():
    mock_spec = type("Spec", (), {"run_fn": AsyncMock()})()
    mock_registry = {"microbiologo": mock_spec}
    mock_output = {
        "análisis": {
            "evaluacion_tecnica": {"enfoques_tecnicos_identificados": [{"enfoque": "x"}]},
            "especialista_adicional_recomendado": {"si_no": False},
            "informe_completo": "informe largo" * 100,
        },
        "nivel_confianza": "medio",
        "recomendaciones": [],
    }

    with (
        patch("conductor._resolver_caso", new=AsyncMock(return_value=CASO_HELIOS)),
        patch("conductor._resolver_frente", new=AsyncMock(return_value=FRENTE_TECNICO)),
        patch("conductor.get_registry", return_value=mock_registry),
        patch("conductor.invocar_agente", new=AsyncMock(return_value=mock_output)) as mock_invocar,
    ):
        result = await cond._tool_correr_especialista("microbiologo", "helios", "técnico", None, None, False)

    mock_invocar.assert_awaited_once()
    _, kwargs = mock_invocar.call_args
    assert kwargs["frente_id"] == "frente-tecnico"
    assert "oportunidad_id" not in kwargs
    assert result["nivel_confianza"] == "medio"
    assert len(result["informe_resumen"]) <= 600


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tool_correr_especialista_frente_no_encontrado():
    with (
        patch("conductor._resolver_caso", new=AsyncMock(return_value=CASO_HELIOS)),
        patch("conductor._resolver_frente", new=AsyncMock(return_value=None)),
    ):
        result = await cond._tool_correr_especialista("microbiologo", "helios", "no existe", None, None, False)
    assert "error" in result


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tool_correr_especialista_nombre_invalido():
    result = await cond._tool_correr_especialista("especialista_inventado", "helios", "técnico", None, None, False)
    assert "error" in result


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tool_correr_especialista_ingeniero_ambiental():
    """El segundo especialista (Etapa 7) también es invocable — no quedó hardcodeado a microbiólogo."""
    mock_spec = type("Spec", (), {"run_fn": AsyncMock()})()
    mock_registry = {"ingeniero_ambiental": mock_spec}
    mock_output = {
        "análisis": {"evaluacion_tecnica": {"enfoques_tecnicos_identificados": []}, "especialista_adicional_recomendado": {"si_no": False}, "informe_completo": "x"},
        "nivel_confianza": "alto",
        "recomendaciones": [],
    }
    with (
        patch("conductor._resolver_caso", new=AsyncMock(return_value=CASO_HELIOS)),
        patch("conductor._resolver_frente", new=AsyncMock(return_value=FRENTE_TECNICO)),
        patch("conductor.get_registry", return_value=mock_registry),
        patch("conductor.invocar_agente", new=AsyncMock(return_value=mock_output)) as mock_invocar,
    ):
        result = await cond._tool_correr_especialista("ingeniero_ambiental", "helios", "técnico", None, None, False)

    mock_invocar.assert_awaited_once()
    assert result["nivel_confianza"] == "alto"


# ── _tool_ver_documento ──────────────────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_tool_ver_documento_encontrado():
    doc = {"id": "doc-1", "tipo": "documento_caso", "props": {"titulo": "t", "contenido": "c", "modo": "chat", "estado": "borrador", "agente": "microbiologo"}}
    with patch("conductor.motor_api.obtener", new=AsyncMock(return_value=doc)):
        result = await cond._tool_ver_documento("doc-1")
    assert result["contenido"] == "c"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tool_ver_documento_no_encontrado():
    with patch("conductor.motor_api.obtener", new=AsyncMock(return_value=None)):
        result = await cond._tool_ver_documento("no-existe")
    assert "error" in result


# ── _tool_anotar_leccion (trigger explícito, Etapa 9) ───────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_tool_anotar_leccion_guarda_con_fuente_humano():
    with (
        patch("conductor.aprendizaje.ensure_area", new=AsyncMock()),
        patch("conductor.aprendizaje.guardar_leccion_caso", new=AsyncMock(return_value={"success": True, "id": "leccion-1"})) as mock_guardar,
    ):
        result = await cond._tool_anotar_leccion("Siempre validar el flete antes de recomendar.", "Helios, logística")

    assert result == {"guardado": True, "id": "leccion-1"}
    _, kwargs = mock_guardar.call_args
    assert kwargs["agente"] == "conductor"
    assert kwargs["fuente"] == "humano"
    assert kwargs["contenido"] == "Siempre validar el flete antes de recomendar."


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tool_anotar_leccion_contenido_vacio_es_error():
    result = await cond._tool_anotar_leccion("   ", "contexto")
    assert "error" in result


@pytest.mark.unit
@pytest.mark.asyncio
async def test_despachar_tool_anotar_leccion():
    with patch("conductor._tool_anotar_leccion", new=AsyncMock(return_value={"guardado": True, "id": "x"})) as mock_tool:
        result = await cond._despachar_tool("anotar_leccion", {"contenido": "c", "contexto": "ctx"}, verbose=False)
    mock_tool.assert_awaited_once_with("c", "ctx")
    assert result == {"guardado": True, "id": "x"}


# ── _tool_crear_caso (Etapa 13, 2026-08-17) ─────────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_tool_crear_caso_exito():
    with patch("conductor._crear_caso_fn", new=AsyncMock(return_value={"success": True, "caso_id": "caso-1", "error": None})) as mock_crear:
        result = await cond._tool_crear_caso("Compostaje Norte", "Planta busca valorizar residuo.", "desde_cero", None)

    assert result == {"creado": True, "caso_id": "caso-1"}
    _, kwargs = mock_crear.call_args
    assert kwargs["nombre"] == "Compostaje Norte"
    assert kwargs["tenant"] == cond._TENANT


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tool_crear_caso_nombre_vacio_es_error():
    result = await cond._tool_crear_caso("   ", "descripción", None, None)
    assert "error" in result


@pytest.mark.unit
@pytest.mark.asyncio
async def test_tool_crear_caso_falla_en_km():
    with patch("conductor._crear_caso_fn", new=AsyncMock(return_value={"success": False, "caso_id": None, "error": "boom"})):
        result = await cond._tool_crear_caso("X", "Y", None, None)
    assert "error" in result


@pytest.mark.unit
@pytest.mark.asyncio
async def test_despachar_tool_crear_caso():
    with patch("conductor._tool_crear_caso", new=AsyncMock(return_value={"creado": True, "caso_id": "x"})) as mock_tool:
        result = await cond._despachar_tool("crear_caso", {"nombre": "N", "descripcion": "D", "estadio": "e", "notas": "n"}, verbose=False)
    mock_tool.assert_awaited_once_with("N", "D", "e", "n")
    assert result == {"creado": True, "caso_id": "x"}


# ── cerrar_sesion (trigger automático, Etapa 9) ─────────────────────────────

def _mock_response_leccion(hay_leccion: bool, contenido: str = "", contexto: str = ""):
    tool_call = type("ToolUseBlock", (), {
        "type": "tool_use", "name": "submit_leccion", "id": "tool_1",
        "input": {"hay_leccion_nueva": hay_leccion, "contenido": contenido, "contexto": contexto},
    })()
    usage = type("Usage", (), {"input_tokens": 10, "output_tokens": 5})()
    return type("Response", (), {"stop_reason": "tool_use", "content": [tool_call], "usage": usage})()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cerrar_sesion_conversacion_muy_corta_no_evalua():
    """Menos de 2 turnos reales de Sebas — ni vale la pena llamar al modelo."""
    with patch("conductor._ai_complete", new=AsyncMock()) as mock_ai:
        result = await cond.cerrar_sesion([{"role": "user", "content": "hola"}])
    mock_ai.assert_not_called()
    assert result is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cerrar_sesion_sin_leccion_nueva_no_guarda():
    messages = [
        {"role": "user", "content": "¿Qué casos tenemos?"},
        {"role": "assistant", "content": "Dos casos."},
        {"role": "user", "content": "Contame de Helios."},
        {"role": "assistant", "content": "Viene así."},
    ]
    with (
        patch("conductor.aprendizaje.ensure_area", new=AsyncMock()),
        patch("conductor.aprendizaje.leer_lecciones_caso", new=AsyncMock(return_value=[])),
        patch("conductor._ai_complete", new=AsyncMock(return_value=_mock_response_leccion(False))),
        patch("conductor.aprendizaje.guardar_leccion_caso", new=AsyncMock()) as mock_guardar,
    ):
        result = await cond.cerrar_sesion(messages)

    mock_guardar.assert_not_called()
    assert result is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cerrar_sesion_con_leccion_nueva_guarda_con_fuente_agente_auto():
    messages = [
        {"role": "user", "content": "¿Qué casos tenemos?"},
        {"role": "assistant", "content": "Dos casos."},
        {"role": "user", "content": "Contame de Helios."},
        {"role": "assistant", "content": "Viene así."},
    ]
    with (
        patch("conductor.aprendizaje.ensure_area", new=AsyncMock()),
        patch("conductor.aprendizaje.leer_lecciones_caso", new=AsyncMock(return_value=[])),
        patch("conductor._ai_complete", new=AsyncMock(return_value=_mock_response_leccion(
            True, contenido="Chequear el flete antes de avanzar.", contexto="Helios, logística",
        ))),
        patch("conductor.aprendizaje.guardar_leccion_caso", new=AsyncMock(return_value={"success": True, "id": "leccion-2"})) as mock_guardar,
    ):
        result = await cond.cerrar_sesion(messages)

    assert result == {"success": True, "id": "leccion-2"}
    _, kwargs = mock_guardar.call_args
    assert kwargs["fuente"] == "agente_auto"
    assert kwargs["contenido"] == "Chequear el flete antes de avanzar."


@pytest.mark.unit
@pytest.mark.asyncio
async def test_cerrar_sesion_no_llama_submit_leccion_se_trata_como_sin_leccion():
    messages = [
        {"role": "user", "content": "¿Qué casos tenemos?"},
        {"role": "assistant", "content": "Dos casos."},
        {"role": "user", "content": "Gracias."},
        {"role": "assistant", "content": "De nada."},
    ]
    texto_block = type("TextBlock", (), {"type": "text", "text": "no llamé la tool"})()
    usage = type("Usage", (), {"input_tokens": 1, "output_tokens": 1})()
    response = type("Response", (), {"stop_reason": "end_turn", "content": [texto_block], "usage": usage})()

    with (
        patch("conductor.aprendizaje.ensure_area", new=AsyncMock()),
        patch("conductor.aprendizaje.leer_lecciones_caso", new=AsyncMock(return_value=[])),
        patch("conductor._ai_complete", new=AsyncMock(return_value=response)),
    ):
        result = await cond.cerrar_sesion(messages)

    assert result is None


# ── enviar_mensaje — loop conversacional ────────────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_enviar_mensaje_mantiene_historial_entre_turnos():
    mock_text = type("TextBlock", (), {"type": "text", "text": "Respuesta 1"})()
    mock_usage = type("Usage", (), {"input_tokens": 10, "output_tokens": 5})()
    mock_response = type("Response", (), {"stop_reason": "end_turn", "content": [mock_text], "usage": mock_usage})()

    with patch("conductor._ai_complete", new=AsyncMock(return_value=mock_response)):
        respuesta, messages = await cond.enviar_mensaje([], "Hola")

    assert respuesta == "Respuesta 1"
    assert messages[0] == {"role": "user", "content": "Hola"}
    assert len(messages) == 2  # user + assistant

    with patch("conductor._ai_complete", new=AsyncMock(return_value=mock_response)):
        _, messages = await cond.enviar_mensaje(messages, "Segundo mensaje")

    assert len(messages) == 4
    assert messages[2] == {"role": "user", "content": "Segundo mensaje"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enviar_mensaje_despacha_tool_use():
    tool_call = type("ToolUseBlock", (), {
        "type": "tool_use", "name": "listar_casos", "id": "tool_1", "input": {},
    })()
    mock_usage = type("Usage", (), {"input_tokens": 10, "output_tokens": 5})()
    r1 = type("Response", (), {"stop_reason": "tool_use", "content": [tool_call], "usage": mock_usage})()
    mock_text = type("TextBlock", (), {"type": "text", "text": "Tenés 2 casos."})()
    r2 = type("Response", (), {"stop_reason": "end_turn", "content": [mock_text], "usage": mock_usage})()

    with (
        patch("conductor._ai_complete", new=AsyncMock(side_effect=[r1, r2])),
        patch("conductor._tool_listar_casos", new=AsyncMock(return_value={"casos": []})) as mock_listar,
    ):
        respuesta, messages = await cond.enviar_mensaje([], "¿Qué casos tenés?")

    mock_listar.assert_awaited_once()
    assert respuesta == "Tenés 2 casos."
    # el tool_result quedó en el historial
    assert any(
        isinstance(m.get("content"), list) and m["content"]
        and isinstance(m["content"][0], dict) and m["content"][0].get("type") == "tool_result"
        for m in messages
    )


# ── Integration: sesión conversacional real (solo lectura) ─────────────────

@pytest.mark.integration
@pytest.mark.asyncio
async def test_sesion_conversacional_real_sobre_helios():
    """
    Corrida real contra Anthropic + KM real — solo tools de lectura (listar_casos/ver_caso),
    sin invocar al microbiólogo (evita gastar tokens de más en cada corrida de la suite).

    Verificación explícita del plan (Etapa 5): compara el comportamiento contra lo que Sebas
    ejerció a mano el 22/07 — leer estado real antes de opinar, no inventar que un frente ya
    tiene trabajo hecho sin chequearlo.
    """
    from knowledge_module.db import reset_engine
    reset_engine()

    messages: list[dict] = []

    r1, messages = await cond.enviar_mensaje(messages, "¿Qué casos tenemos activos?", verbose=True)
    assert isinstance(r1, str) and len(r1) > 0

    r2, messages = await cond.enviar_mensaje(messages, "Contame cómo viene Helios.", verbose=True)
    assert isinstance(r2, str) and len(r2) > 0
    # el Conductor debería haber llamado ver_caso para responder esto con datos reales, no inventados
    tool_calls = [
        b.name for m in messages if isinstance(m.get("content"), list)
        for b in m["content"] if hasattr(b, "name")
    ]
    assert "ver_caso" in tool_calls, "El Conductor respondió sobre Helios sin llamar ver_caso — puede estar inventando el estado"
