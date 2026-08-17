"""
Tests de la API de solo lectura — CRIZA.

Unit: TestClient (in-process, sin servidor real) con mocks del KM.
Integration: TestClient contra el KM real.

Correr unit: pytest tests/ -m "not integration"
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

_CRIZA = Path(__file__).parent.parent.parent
_MODULE = Path(__file__).parent.parent
sys.path.insert(0, str(_CRIZA))
sys.path.insert(0, str(_MODULE))

import main as api_main

client = TestClient(api_main.app)

CASO_HELIOS = {
    "id": "caso-helios",
    "tipo": "caso",
    "props": {"nombre": "Efluentes biogás (Helios)", "descripcion": "desc", "estadio": "desde_cero"},
}
FRENTE_TECNICO = {"id": "frente-tecnico", "tipo": "frente", "props": {"nombre": "Frente técnico", "estado": "activo"}}


@pytest.mark.unit
def test_listar_casos():
    casos_mock = [CASO_HELIOS]
    with patch("main._listar_casos_fn", new=AsyncMock(return_value=casos_mock)):
        resp = client.get("/casos")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["nombre"] == "Efluentes biogás (Helios)"


# ── Crear caso (Etapa 13, 2026-08-17) ────────────────────────────────────────

@pytest.mark.unit
def test_crear_caso_exito():
    with patch("main._crear_caso_fn", new=AsyncMock(return_value={"success": True, "caso_id": "caso-nuevo-1", "error": None})) as mock_crear:
        resp = client.post("/casos", json={"nombre": "Compostaje Norte", "descripcion": "Planta de compostaje busca valorizar residuo.", "estadio": "desde_cero"})

    assert resp.status_code == 200
    assert resp.json() == {"caso_id": "caso-nuevo-1"}
    _, kwargs = mock_crear.call_args
    assert kwargs["nombre"] == "Compostaje Norte"
    assert kwargs["estadio"] == "desde_cero"


@pytest.mark.unit
def test_crear_caso_nombre_vacio_es_400():
    resp = client.post("/casos", json={"nombre": "   ", "descripcion": "algo"})
    assert resp.status_code == 400


@pytest.mark.unit
def test_crear_caso_descripcion_vacia_es_400():
    resp = client.post("/casos", json={"nombre": "algo", "descripcion": ""})
    assert resp.status_code == 400


@pytest.mark.unit
def test_crear_caso_falla_en_km_es_500():
    with patch("main._crear_caso_fn", new=AsyncMock(return_value={"success": False, "caso_id": None, "error": "boom"})):
        resp = client.post("/casos", json={"nombre": "X", "descripcion": "Y"})
    assert resp.status_code == 500


@pytest.mark.unit
def test_obtener_caso_no_encontrado():
    with patch("main.motor_api.obtener", new=AsyncMock(return_value=None)):
        resp = client.get("/casos/no-existe")
    assert resp.status_code == 404


@pytest.mark.unit
def test_obtener_caso_completo():
    with (
        patch("main.motor_api.obtener", new=AsyncMock(return_value=CASO_HELIOS)),
        patch("main._obtener_frentes_fn", new=AsyncMock(return_value=[FRENTE_TECNICO])),
        patch("main._obtener_documentos_fn", new=AsyncMock(return_value=[
            {"id": "doc-1", "props": {"titulo": "Evaluación", "modo": "chat", "estado": "borrador"}},
        ])),
        patch("main.motor_api.conexiones_de", new=AsyncMock(return_value=[])),
        patch("main._obtener_pendientes_fn", new=AsyncMock(return_value=[
            {"id": "p1", "props": {"descripcion": "Confirmar flete", "estado": "abierto"}},
        ])),
    ):
        resp = client.get("/casos/caso-helios")

    assert resp.status_code == 200
    data = resp.json()
    assert data["nombre"] == "Efluentes biogás (Helios)"
    assert len(data["frentes"]) == 1
    assert data["frentes"][0]["documentos"][0]["titulo"] == "Evaluación"
    assert data["pendientes"][0]["descripcion"] == "Confirmar flete"


@pytest.mark.unit
def test_obtener_documento_no_encontrado():
    with patch("main.motor_api.obtener", new=AsyncMock(return_value=None)):
        resp = client.get("/documentos/no-existe")
    assert resp.status_code == 404


@pytest.mark.unit
def test_obtener_documento_encontrado():
    doc = {"id": "doc-1", "tipo": "documento_caso", "props": {"titulo": "t", "contenido": "c", "modo": "chat", "estado": "borrador", "agente": "microbiologo"}}
    with patch("main.motor_api.obtener", new=AsyncMock(return_value=doc)):
        resp = client.get("/documentos/doc-1")
    assert resp.status_code == 200
    assert resp.json()["contenido"] == "c"


@pytest.mark.unit
def test_obtener_documento_id_de_otro_tipo_es_404():
    """Pasar el id de un caso (no un documento) no debe devolver datos de otro tipo."""
    with patch("main.motor_api.obtener", new=AsyncMock(return_value=CASO_HELIOS)):
        resp = client.get("/documentos/caso-helios")
    assert resp.status_code == 404


# ── Descargar documento (Etapa 14, 2026-08-17) ───────────────────────────────

@pytest.mark.unit
def test_slug_archivo_normaliza_acentos_y_simbolos():
    assert api_main._slug_archivo("Evaluación — microbiologo") == "evaluacion-microbiologo"


@pytest.mark.unit
def test_slug_archivo_vacio_usa_fallback():
    assert api_main._slug_archivo("") == "documento"


@pytest.mark.unit
def test_descargar_documento_ok():
    doc = {"id": "doc-1", "tipo": "documento_caso", "props": {"titulo": "Evaluación — microbiologo", "contenido": "# Informe\n\ncontenido real"}}
    with patch("main.motor_api.obtener", new=AsyncMock(return_value=doc)):
        resp = client.get("/documentos/doc-1/descargar")
    assert resp.status_code == 200
    assert resp.text == "# Informe\n\ncontenido real"
    assert resp.headers["content-type"].startswith("text/markdown")
    assert 'filename="evaluacion-microbiologo.md"' in resp.headers["content-disposition"]
    assert "attachment" in resp.headers["content-disposition"]


@pytest.mark.unit
def test_descargar_documento_no_encontrado():
    with patch("main.motor_api.obtener", new=AsyncMock(return_value=None)):
        resp = client.get("/documentos/no-existe/descargar")
    assert resp.status_code == 404


@pytest.mark.unit
def test_descargar_documento_otro_tipo_es_404():
    with patch("main.motor_api.obtener", new=AsyncMock(return_value=CASO_HELIOS)):
        resp = client.get("/documentos/caso-helios/descargar")
    assert resp.status_code == 404


# ── Elegir modelo por sesión (Etapa 15, 2026-08-17) ─────────────────────────────

@pytest.mark.unit
def test_listar_modelos():
    resp = client.get("/modelos")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 4
    ids = {m["id"] for m in data}
    assert "claude-sonnet-4-6" in ids
    assert all({"id", "nombre", "nota"} <= m.keys() for m in data)


# ── Chat del Conductor — sesiones persistidas en el KM, no en memoria ──────────

@pytest.mark.unit
def test_crear_sesion_conductor():
    with (
        patch("main.load_plantilla", new=AsyncMock(return_value={})),
        patch("main.motor_api.guardar_ficha", new=AsyncMock(return_value={"success": True, "id": "sesion-1"})) as mock_guardar,
    ):
        resp = client.post("/conductor/sesiones")

    assert resp.status_code == 200
    assert resp.json()["session_id"] == "sesion-1"
    _, kwargs = mock_guardar.call_args
    assert kwargs["area"] == "conductor_sesiones"
    assert kwargs["campos"]["mensajes"] == []


@pytest.mark.unit
def test_crear_sesion_conductor_con_modelo_elegido():
    with (
        patch("main.load_plantilla", new=AsyncMock(return_value={})),
        patch("main.motor_api.guardar_ficha", new=AsyncMock(return_value={"success": True, "id": "sesion-1"})) as mock_guardar,
    ):
        resp = client.post("/conductor/sesiones", json={"modelo": "claude-opus-5"})

    assert resp.status_code == 200
    _, kwargs = mock_guardar.call_args
    assert kwargs["campos"]["modelo"] == "claude-opus-5"


@pytest.mark.unit
def test_crear_sesion_conductor_sin_body_queda_modelo_none():
    """El body es opcional (test_crear_sesion_conductor de arriba ya lo cubre sin json=) — acá
    se confirma explícitamente que el campo persistido es None, no que falte la clave."""
    with (
        patch("main.load_plantilla", new=AsyncMock(return_value={})),
        patch("main.motor_api.guardar_ficha", new=AsyncMock(return_value={"success": True, "id": "sesion-1"})) as mock_guardar,
    ):
        resp = client.post("/conductor/sesiones")

    assert resp.status_code == 200
    _, kwargs = mock_guardar.call_args
    assert kwargs["campos"]["modelo"] is None


@pytest.mark.unit
def test_crear_sesion_conductor_falla_al_guardar_es_500():
    with (
        patch("main.load_plantilla", new=AsyncMock(return_value={})),
        patch("main.motor_api.guardar_ficha", new=AsyncMock(return_value={"success": False, "error": "boom"})),
    ):
        resp = client.post("/conductor/sesiones")
    assert resp.status_code == 500


@pytest.mark.unit
def test_enviar_mensaje_sesion_inexistente():
    with patch("main.motor_api.obtener", new=AsyncMock(return_value=None)):
        resp = client.post("/conductor/sesiones/no-existe/mensajes", json={"texto": "hola"})
    assert resp.status_code == 404


@pytest.mark.unit
def test_enviar_mensaje_session_id_invalido_es_404_no_500():
    """Un session_id que no es un UUID válido rompe la query SQL — se captura y se trata igual
    que 'no encontrada', no como un error de servidor."""
    with patch("main.motor_api.obtener", new=AsyncMock(side_effect=Exception("invalid input syntax for type uuid"))):
        resp = client.post("/conductor/sesiones/no-es-un-uuid/mensajes", json={"texto": "hola"})
    assert resp.status_code == 404


@pytest.mark.unit
def test_enviar_mensaje_vacio_es_400():
    resp = client.post("/conductor/sesiones/cualquier-id/mensajes", json={"texto": "   "})
    assert resp.status_code == 400


@pytest.mark.unit
def test_enviar_mensaje_conductor_devuelve_respuesta():
    sesion = {"id": "sesion-1", "tipo": "sesion", "props": {"mensajes": []}}

    async def fake_enviar_mensaje(messages, texto, model=None, verbose=False, tracker=None):
        messages.append({"role": "user", "content": texto})
        messages.append({"role": "assistant", "content": "Hola, ¿en qué te ayudo?"})
        return "Hola, ¿en qué te ayudo?", messages

    with (
        patch("main.motor_api.obtener", new=AsyncMock(return_value=sesion)),
        patch("main.motor_api.actualizar_props", new=AsyncMock(return_value={"success": True})) as mock_actualizar,
        patch("main._enviar_mensaje_conductor", new=fake_enviar_mensaje),
    ):
        resp = client.post("/conductor/sesiones/sesion-1/mensajes", json={"texto": "Hola"})

    assert resp.status_code == 200
    assert resp.json()["respuesta"] == "Hola, ¿en qué te ayudo?"
    args, _ = mock_actualizar.call_args
    assert args[0] == "sesion-1"
    assert len(args[1]["mensajes"]) == 2  # persistió el historial actualizado


@pytest.mark.unit
def test_enviar_mensaje_conductor_mantiene_historial_entre_turnos():
    """El segundo mensaje del mismo session_id debe arrancar con los mensajes que el primer
    turno persistió — la memoria conversacional viene de leer el KM, no de un dict en memoria."""
    km_fake: dict[str, list] = {"sesion-1": []}
    historiales_vistos = []

    async def fake_obtener(ficha_id, *, tenant):
        return {"id": ficha_id, "tipo": "sesion", "props": {"mensajes": km_fake[ficha_id]}}

    async def fake_actualizar_props(ficha_id, cambios, *, tenant):
        km_fake[ficha_id] = cambios["mensajes"]
        return {"success": True}

    async def fake_enviar_mensaje(messages, texto, model=None, verbose=False, tracker=None):
        historiales_vistos.append(len(messages))
        messages.append({"role": "user", "content": texto})
        messages.append({"role": "assistant", "content": "ok"})
        return "ok", messages

    with (
        patch("main.motor_api.obtener", new=fake_obtener),
        patch("main.motor_api.actualizar_props", new=fake_actualizar_props),
        patch("main._enviar_mensaje_conductor", new=fake_enviar_mensaje),
    ):
        client.post("/conductor/sesiones/sesion-1/mensajes", json={"texto": "primero"})
        client.post("/conductor/sesiones/sesion-1/mensajes", json={"texto": "segundo"})

    assert historiales_vistos == [0, 2]  # el segundo turno arrancó con los 2 mensajes que quedaron del primero


@pytest.mark.unit
def test_enviar_mensaje_conductor_pasa_modelo_elegido_a_la_sesion():
    sesion = {"id": "sesion-1", "tipo": "sesion", "props": {"mensajes": [], "modelo": "claude-haiku-4-5-20251001"}}
    kwargs_vistos = {}

    async def fake_enviar_mensaje(messages, texto, model=None, verbose=False, tracker=None):
        kwargs_vistos["model"] = model
        messages.append({"role": "user", "content": texto})
        messages.append({"role": "assistant", "content": "ok"})
        return "ok", messages

    with (
        patch("main.motor_api.obtener", new=AsyncMock(return_value=sesion)),
        patch("main.motor_api.actualizar_props", new=AsyncMock(return_value={"success": True})),
        patch("main._enviar_mensaje_conductor", new=fake_enviar_mensaje),
    ):
        resp = client.post("/conductor/sesiones/sesion-1/mensajes", json={"texto": "hola"})

    assert resp.status_code == 200
    assert kwargs_vistos["model"] == "claude-haiku-4-5-20251001"


@pytest.mark.unit
def test_enviar_mensaje_conductor_sin_modelo_no_fuerza_override():
    """Sesión sin `modelo` (creada antes de la Etapa 15, o sin elegir uno) — no debe pasarse
    `model=` al agente, para que siga usando su default (env var del agente)."""
    sesion = {"id": "sesion-1", "tipo": "sesion", "props": {"mensajes": []}}
    kwargs_vistos = {}

    async def fake_enviar_mensaje(messages, texto, model=None, verbose=False, tracker=None):
        kwargs_vistos["model"] = model
        messages.append({"role": "user", "content": texto})
        messages.append({"role": "assistant", "content": "ok"})
        return "ok", messages

    with (
        patch("main.motor_api.obtener", new=AsyncMock(return_value=sesion)),
        patch("main.motor_api.actualizar_props", new=AsyncMock(return_value={"success": True})),
        patch("main._enviar_mensaje_conductor", new=fake_enviar_mensaje),
    ):
        resp = client.post("/conductor/sesiones/sesion-1/mensajes", json={"texto": "hola"})

    assert resp.status_code == 200
    assert kwargs_vistos["model"] is None


@pytest.mark.unit
def test_cerrar_sesion_conductor_no_encontrada():
    with patch("main.motor_api.obtener", new=AsyncMock(return_value=None)):
        resp = client.post("/conductor/sesiones/no-existe/cerrar")
    assert resp.status_code == 404


@pytest.mark.unit
def test_cerrar_sesion_conductor_con_leccion():
    sesion = {"id": "sesion-1", "tipo": "sesion", "props": {"mensajes": [{"role": "user", "content": "hola"}]}}
    with (
        patch("main.motor_api.obtener", new=AsyncMock(return_value=sesion)),
        patch("main._cerrar_sesion_conductor", new=AsyncMock(return_value={"success": True, "id": "leccion-1"})),
    ):
        resp = client.post("/conductor/sesiones/sesion-1/cerrar")
    assert resp.status_code == 200
    assert resp.json() == {"leccion_guardada": True, "id": "leccion-1"}


@pytest.mark.unit
def test_cerrar_sesion_conductor_sin_leccion():
    sesion = {"id": "sesion-1", "tipo": "sesion", "props": {"mensajes": []}}
    with (
        patch("main.motor_api.obtener", new=AsyncMock(return_value=sesion)),
        patch("main._cerrar_sesion_conductor", new=AsyncMock(return_value=None)),
    ):
        resp = client.post("/conductor/sesiones/sesion-1/cerrar")
    assert resp.status_code == 200
    assert resp.json() == {"leccion_guardada": False, "id": None}


# ── Chat con un especialista puntual (Etapa 10, 2026-08-16) ────────────────────

@pytest.mark.unit
def test_crear_sesion_especialista_nombre_invalido():
    resp = client.post("/especialistas/no-existe/sesiones", json={"frente_id": "f1"})
    assert resp.status_code == 404


@pytest.mark.unit
def test_crear_sesion_especialista_ok():
    with (
        patch("main._mod_microbiologo.iniciar_sesion", new=AsyncMock(return_value=[{"role": "user", "content": "contexto inicial"}])),
        patch("main.load_plantilla", new=AsyncMock(return_value={})),
        patch("main.motor_api.guardar_ficha", new=AsyncMock(return_value={"success": True, "id": "sesion-esp-1"})) as mock_guardar,
    ):
        resp = client.post("/especialistas/microbiologo/sesiones", json={"frente_id": "frente-1"})

    assert resp.status_code == 200
    assert resp.json() == {"session_id": "sesion-esp-1"}
    _, kwargs = mock_guardar.call_args
    assert kwargs["area"] == "especialista_sesiones"
    assert kwargs["campos"]["especialista"] == "microbiologo"
    assert kwargs["campos"]["frente_id"] == "frente-1"


@pytest.mark.unit
def test_crear_sesion_especialista_con_modelo_elegido():
    with (
        patch("main._mod_microbiologo.iniciar_sesion", new=AsyncMock(return_value=[{"role": "user", "content": "contexto inicial"}])),
        patch("main.load_plantilla", new=AsyncMock(return_value={})),
        patch("main.motor_api.guardar_ficha", new=AsyncMock(return_value={"success": True, "id": "sesion-esp-1"})) as mock_guardar,
    ):
        resp = client.post("/especialistas/microbiologo/sesiones", json={"frente_id": "frente-1", "modelo": "claude-sonnet-5"})

    assert resp.status_code == 200
    _, kwargs = mock_guardar.call_args
    assert kwargs["campos"]["modelo"] == "claude-sonnet-5"


@pytest.mark.unit
def test_crear_sesion_especialista_frente_no_encontrado_es_404():
    with patch("main._mod_microbiologo.iniciar_sesion", new=AsyncMock(side_effect=ValueError("Frente no encontrado en el KM"))):
        resp = client.post("/especialistas/microbiologo/sesiones", json={"frente_id": "no-existe"})
    assert resp.status_code == 404


@pytest.mark.unit
def test_crear_sesion_especialista_consulta_libre_sin_frente_id():
    """Etapa 12 — sin frente_id en el body, no debe llamar iniciar_sesion (no hay contexto de
    caso que armar) y la ficha se crea con frente_id=None."""
    with (
        patch("main._mod_microbiologo.iniciar_sesion", new=AsyncMock()) as mock_iniciar,
        patch("main.load_plantilla", new=AsyncMock(return_value={})),
        patch("main.motor_api.guardar_ficha", new=AsyncMock(return_value={"success": True, "id": "sesion-libre-1"})) as mock_guardar,
    ):
        resp = client.post("/especialistas/microbiologo/sesiones", json={})

    assert resp.status_code == 200
    assert resp.json() == {"session_id": "sesion-libre-1"}
    mock_iniciar.assert_not_awaited()
    _, kwargs = mock_guardar.call_args
    assert kwargs["campos"]["frente_id"] is None
    assert kwargs["campos"]["mensajes"] == []


@pytest.mark.unit
def test_enviar_mensaje_especialista_sesion_inexistente():
    with patch("main.motor_api.obtener", new=AsyncMock(return_value=None)):
        resp = client.post("/especialistas/sesiones/no-existe/mensajes", json={"texto": "hola"})
    assert resp.status_code == 404


@pytest.mark.unit
def test_enviar_mensaje_especialista_vacio_es_400():
    resp = client.post("/especialistas/sesiones/cualquier-id/mensajes", json={"texto": "   "})
    assert resp.status_code == 400


@pytest.mark.unit
def test_enviar_mensaje_especialista_devuelve_respuesta():
    sesion = {"id": "sesion-esp-1", "tipo": "sesion_especialista", "props": {"especialista": "microbiologo", "frente_id": "frente-1", "mensajes": []}}

    async def fake_enviar_mensaje(messages, texto, frente_id):
        messages.append({"role": "user", "content": texto})
        messages.append({"role": "assistant", "content": "Respuesta del microbiólogo"})
        return "Respuesta del microbiólogo", messages

    with (
        patch("main.motor_api.obtener", new=AsyncMock(return_value=sesion)),
        patch("main.motor_api.actualizar_props", new=AsyncMock(return_value={"success": True})),
        patch("main._mod_microbiologo.enviar_mensaje", new=fake_enviar_mensaje),
    ):
        resp = client.post("/especialistas/sesiones/sesion-esp-1/mensajes", json={"texto": "¿Qué opinás?"})

    assert resp.status_code == 200
    assert resp.json()["respuesta"] == "Respuesta del microbiólogo"


@pytest.mark.unit
def test_enviar_mensaje_especialista_pasa_modelo_elegido():
    sesion = {"id": "sesion-esp-1", "tipo": "sesion_especialista", "props": {"especialista": "microbiologo", "frente_id": "frente-1", "mensajes": [], "modelo": "claude-haiku-4-5-20251001"}}
    kwargs_vistos = {}

    async def fake_enviar_mensaje(messages, texto, frente_id, model=None):
        kwargs_vistos["model"] = model
        messages.append({"role": "user", "content": texto})
        messages.append({"role": "assistant", "content": "ok"})
        return "ok", messages

    with (
        patch("main.motor_api.obtener", new=AsyncMock(return_value=sesion)),
        patch("main.motor_api.actualizar_props", new=AsyncMock(return_value={"success": True})),
        patch("main._mod_microbiologo.enviar_mensaje", new=fake_enviar_mensaje),
    ):
        resp = client.post("/especialistas/sesiones/sesion-esp-1/mensajes", json={"texto": "hola"})

    assert resp.status_code == 200
    assert kwargs_vistos["model"] == "claude-haiku-4-5-20251001"


@pytest.mark.unit
def test_enviar_mensaje_especialista_sin_modelo_no_fuerza_override():
    sesion = {"id": "sesion-esp-1", "tipo": "sesion_especialista", "props": {"especialista": "microbiologo", "frente_id": "frente-1", "mensajes": []}}
    kwargs_vistos = {}

    async def fake_enviar_mensaje(messages, texto, frente_id, model=None):
        kwargs_vistos["model"] = model
        messages.append({"role": "user", "content": texto})
        messages.append({"role": "assistant", "content": "ok"})
        return "ok", messages

    with (
        patch("main.motor_api.obtener", new=AsyncMock(return_value=sesion)),
        patch("main.motor_api.actualizar_props", new=AsyncMock(return_value={"success": True})),
        patch("main._mod_microbiologo.enviar_mensaje", new=fake_enviar_mensaje),
    ):
        resp = client.post("/especialistas/sesiones/sesion-esp-1/mensajes", json={"texto": "hola"})

    assert resp.status_code == 200
    assert kwargs_vistos["model"] is None


# ── Características de un agente (Etapa 11, 2026-08-16) ─────────────────────────

@pytest.mark.unit
def test_obtener_info_agente_nombre_invalido():
    resp = client.get("/agentes/no-existe")
    assert resp.status_code == 404


@pytest.mark.unit
def test_obtener_info_agente_conductor():
    resp = client.get("/agentes/conductor")
    assert resp.status_code == 200
    data = resp.json()
    assert data["nombre"] == "conductor"
    assert data["system_prompt"]
    nombres = {t["name"] for t in data["tools"]}
    assert "ver_caso" in nombres
    # el Conductor no distingue chat de corrida formal — todas sus tools están disponibles en chat
    assert all(t["disponible_en_chat"] for t in data["tools"])


@pytest.mark.unit
def test_obtener_info_agente_especialista_marca_submit_fuera_del_chat():
    resp = client.get("/agentes/microbiologo")
    assert resp.status_code == 200
    data = resp.json()
    tools_por_nombre = {t["name"]: t for t in data["tools"]}
    assert tools_por_nombre["submit_evaluacion_tecnica"]["disponible_en_chat"] is False
    assert tools_por_nombre["search_kegg"]["disponible_en_chat"] is True


@pytest.mark.unit
def test_cors_permite_localhost_3000():
    resp = client.options(
        "/casos",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"


# ── Integration: contra el KM real ──────────────────────────────────────────
#
# httpx.AsyncClient (no el TestClient síncrono) — el TestClient síncrono crea un event loop
# nuevo por request, y el engine async de knowledge_module cachea un pool de conexiones atado
# al loop de la PRIMERA request; en la segunda request, con un loop distinto, revienta con
# "Event loop is closed" al cerrar conexiones huérfanas. AsyncClient corre dentro del mismo
# loop que el test (pytest-asyncio), igual que un server real (uvicorn) sirve todo un mismo loop.

@pytest.mark.integration
@pytest.mark.asyncio
async def test_listar_y_obtener_caso_real():
    """Corrida real contra el KM — Helios/MicroBigs ya cargados."""
    from knowledge_module.db import reset_engine
    reset_engine()

    transport = httpx.ASGITransport(app=api_main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/casos")
        assert resp.status_code == 200
        casos = resp.json()
        assert len(casos) >= 2
        helios = next(c for c in casos if "Helios" in c["nombre"])

        resp2 = await ac.get(f"/casos/{helios['id']}")
        assert resp2.status_code == 200
        detalle = resp2.json()
        assert len(detalle["frentes"]) >= 2
        assert isinstance(detalle["pendientes"], list)
