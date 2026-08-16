"""
Tests — Motor Orquestador v2

Markers:
  unit        → sin red, sin DB (mocks)
  integration → requiere DB

Correr:
  pytest criza/orquestador/tests/test_motor.py -m unit -v
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_CRIZA = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_CRIZA))

from orquestador.motor import (
    EstimacionCosto,
    InspeccionResult,
    MotorResult,
    _advance,
    _build_context,
    _extract_expediente,
    _get_nested,
    _next_step_id,
    _resolve,
    _steps_index,
    ejecutar,
    estimar_costo,
    inspeccionar_caso,
    reanudar_desde,
)
from orquestador.registry import AgentSpec


# ── Fixtures ──────────────────────────────────────────────────────────────────

FLOW_SIMPLE = {
    "name": "pipeline_test",
    "version": "1.0",
    "objective_template": "Objetivo: {entry.descripcion}",
    "steps": [
        {
            "id": "crear_oportunidad",
            "type": "km_write",
            "action": "crear_oportunidad",
            "props_from_entry": {"nombre": "descripcion", "descripcion": "descripcion"},
        },
        {
            "id": "market",
            "type": "agent",
            "agent": "mercado",
            "contract_input": {
                "caso": "{entry.descripcion}",
                "conocimiento": {"oportunidad_id": "{state.oportunidad_id}"},
            },
            "on_error": "stop",
        },
        {
            "id": "armador",
            "type": "agent",
            "agent": "armador",
            "contract_input": {
                "conocimiento": {"oportunidad_id": "{state.oportunidad_id}"},
            },
            "on_error": "stop",
        },
    ],
}

FLOW_CON_ROUTING = {
    "name": "pipeline_routing_test",
    "version": "1.0",
    "steps": [
        {
            "id": "evidence",
            "type": "agent",
            "agent": "evidencia",
            "contract_input": {"conocimiento": {"oportunidad_id": "{state.oportunidad_id}"}},
            "routing": {
                "field": "próximo_agente",
                "routes": {
                    "cientifico_especialista": "especialista",
                    "_default": "armador",
                },
            },
        },
        {"id": "especialista", "type": "agent", "agent": "cientifico_especialista", "next": "armador", "contract_input": {}},
        {"id": "armador", "type": "agent", "agent": "armador", "contract_input": {}},
    ],
}

FLOW_CON_GATE = {
    "name": "pipeline_gate_test",
    "version": "1.0",
    "steps": [
        {
            "id": "investigacion_amplia",
            "type": "agent",
            "agent": "investigacion_amplia",
            "contract_input": {"caso": "{entry.sector}"},
            "gate_humano": {
                "mensaje": "¿Cuál candidato?",
                "espera_campo": "candidato_elegido",
            },
            "on_error": "stop",
        },
        {"id": "market", "type": "agent", "agent": "mercado", "contract_input": {}},
    ],
}

MARKET_OUTPUT = {
    "análisis": {"resumen": "Mercado analizado", "cruces": {}},
    "nivel_confianza": "alto",
    "recomendaciones": [],
    "próximo_agente": None,
    "nuevo_conocimiento": [],
}

ARMADOR_OUTPUT = {
    "análisis": {"expediente": "# Expediente\n\nContenido completo..."},
    "nivel_confianza": "alto",
    "recomendaciones": [],
    "próximo_agente": None,
    "nuevo_conocimiento": [],
}

EVIDENCE_OUTPUT_CON_ESPECIALISTA = {
    "análisis": {"informe": "Evidencia analizada"},
    "nivel_confianza": "medio",
    "recomendaciones": ["brecha A"],
    "próximo_agente": "cientifico_especialista",
    "nuevo_conocimiento": [],
}

EVIDENCE_OUTPUT_SIN_ESPECIALISTA = {
    **EVIDENCE_OUTPUT_CON_ESPECIALISTA,
    "próximo_agente": None,
}

IA_OUTPUT = {
    "análisis": {"informe": "IA completada"},
    "nivel_confianza": "medio",
    "recomendaciones": [{"candidato": "Olor estiércol", "prioridad": "alta"}],
    "próximo_agente": "mercado",
    "nuevo_conocimiento": [],
}

ENTRY_DOLOR = {"descripcion": "Olor de estiércol porcino", "mercado_objetivo": "porcicultura"}
ENTRY_SECTOR = {"sector": "porcicultura"}


def _spec(nombre: str, run_fn) -> AgentSpec:
    return AgentSpec(
        nombre=nombre, modulo="", descripcion="", prop_key=nombre,
        activo=run_fn is not None, run_fn=run_fn,
    )


def make_registry(**overrides):
    base = {
        "mercado": _spec("mercado", AsyncMock(return_value=MARKET_OUTPUT)),
        "evidencia": _spec("evidencia", AsyncMock(return_value=EVIDENCE_OUTPUT_SIN_ESPECIALISTA)),
        "investigacion_amplia": _spec("investigacion_amplia", AsyncMock(return_value=IA_OUTPUT)),
        "armador": _spec("armador", AsyncMock(return_value=ARMADOR_OUTPUT)),
        "cientifico_especialista": _spec("cientifico_especialista", None),
    }
    for nombre, valor in overrides.items():
        base[nombre] = valor if isinstance(valor, AgentSpec) else _spec(nombre, valor)
    return base


# ── _get_nested ───────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_get_nested_acceso_simple():
    assert _get_nested({"a": {"b": "valor"}}, ["a", "b"]) == "valor"


@pytest.mark.unit
def test_get_nested_clave_ausente():
    assert _get_nested({"a": 1}, ["b"]) == ""


@pytest.mark.unit
def test_get_nested_no_dict():
    assert _get_nested("string", ["x"]) == ""


# ── _resolve ──────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_resolve_string_simple():
    ctx = {"entry.descripcion": "dolor X"}
    assert _resolve("{entry.descripcion}", ctx) == "dolor X"


@pytest.mark.unit
def test_resolve_dict_recursivo():
    ctx = {"entry.descripcion": "dolor X", "state.oportunidad_id": "uuid-1"}
    result = _resolve({"caso": "{entry.descripcion}", "conocimiento": {"oportunidad_id": "{state.oportunidad_id}"}}, ctx)
    assert result == {"caso": "dolor X", "conocimiento": {"oportunidad_id": "uuid-1"}}


@pytest.mark.unit
def test_resolve_template_sin_match_queda_igual():
    ctx = {}
    assert _resolve("{entry.descripcion}", ctx) == "{entry.descripcion}"


@pytest.mark.unit
def test_resolve_non_string_pasa_igual():
    assert _resolve(42, {}) == 42
    assert _resolve(None, {}) is None


# ── _build_context ─────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_build_context_entry():
    ctx = _build_context({"descripcion": "test"}, {}, {}, {})
    assert ctx["entry.descripcion"] == "test"


@pytest.mark.unit
def test_build_context_state():
    ctx = _build_context({}, {"oportunidad_id": "uuid-1"}, {}, {})
    assert ctx["state.oportunidad_id"] == "uuid-1"


@pytest.mark.unit
def test_build_context_steps_output():
    ctx = _build_context({}, {}, {"market": {"nivel_confianza": "alto"}}, {})
    assert ctx["steps.market.output.nivel_confianza"] == "alto"


# ── _steps_index ─────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_steps_index_retorna_dict_keyed_por_id():
    idx = _steps_index(FLOW_SIMPLE)
    assert "crear_oportunidad" in idx
    assert "market" in idx
    assert "armador" in idx


# ── _next_step_id ─────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_next_step_routing_a_especialista():
    step = FLOW_CON_ROUTING["steps"][0]
    idx = _steps_index(FLOW_CON_ROUTING)
    output = {"próximo_agente": "cientifico_especialista"}
    assert _next_step_id(step, output, idx) == "especialista"


@pytest.mark.unit
def test_next_step_routing_default():
    step = FLOW_CON_ROUTING["steps"][0]
    idx = _steps_index(FLOW_CON_ROUTING)
    output = {"próximo_agente": None}
    assert _next_step_id(step, output, idx) == "armador"


@pytest.mark.unit
def test_next_step_explicito():
    step = FLOW_CON_ROUTING["steps"][1]  # especialista tiene next="armador"
    idx = _steps_index(FLOW_CON_ROUTING)
    assert _next_step_id(step, {}, idx) == "armador"


@pytest.mark.unit
def test_next_step_avance_secuencial():
    step = FLOW_SIMPLE["steps"][0]  # crear_oportunidad → market
    idx = _steps_index(FLOW_SIMPLE)
    assert _next_step_id(step, {}, idx) == "market"


# ── _advance ─────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_advance_a_siguiente():
    assert _advance(["a", "b", "c"], "a") == "b"


@pytest.mark.unit
def test_advance_desde_ultimo():
    assert _advance(["a", "b"], "b") is None


# ── _extract_expediente ────────────────────────────────────────────────────────

@pytest.mark.unit
def test_extract_expediente_desde_armador():
    steps_output = {"armador": ARMADOR_OUTPUT}
    exp = _extract_expediente(steps_output)
    assert "Expediente" in exp


@pytest.mark.unit
def test_extract_expediente_sin_armador():
    assert _extract_expediente({}) is None


# ── ejecutar — flow completo ──────────────────────────────────────────────────

@pytest.mark.unit
def test_ejecutar_flow_completo():
    registry = make_registry()

    with (
        patch("orquestador.motor.motor_api.guardar_ficha", new_callable=AsyncMock) as mock_guardar_ficha,
        patch("orquestador.motor.motor_api.actualizar_props", new_callable=AsyncMock),
    ):
        mock_guardar_ficha.return_value = {"id": "uuid-test-1"}

        result = asyncio.run(
            ejecutar(
                flow=FLOW_SIMPLE,
                entry=ENTRY_DOLOR,
                tenant="criza",
                registry=registry,
            )
        )

    assert result.status == "completo"
    assert result.oportunidad_id == "uuid-test-1"
    assert result.expediente_markdown is not None
    assert "Expediente" in result.expediente_markdown


@pytest.mark.unit
def test_ejecutar_llama_agentes_en_orden():
    registry = make_registry()
    calls = []

    async def track_market(contract_input, verbose=False):
        calls.append("market")
        return MARKET_OUTPUT

    async def track_armador(contract_input, verbose=False):
        calls.append("armador")
        return ARMADOR_OUTPUT

    registry["mercado"] = _spec("mercado", track_market)
    registry["armador"] = _spec("armador", track_armador)

    with (
        patch("orquestador.motor.motor_api.guardar_ficha", new_callable=AsyncMock, return_value={"id": "uuid-2"}),
        patch("orquestador.motor.motor_api.actualizar_props", new_callable=AsyncMock),
    ):
        asyncio.run(
            ejecutar(flow=FLOW_SIMPLE, entry=ENTRY_DOLOR, tenant="criza", registry=registry)
        )

    assert calls == ["market", "armador"]


@pytest.mark.unit
def test_ejecutar_pasa_oportunidad_id_a_agentes():
    captured = {}

    async def mock_market(contract_input, verbose=False):
        captured["oportunidad_id"] = contract_input.get("conocimiento", {}).get("oportunidad_id")
        return MARKET_OUTPUT

    registry = make_registry(mercado=mock_market)

    with (
        patch("orquestador.motor.motor_api.guardar_ficha", new_callable=AsyncMock, return_value={"id": "uuid-xyz"}),
        patch("orquestador.motor.motor_api.actualizar_props", new_callable=AsyncMock),
    ):
        asyncio.run(
            ejecutar(flow=FLOW_SIMPLE, entry=ENTRY_DOLOR, tenant="criza", registry=registry)
        )

    assert captured["oportunidad_id"] == "uuid-xyz"


@pytest.mark.unit
def test_ejecutar_on_error_stop():
    async def market_falla(contract_input, verbose=False):
        raise RuntimeError("API caída")

    registry = make_registry(mercado=market_falla)

    with (
        patch("orquestador.motor.motor_api.guardar_ficha", new_callable=AsyncMock, return_value={"id": "uuid-3"}),
        patch("orquestador.motor.motor_api.actualizar_props", new_callable=AsyncMock),
    ):
        result = asyncio.run(
            ejecutar(flow=FLOW_SIMPLE, entry=ENTRY_DOLOR, tenant="criza", registry=registry)
        )

    assert result.status == "stop"
    assert "market" in result.error


@pytest.mark.unit
def test_ejecutar_on_error_continue():
    flow_con_continue = {
        **FLOW_SIMPLE,
        "steps": [
            FLOW_SIMPLE["steps"][0],  # crear_oportunidad
            {**FLOW_SIMPLE["steps"][1], "on_error": "continue"},  # market → continue
            FLOW_SIMPLE["steps"][2],  # armador
        ],
    }

    async def market_falla(contract_input, verbose=False):
        raise RuntimeError("API caída")

    registry = make_registry(mercado=market_falla)

    with (
        patch("orquestador.motor.motor_api.guardar_ficha", new_callable=AsyncMock, return_value={"id": "uuid-4"}),
        patch("orquestador.motor.motor_api.actualizar_props", new_callable=AsyncMock),
    ):
        result = asyncio.run(
            ejecutar(flow=flow_con_continue, entry=ENTRY_DOLOR, tenant="criza", registry=registry)
        )

    # El pipeline termina completo aunque market haya fallado
    assert result.status == "completo"
    assert result.pipeline_status["market"]["status"] == "error"


@pytest.mark.unit
def test_ejecutar_skip_agente_none():
    """Un agente con valor None en el registry (stub) se saltea sin romper el pipeline."""
    flow_con_especialista = {
        "name": "test",
        "version": "1.0",
        "steps": [
            {"id": "crear_oportunidad", "type": "km_write", "action": "crear_oportunidad", "props_from_entry": {}},
            {"id": "especialista", "type": "agent", "agent": "cientifico_especialista",
             "contract_input": {}, "next": "armador", "on_error": "continue"},
            {"id": "armador", "type": "agent", "agent": "armador", "contract_input": {}},
        ],
    }
    registry = make_registry()  # cientifico_especialista = None

    with (
        patch("orquestador.motor.motor_api.guardar_ficha", new_callable=AsyncMock, return_value={"id": "uuid-5"}),
        patch("orquestador.motor.motor_api.actualizar_props", new_callable=AsyncMock),
    ):
        result = asyncio.run(
            ejecutar(flow=flow_con_especialista, entry=ENTRY_DOLOR, tenant="criza", registry=registry)
        )

    assert result.status == "completo"
    assert result.pipeline_status["especialista"]["status"] == "skipped"


@pytest.mark.unit
def test_ejecutar_routing_con_especialista():
    """Si evidencia retorna próximo_agente='cientifico_especialista', el router va al especialista."""
    flow = {
        "name": "test_routing",
        "version": "1.0",
        "steps": [
            {"id": "crear_oportunidad", "type": "km_write", "action": "crear_oportunidad", "props_from_entry": {}},
            {
                "id": "evidence",
                "type": "agent",
                "agent": "evidencia",
                "contract_input": {"conocimiento": {"oportunidad_id": "{state.oportunidad_id}"}},
                "routing": {"field": "próximo_agente", "routes": {"cientifico_especialista": "especialista", "_default": "armador"}},
            },
            {"id": "especialista", "type": "agent", "agent": "cientifico_especialista", "next": "armador", "contract_input": {}, "on_error": "continue"},
            {"id": "armador", "type": "agent", "agent": "armador", "contract_input": {}},
        ],
    }
    orden = []

    async def track_evidence(contract_input, verbose=False):
        orden.append("evidence")
        return EVIDENCE_OUTPUT_CON_ESPECIALISTA  # próximo=cientifico_especialista

    registry = make_registry(evidencia=track_evidence)

    with (
        patch("orquestador.motor.motor_api.guardar_ficha", new_callable=AsyncMock, return_value={"id": "uuid-6"}),
        patch("orquestador.motor.motor_api.actualizar_props", new_callable=AsyncMock),
    ):
        asyncio.run(
            ejecutar(flow=flow, entry=ENTRY_DOLOR, tenant="criza", registry=registry)
        )

    assert "evidence" in orden
    # especialista es None → skipped pero el armador sigue
    assert registry["armador"].run_fn.called


@pytest.mark.unit
def test_ejecutar_gate_humano_pausa():
    """El pipeline pausa en gate_humano y retorna MotorResult(status='gate_humano')."""
    registry = make_registry()

    with (
        patch("orquestador.motor.motor_api.guardar_ficha", new_callable=AsyncMock, return_value={"id": "uuid-gate"}),
        patch("orquestador.motor.motor_api.actualizar_props", new_callable=AsyncMock),
    ):
        result = asyncio.run(
            ejecutar(flow=FLOW_CON_GATE, entry=ENTRY_SECTOR, tenant="criza", registry=registry)
        )

    assert result.status == "gate_humano"
    assert result.gate_data is not None
    assert result.gate_data["step_id"] == "investigacion_amplia"
    assert result.gate_data["espera_campo"] == "candidato_elegido"
    # market NO debe haber corrido aún
    assert not registry["mercado"].run_fn.called


@pytest.mark.unit
def test_motor_result_estructura():
    """MotorResult tiene los campos esperados."""
    r = MotorResult(status="completo", oportunidad_id="uuid-x")
    assert r.status == "completo"
    assert r.oportunidad_id == "uuid-x"
    assert r.pipeline_status == {}
    assert r.gate_data is None
    assert r.expediente_markdown is None
    assert r.error is None


# ── inspeccionar_caso — Etapa 2 (2026-08-16) ────────────────────────────────────

@pytest.mark.unit
def test_inspeccionar_caso_prop_presente_es_completo():
    registry = make_registry()
    oportunidad = {"id": "uuid-1", "props": {"mercado": {"resumen": "ok"}}}

    with patch("orquestador.motor.motor_api.obtener", new=AsyncMock(return_value=oportunidad)):
        result = asyncio.run(inspeccionar_caso(FLOW_SIMPLE, "uuid-1", "criza", registry))

    assert "market" in result.completos
    assert "market" not in result.pendientes


@pytest.mark.unit
def test_inspeccionar_caso_prop_ausente_es_pendiente():
    registry = make_registry()
    oportunidad = {"id": "uuid-1", "props": {}}

    with patch("orquestador.motor.motor_api.obtener", new=AsyncMock(return_value=oportunidad)):
        result = asyncio.run(inspeccionar_caso(FLOW_SIMPLE, "uuid-1", "criza", registry))

    assert result.pendientes == ["market", "armador"]
    assert result.completos == []


@pytest.mark.unit
def test_inspeccionar_caso_agente_no_registrado_es_no_disponible():
    registry = {"armador": make_registry()["armador"]}  # falta "mercado" en el registry
    oportunidad = {"id": "uuid-1", "props": {}}

    with patch("orquestador.motor.motor_api.obtener", new=AsyncMock(return_value=oportunidad)):
        result = asyncio.run(inspeccionar_caso(FLOW_SIMPLE, "uuid-1", "criza", registry))

    assert "market" in result.no_disponibles


@pytest.mark.unit
def test_inspeccionar_caso_agente_inactivo_es_no_disponible():
    registry = make_registry(mercado=_spec("mercado", None))  # run_fn=None
    oportunidad = {"id": "uuid-1", "props": {}}

    with patch("orquestador.motor.motor_api.obtener", new=AsyncMock(return_value=oportunidad)):
        result = asyncio.run(inspeccionar_caso(FLOW_SIMPLE, "uuid-1", "criza", registry))

    assert "market" in result.no_disponibles


@pytest.mark.unit
def test_inspeccionar_caso_ignora_steps_no_agent():
    """FLOW_SIMPLE tiene un step type=km_write ('crear_oportunidad') — no debe aparecer."""
    registry = make_registry()
    oportunidad = {"id": "uuid-1", "props": {}}

    with patch("orquestador.motor.motor_api.obtener", new=AsyncMock(return_value=oportunidad)):
        result = asyncio.run(inspeccionar_caso(FLOW_SIMPLE, "uuid-1", "criza", registry))

    step_ids = {p.step_id for p in result.pasos}
    assert "crear_oportunidad" not in step_ids


@pytest.mark.unit
def test_inspeccionar_caso_oportunidad_inexistente():
    registry = make_registry()
    with patch("orquestador.motor.motor_api.obtener", new=AsyncMock(return_value=None)):
        with pytest.raises(ValueError, match="no encontrada"):
            asyncio.run(inspeccionar_caso(FLOW_SIMPLE, "no-existe", "criza", registry))


# ── estimar_costo — Etapa 2 (2026-08-16) ─────────────────────────────────────────

@pytest.mark.unit
def test_estimar_costo_con_historico_promedia():
    registry = make_registry()
    oportunidad = {"id": "uuid-1", "props": {}}
    historicas = [
        {"props": {"token_usage": {"mercado": {"total_tokens": 1000}}}},
        {"props": {"token_usage": {"mercado": {"total_tokens": 2000}}}},
        {"props": {"token_usage": {"armador": {"total_tokens": 500}}}},
    ]

    with (
        patch("orquestador.motor.motor_api.obtener", new=AsyncMock(return_value=oportunidad)),
        patch("orquestador.motor.motor_api.listar", new=AsyncMock(return_value=historicas)),
    ):
        result = asyncio.run(estimar_costo(FLOW_SIMPLE, "uuid-1", "criza", registry))

    paso_market = next(p for p in result.pasos if p.step_id == "market")
    assert paso_market.tokens_estimados == 1500
    assert paso_market.basado_en == 2

    paso_armador = next(p for p in result.pasos if p.step_id == "armador")
    assert paso_armador.tokens_estimados == 500
    assert paso_armador.basado_en == 1

    assert result.total_estimado == 2000


@pytest.mark.unit
def test_estimar_costo_sin_historico_es_none():
    registry = make_registry()
    oportunidad = {"id": "uuid-1", "props": {}}

    with (
        patch("orquestador.motor.motor_api.obtener", new=AsyncMock(return_value=oportunidad)),
        patch("orquestador.motor.motor_api.listar", new=AsyncMock(return_value=[])),
    ):
        result = asyncio.run(estimar_costo(FLOW_SIMPLE, "uuid-1", "criza", registry))

    paso_market = next(p for p in result.pasos if p.step_id == "market")
    assert paso_market.tokens_estimados is None
    assert result.total_estimado is None  # no aparenta certeza que no hay


@pytest.mark.unit
def test_estimar_costo_sin_pendientes_total_cero():
    registry = make_registry()
    oportunidad = {"id": "uuid-1", "props": {"mercado": {"x": 1}, "armador": {"x": 1}}}

    with (
        patch("orquestador.motor.motor_api.obtener", new=AsyncMock(return_value=oportunidad)),
        patch("orquestador.motor.motor_api.listar", new=AsyncMock(return_value=[])),
    ):
        result = asyncio.run(estimar_costo(FLOW_SIMPLE, "uuid-1", "criza", registry))

    assert result.pasos == []
    assert result.total_estimado == 0


# ── reanudar_desde — Etapa 2 (2026-08-16) ────────────────────────────────────────

@pytest.mark.unit
def test_reanudar_desde_no_re_corre_pasos_completos():
    """El step 'market' ya está completo en el KM — reanudar_desde('armador') no debe
    volver a invocar mercado."""
    registry = make_registry()
    oportunidad = {
        "id": "uuid-1",
        "props": {
            "mercado": {"resumen": "ya corrido", "informe_completo": "..."},
            "pipeline_status": {
                "flow": "pipeline_test", "objetivo": "obj", "started_at": "2026-08-16T00:00:00Z",
                "steps": {
                    "crear_oportunidad": {"status": "completo"},
                    "market": {"status": "completo", "nivel_confianza": "alto", "próximo_agente": None},
                },
            },
        },
    }

    with (
        patch("orquestador.motor.motor_api.obtener", new=AsyncMock(return_value=oportunidad)),
        patch("orquestador.motor.motor_api.actualizar_props", new=AsyncMock()),
    ):
        result = asyncio.run(reanudar_desde(FLOW_SIMPLE, "uuid-1", "armador", "criza", registry))

    assert not registry["mercado"].run_fn.called
    assert registry["armador"].run_fn.called
    assert result.status == "completo"


@pytest.mark.unit
def test_reanudar_desde_step_inexistente():
    registry = make_registry()
    oportunidad = {"id": "uuid-1", "props": {}}

    with patch("orquestador.motor.motor_api.obtener", new=AsyncMock(return_value=oportunidad)):
        with pytest.raises(ValueError, match="no existe en el flow"):
            asyncio.run(reanudar_desde(FLOW_SIMPLE, "uuid-1", "step_fantasma", "criza", registry))


@pytest.mark.unit
def test_reanudar_desde_oportunidad_inexistente():
    registry = make_registry()
    with patch("orquestador.motor.motor_api.obtener", new=AsyncMock(return_value=None)):
        with pytest.raises(ValueError, match="no encontrada"):
            asyncio.run(reanudar_desde(FLOW_SIMPLE, "no-existe", "armador", "criza", registry))


@pytest.mark.integration
def test_reanudar_desde_caso_real_no_repaga_pasos_completos():
    """
    Corrida real contra el KM (sin mock de motor_api) — verifica el requisito explícito del
    plan (Etapa 2): reanudar un flow parcial sin re-pagar los pasos ya corridos. Los run_fn de
    los agentes son stubs livianos a propósito — lo que se verifica acá es la mecánica del
    Motor (reconstrucción de estado + persistencia real al KM), no la calidad de síntesis de
    cada agente (eso ya está cubierto en las suites propias de cada uno).
    """
    from knowledge_module.db import reset_engine
    from knowledge_module.motor import api as motor_api

    reset_engine()

    async def _run():
        creada = await motor_api.guardar_ficha(
            area="descubrimiento", tipo="oportunidad", tenant="criza",
            campos={
                "nombre": "TEST reanudar_desde — borrar",
                "descripcion": "Prueba de integración de reanudar_desde (Etapa 2)",
            },
        )
        oportunidad_id = creada["id"]

        # Simula que 'market' ya corrió en una sesión anterior — persistencia real al KM.
        await motor_api.actualizar_props(
            oportunidad_id,
            {
                "mercado": {"resumen": "Mercado ya evaluado (fixture de test)", "informe_completo": "..."},
                "pipeline_status": {
                    "flow": "pipeline_test", "objetivo": "obj de prueba",
                    "started_at": "2026-08-16T00:00:00Z",
                    "steps": {
                        "crear_oportunidad": {"status": "completo"},
                        "market": {"status": "completo", "nivel_confianza": "alto", "próximo_agente": None},
                    },
                },
            },
            tenant="criza",
        )

        market_calls = []
        armador_calls = []

        async def market_stub(contract_input, verbose=False):
            market_calls.append(contract_input)
            return MARKET_OUTPUT

        async def armador_stub(contract_input, verbose=False):
            armador_calls.append(contract_input)
            return ARMADOR_OUTPUT

        registry = {
            "mercado": _spec("mercado", market_stub),
            "armador": _spec("armador", armador_stub),
        }

        # verbose=False: motor.py imprime '→' (U+2192), que la consola cp1252 de Windows no
        # puede encodear bajo pytest's capture — no es un bug de reanudar_desde, es un
        # problema de codepage de la terminal, ver test_run_agent_caso_real para el mismo caso.
        result = await reanudar_desde(FLOW_SIMPLE, oportunidad_id, "armador", "criza", registry, verbose=False)

        assert market_calls == [], "reanudar_desde volvió a invocar 'market' — no debería, ya estaba completo"
        assert len(armador_calls) == 1
        assert result.status == "completo"

        # Verificación leyendo el KM (DoD del proyecto: no confiar solo en el valor de retorno).
        oportunidad_final = await motor_api.obtener(oportunidad_id, tenant="criza")
        props_final = oportunidad_final.get("props") or {}
        assert props_final.get("armador") is not None, "props.armador no quedó persistido en el KM"
        assert props_final["pipeline_status"]["steps"]["armador"]["status"] == "completo"

    asyncio.run(_run())
