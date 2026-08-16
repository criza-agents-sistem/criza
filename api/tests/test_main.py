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
