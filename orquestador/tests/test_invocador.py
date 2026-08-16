"""
Tests — La costura (orquestador/invocador.py)

Markers:
  unit → sin red, sin DB (mocks)
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

_CRIZA = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_CRIZA))

from orquestador.invocador import invocar_agente
from orquestador.registry import AgentSpec


def _spec(nombre: str, run_fn, prop_key: str | None = None) -> AgentSpec:
    return AgentSpec(
        nombre=nombre, modulo="", descripcion="", prop_key=prop_key or nombre,
        activo=run_fn is not None, run_fn=run_fn,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_invocar_agente_persiste_analisis_bajo_prop_key():
    """El resultado de análisis debe quedar en props[prop_key], genérico — sin casos
    especiales por agente."""
    run_fn = AsyncMock(return_value={
        "análisis": {"cruce_1": {"x": 1}, "informe_completo": "texto"},
        "nivel_confianza": "medio",
        "recomendaciones": [],
        "próximo_agente": None,
        "nuevo_conocimiento": [],
    })
    spec = _spec("mercado", run_fn)

    with patch("orquestador.invocador.motor_api.actualizar_props", new_callable=AsyncMock) as mock_ap:
        output = await invocar_agente(
            spec=spec,
            contract_input={"caso": "test"},
            tenant="criza",
            oportunidad_id="uuid-1",
            verbose=False,
        )

    mock_ap.assert_awaited_once_with(
        "uuid-1",
        {"mercado": {"cruce_1": {"x": 1}, "informe_completo": "texto"}},
        tenant="criza",
    )
    assert output["análisis"]["informe_completo"] == "texto"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_invocar_agente_usa_prop_key_declarado_no_el_nombre():
    """prop_key puede diferir del nombre del agente — la costura respeta el registro, no
    asume que son lo mismo."""
    run_fn = AsyncMock(return_value={"análisis": {"informe_completo": "x"}})
    spec = _spec("cientifico_microbiologo", run_fn, prop_key="microbiologo_v1")

    with patch("orquestador.invocador.motor_api.actualizar_props", new_callable=AsyncMock) as mock_ap:
        await invocar_agente(spec, {}, tenant="criza", oportunidad_id="uuid-2")

    args, kwargs = mock_ap.call_args
    assert "microbiologo_v1" in args[1]
    assert "cientifico_microbiologo" not in args[1]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_invocar_agente_sin_oportunidad_id_no_persiste():
    """Sin oportunidad_id (ej. exploración sin caso todavía creado) no hay dónde persistir —
    no debe intentar escribir al KM ni romper."""
    run_fn = AsyncMock(return_value={"análisis": {"informe_completo": "x"}})
    spec = _spec("mercado", run_fn)

    with patch("orquestador.invocador.motor_api.actualizar_props", new_callable=AsyncMock) as mock_ap:
        output = await invocar_agente(spec, {}, tenant="criza", oportunidad_id=None)

    mock_ap.assert_not_awaited()
    assert output["análisis"]["informe_completo"] == "x"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_invocar_agente_sin_analisis_no_escribe_prop_vacia():
    """Si el agente no llegó a producir análisis (ej. truncado, sin submit), no escribir
    props[prop_key] con None — mejor nada que un valor falso."""
    run_fn = AsyncMock(return_value={"análisis": None, "nivel_confianza": "bajo"})
    spec = _spec("mercado", run_fn)

    with patch("orquestador.invocador.motor_api.actualizar_props", new_callable=AsyncMock) as mock_ap:
        await invocar_agente(spec, {}, tenant="criza", oportunidad_id="uuid-3")

    mock_ap.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_invocar_agente_sin_run_fn_levanta_valueerror():
    """Invocar un agente inactivo/sin cargar es un bug del llamador — no se saltea en
    silencio acá (motor.py es quien decide saltear, ver test_motor.py)."""
    spec = _spec("cientifico_especialista", None)

    with pytest.raises(ValueError, match="no disponible"):
        await invocar_agente(spec, {}, tenant="criza", oportunidad_id="uuid-4")


# ── frente_id — modelo de casos.yaml (Etapa 4, 2026-08-16) ──────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_invocar_agente_con_frente_id_guarda_documento_de_frente():
    run_fn = AsyncMock(return_value={
        "análisis": {"evaluacion_tecnica": {}, "informe_completo": "texto del informe"},
        "nivel_confianza": "medio",
        "recomendaciones": [],
        "próximo_agente": None,
        "nuevo_conocimiento": [],
    })
    spec = _spec("microbiologo", run_fn)

    with patch("orquestador.invocador.guardar_documento_de_frente", new_callable=AsyncMock) as mock_guardar:
        mock_guardar.return_value = {"success": True, "documento_id": "doc-1", "error": None}
        output = await invocar_agente(
            spec=spec, contract_input={"conocimiento": {"frente_id": "frente-1"}},
            tenant="criza", frente_id="frente-1", verbose=False,
        )

    mock_guardar.assert_awaited_once_with(
        frente_id="frente-1",
        titulo="Evaluación — microbiologo",
        contenido="texto del informe",
        tenant="criza",
        analisis_estructurado={"evaluacion_tecnica": {}, "informe_completo": "texto del informe"},
        agente="microbiologo",
    )
    assert output["análisis"]["informe_completo"] == "texto del informe"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_invocar_agente_con_frente_id_no_toca_props_de_oportunidad():
    """frente_id y oportunidad_id son caminos separados — invocar con frente_id nunca debe
    llamar actualizar_props (eso es solo del camino oportunidad_id)."""
    run_fn = AsyncMock(return_value={"análisis": {"informe_completo": "x"}})
    spec = _spec("microbiologo", run_fn)

    with (
        patch("orquestador.invocador.motor_api.actualizar_props", new_callable=AsyncMock) as mock_ap,
        patch("orquestador.invocador.guardar_documento_de_frente", new_callable=AsyncMock,
              return_value={"success": True, "documento_id": "doc-1", "error": None}),
    ):
        await invocar_agente(spec, {}, tenant="criza", frente_id="frente-1")

    mock_ap.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_invocar_agente_sin_analisis_no_guarda_documento():
    run_fn = AsyncMock(return_value={"análisis": None})
    spec = _spec("microbiologo", run_fn)

    with patch("orquestador.invocador.guardar_documento_de_frente", new_callable=AsyncMock) as mock_guardar:
        await invocar_agente(spec, {}, tenant="criza", frente_id="frente-1")

    mock_guardar.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_invocar_agente_sin_oportunidad_id_ni_frente_id_no_persiste():
    """Ninguno de los dos identificadores — no hay dónde persistir, no debe romper."""
    run_fn = AsyncMock(return_value={"análisis": {"informe_completo": "x"}})
    spec = _spec("microbiologo", run_fn)

    with (
        patch("orquestador.invocador.motor_api.actualizar_props", new_callable=AsyncMock) as mock_ap,
        patch("orquestador.invocador.guardar_documento_de_frente", new_callable=AsyncMock) as mock_guardar,
    ):
        output = await invocar_agente(spec, {}, tenant="criza")

    mock_ap.assert_not_awaited()
    mock_guardar.assert_not_awaited()
    assert output["análisis"]["informe_completo"] == "x"
