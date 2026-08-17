"""
Tests para criza/utils/casos.py

Unit tests: mock de motor_api. Integration: pytest -m integration, contra el KM real —
usa el branch de staging (ver docs/STAGING.md), no producción.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

_CRIZA = Path(__file__).parent.parent.parent
if str(_CRIZA) not in sys.path:
    sys.path.insert(0, str(_CRIZA))

import utils.casos as casos


# ── Unit: obtener_frente_con_caso ───────────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_obtener_frente_con_caso_encuentra_ambos():
    frente = {"id": "frente-1", "tipo": "frente", "props": {"nombre": "Frente técnico"}}
    caso = {"id": "caso-1", "tipo": "caso", "props": {"nombre": "Helios"}}

    with (
        patch("utils.casos.motor_api.obtener", new=AsyncMock(return_value=frente)),
        patch("utils.casos.motor_api.conexiones_de", new=AsyncMock(return_value=[caso])),
    ):
        result = await casos.obtener_frente_con_caso("frente-1", tenant="criza")

    assert result["frente"] == frente
    assert result["caso"] == caso


@pytest.mark.unit
@pytest.mark.asyncio
async def test_obtener_frente_con_caso_frente_inexistente():
    with patch("utils.casos.motor_api.obtener", new=AsyncMock(return_value=None)):
        result = await casos.obtener_frente_con_caso("no-existe", tenant="criza")

    assert result["frente"] is None
    assert result["caso"] is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_obtener_frente_con_caso_sin_conexion_entrante():
    frente = {"id": "frente-1", "tipo": "frente", "props": {}}
    with (
        patch("utils.casos.motor_api.obtener", new=AsyncMock(return_value=frente)),
        patch("utils.casos.motor_api.conexiones_de", new=AsyncMock(return_value=[])),
    ):
        result = await casos.obtener_frente_con_caso("frente-1", tenant="criza")

    assert result["frente"] == frente
    assert result["caso"] is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_obtener_frente_con_caso_usa_direccion_entrante():
    frente = {"id": "frente-1", "tipo": "frente", "props": {}}
    with (
        patch("utils.casos.motor_api.obtener", new=AsyncMock(return_value=frente)),
        patch("utils.casos.motor_api.conexiones_de", new=AsyncMock(return_value=[])) as mock_conn,
    ):
        await casos.obtener_frente_con_caso("frente-1", tenant="criza")

    mock_conn.assert_awaited_once_with(
        "frente-1", tipo_conexion="tiene_frente", direccion="entrantes", tenant="criza"
    )


# ── Unit: obtener_pendientes_de_caso ────────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_obtener_pendientes_filtra_resueltos_por_default():
    pendientes = [
        {"id": "p1", "props": {"estado": "abierto"}},
        {"id": "p2", "props": {"estado": "resuelto"}},
    ]
    with patch("utils.casos.motor_api.conexiones_de", new=AsyncMock(return_value=pendientes)):
        result = await casos.obtener_pendientes_de_caso("caso-1", tenant="criza")

    assert len(result) == 1
    assert result[0]["id"] == "p1"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_obtener_pendientes_incluye_resueltos_si_se_pide():
    pendientes = [
        {"id": "p1", "props": {"estado": "abierto"}},
        {"id": "p2", "props": {"estado": "resuelto"}},
    ]
    with patch("utils.casos.motor_api.conexiones_de", new=AsyncMock(return_value=pendientes)):
        result = await casos.obtener_pendientes_de_caso("caso-1", tenant="criza", solo_abiertos=False)

    assert len(result) == 2


# ── Unit: guardar_documento_de_frente ───────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_guardar_documento_de_frente_exito():
    with (
        patch("utils.casos.motor_api.guardar_ficha", new=AsyncMock(return_value={"success": True, "id": "doc-1"})),
        patch("utils.casos.motor_api.guardar_conexion", new=AsyncMock(return_value={"success": True, "id": "conn-1"})) as mock_conn,
    ):
        result = await casos.guardar_documento_de_frente(
            frente_id="frente-1", titulo="Evaluación", contenido="texto", tenant="criza",
            analisis_estructurado={"x": 1}, agente="microbiologo",
        )

    assert result == {"success": True, "documento_id": "doc-1", "error": None}
    mock_conn.assert_awaited_once_with(
        area="casos", tipo="frente_produce_documento",
        desde_ficha_id="frente-1", hacia_ficha_id="doc-1", tenant="criza",
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_guardar_documento_de_frente_falla_al_crear_ficha():
    with patch("utils.casos.motor_api.guardar_ficha", new=AsyncMock(return_value={"success": False, "error": "boom"})):
        result = await casos.guardar_documento_de_frente(
            frente_id="frente-1", titulo="t", contenido="c", tenant="criza",
        )

    assert result["success"] is False
    assert result["documento_id"] is None
    assert result["error"] == "boom"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_guardar_documento_de_frente_falla_al_conectar():
    with (
        patch("utils.casos.motor_api.guardar_ficha", new=AsyncMock(return_value={"success": True, "id": "doc-1"})),
        patch("utils.casos.motor_api.guardar_conexion", new=AsyncMock(return_value={"success": False, "error": "no existe frente"})),
    ):
        result = await casos.guardar_documento_de_frente(
            frente_id="frente-inexistente", titulo="t", contenido="c", tenant="criza",
        )

    assert result["success"] is False
    assert result["documento_id"] == "doc-1"  # el documento sí se creó, aunque la conexión falló
    assert result["error"] == "no existe frente"


# ── Unit: crear_caso (Etapa 13, 2026-08-17) ─────────────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_crear_caso_exito_computa_texto_busqueda():
    with patch("utils.casos.motor_api.guardar_ficha", new=AsyncMock(return_value={"success": True, "id": "caso-1"})) as mock_guardar:
        result = await casos.crear_caso(
            nombre="Compostaje Norte", descripcion="Planta de compostaje busca valorizar residuo.",
            tenant="criza", estadio="desde_cero",
        )

    assert result == {"success": True, "caso_id": "caso-1", "error": None}
    _, kwargs = mock_guardar.call_args
    assert kwargs["area"] == "casos"
    assert kwargs["tipo"] == "caso"
    assert kwargs["campos"]["texto_busqueda"] == "Compostaje Norte. Planta de compostaje busca valorizar residuo."
    assert kwargs["campos"]["estadio"] == "desde_cero"
    assert kwargs["campos"]["participantes"] == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_crear_caso_falla():
    with patch("utils.casos.motor_api.guardar_ficha", new=AsyncMock(return_value={"success": False, "error": "boom"})):
        result = await casos.crear_caso(nombre="X", descripcion="Y", tenant="criza")

    assert result == {"success": False, "caso_id": None, "error": "boom"}


# ── Integration: contra el KM real (branch de staging) ──────────────────────────

@pytest.mark.integration
@pytest.mark.asyncio
async def test_obtener_frente_con_caso_real():
    """Corrida real contra Helios (caso ya cargado, ver config/plantillas/casos.yaml)."""
    from knowledge_module.db import reset_engine
    from knowledge_module.motor import api as motor_api

    reset_engine()
    casos_reales = await motor_api.listar(area="casos", tipo="caso", tenant="criza", limit=10)
    helios = next(c for c in casos_reales if "Helios" in c["props"].get("nombre", ""))
    frentes = await motor_api.conexiones_de(helios["id"], tipo_conexion="tiene_frente", tenant="criza")
    frente_tecnico = next(f for f in frentes if "técnico" in f["props"].get("nombre", "").lower())

    result = await casos.obtener_frente_con_caso(frente_tecnico["id"], tenant="criza")

    assert result["frente"] is not None
    assert result["caso"] is not None
    assert result["caso"]["id"] == helios["id"]
