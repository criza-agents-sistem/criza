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


# ── Chat del Conductor ─────────────────────────────────────────────────────

@pytest.mark.unit
def test_crear_sesion_conductor():
    resp = client.post("/conductor/sesiones")
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]
    assert session_id
    assert session_id in api_main._sesiones_conductor


@pytest.mark.unit
def test_enviar_mensaje_sesion_inexistente():
    resp = client.post("/conductor/sesiones/no-existe/mensajes", json={"texto": "hola"})
    assert resp.status_code == 404


@pytest.mark.unit
def test_enviar_mensaje_vacio_es_400():
    session_id = client.post("/conductor/sesiones").json()["session_id"]
    resp = client.post(f"/conductor/sesiones/{session_id}/mensajes", json={"texto": "   "})
    assert resp.status_code == 400


@pytest.mark.unit
def test_enviar_mensaje_conductor_devuelve_respuesta():
    session_id = client.post("/conductor/sesiones").json()["session_id"]

    async def fake_enviar_mensaje(messages, texto, model=None, verbose=False, tracker=None):
        messages.append({"role": "user", "content": texto})
        messages.append({"role": "assistant", "content": "Hola, ¿en qué te ayudo?"})
        return "Hola, ¿en qué te ayudo?", messages

    with patch("main._enviar_mensaje_conductor", new=fake_enviar_mensaje):
        resp = client.post(f"/conductor/sesiones/{session_id}/mensajes", json={"texto": "Hola"})

    assert resp.status_code == 200
    assert resp.json()["respuesta"] == "Hola, ¿en qué te ayudo?"


@pytest.mark.unit
def test_enviar_mensaje_conductor_mantiene_historial_entre_turnos():
    """El segundo mensaje del mismo session_id debe operar sobre los mismos `messages`
    acumulados — la sesión en memoria es lo que le da memoria conversacional."""
    session_id = client.post("/conductor/sesiones").json()["session_id"]
    historiales_vistos = []

    async def fake_enviar_mensaje(messages, texto, model=None, verbose=False, tracker=None):
        historiales_vistos.append(len(messages))
        messages.append({"role": "user", "content": texto})
        messages.append({"role": "assistant", "content": "ok"})
        return "ok", messages

    with patch("main._enviar_mensaje_conductor", new=fake_enviar_mensaje):
        client.post(f"/conductor/sesiones/{session_id}/mensajes", json={"texto": "primero"})
        client.post(f"/conductor/sesiones/{session_id}/mensajes", json={"texto": "segundo"})

    assert historiales_vistos == [0, 2]  # el segundo turno arrancó con los 2 mensajes del primero


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
