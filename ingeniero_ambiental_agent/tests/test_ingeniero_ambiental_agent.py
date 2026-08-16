"""
Tests del Especialista Ingeniero Ambiental — CRIZA.

Unit: estructura de tools, SYSTEM_PROMPT (checklist anti-sesgo), build_input_desde_frente,
run_agent_desde_frente mock, run() solo acepta frente_id.
Integration: corrida real contra Anthropic + corpus INTA/CONICET + KM (staging).

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

import ingeniero_ambiental_agent as ia
from knowledge_module.preflight import PreflightResult

_PREFLIGHT_OK = PreflightResult(
    ok=True, bloqueantes=[], advertencias=[],
    fuentes_ok=["INTA corpus", "OpenAlex"], fuentes_no_disponibles=[],
)

CASO_TEST = {
    "id": "caso-uuid-1",
    "tipo": "caso",
    "props": {"nombre": "Efluentes biogás (Helios)", "descripcion": "Biodigestor con efluente de alta carga orgánica."},
}
FRENTE_TEST = {
    "id": "frente-uuid-1",
    "tipo": "frente",
    "props": {"nombre": "Frente técnico", "descripcion": "Definir enfoque de valorización del efluente.", "estado": "activo"},
}
PENDIENTES_TEST = [
    {"id": "pend-1", "props": {"descripcion": "Confirmar quién paga el flete.", "estado": "abierto"}},
]

EVALUACION_MOCK = {
    "evaluacion_tecnica": {
        "resumen": {
            "valor": "El balance energético de la ruta de concentración es desfavorable a la escala actual.",
            "estado": "establecido",
            "fuente": "doi:10.1234/test",
        },
        "microorganismos_o_procesos_relevantes": [
            {"nombre": "Evaporación al vacío", "rol": "Concentración de digestato", "estado": "establecido", "fuente": "doi:10.1234/test"},
        ],
        "enfoques_tecnicos_identificados": [
            {"enfoque": "Concentración por evaporación al vacío", "madurez": "maduro", "fuente": "doi:10.1234/test"},
        ],
        "riesgos_o_limitaciones": [
            {"riesgo": "Alto consumo energético a la escala actual de planta", "estado": "asumido"},
        ],
        "brechas_de_conocimiento": [
            {"brecha": "Falta el balance de masa real de la planta (caudal medido, no estimado)", "impacto_en_decision": "alto", "donde_confirmar": "Medición en planta"},
        ],
    },
    "especialista_adicional_recomendado": {
        "si_no": False,
        "descripcion": "",
        "razon": "",
    },
    "informe_completo": (
        "## Evaluación de Ingeniería — Concentración de Digestato\n\n"
        "### Pregunta de ingeniería central\n\n"
        "¿Qué tecnología de concentración es viable a la escala de la planta?\n\n"
        "### Búsquedas realizadas\n\n"
        "1. 'digestate concentration evaporation energy balance'\n\n"
        "### Hallazgos\n\nLa evaporación al vacío es una tecnología madura, pero el consumo energético..."
    ),
    "lecciones_caso": [
        "Buscar 'concentration technologies' en vez de 'treatment' devuelve resultados más específicos de ingeniería"
    ],
}


# ── Unit: estructura de tools ─────────────────────────────────────────────────

@pytest.mark.unit
def test_tools_count():
    assert len(ia.TOOLS) == 5, f"Esperado 5 tools, tiene {len(ia.TOOLS)}"


@pytest.mark.unit
def test_tools_names():
    nombres = {t["name"] for t in ia.TOOLS}
    assert nombres == {
        "search_literature", "buscar_corpus_cientifico", "search_corpus_inta",
        "expand_agrovoc", "submit_evaluacion_tecnica",
    }


@pytest.mark.unit
def test_submit_evaluacion_tecnica_required_fields():
    submit = next(t for t in ia.TOOLS if t["name"] == "submit_evaluacion_tecnica")
    required = submit["input_schema"].get("required", [])
    for field in ("evaluacion_tecnica", "especialista_adicional_recomendado", "informe_completo", "fuentes_y_cobertura"):
        assert field in required


# ── Unit: SYSTEM_PROMPT — checklist anti-sesgo ─────────────────────────────────

@pytest.mark.unit
def test_system_prompt_sin_menciones_de_caso():
    """Mismo control que microbiologo_agent — cero menciones de Helios/biogás/biodigestor."""
    sp_lower = ia.SYSTEM_PROMPT.lower()
    prohibidas = ["helios", "biogás", "biogas", "biodigestor", "mateo", "andrés", "buenas maltas"]
    for termino in prohibidas:
        assert termino not in sp_lower, f"SYSTEM_PROMPT menciona '{termino}' — viola el checklist anti-sesgo"


@pytest.mark.unit
def test_system_prompt_no_nombra_tipo_de_especialista():
    sp_lower = ia.SYSTEM_PROMPT.lower()
    assert "sin nombrar" in sp_lower


@pytest.mark.unit
def test_system_prompt_menciona_submit_evaluacion_tecnica():
    assert "submit_evaluacion_tecnica" in ia.SYSTEM_PROMPT


@pytest.mark.unit
def test_system_prompt_veracidad_por_dato():
    sp = ia.SYSTEM_PROMPT
    assert "establecido" in sp and "asumido" in sp and "a-confirmar" in sp


@pytest.mark.unit
def test_system_prompt_distingue_ingenieria_de_biologia():
    """El prompt debe dejar claro que evalúa ingeniería, no biología/química — el ángulo
    distinto del Microbiólogo."""
    sp_lower = ia.SYSTEM_PROMPT.lower()
    assert "ingeniería" in sp_lower
    assert "balance" in sp_lower


# ── Unit: build_input_desde_frente ──────────────────────────────────────────────

@pytest.mark.unit
def test_build_input_desde_frente_incluye_caso_y_frente():
    result = ia.build_input_desde_frente(FRENTE_TEST, CASO_TEST, [])
    assert "Efluentes biogás (Helios)" in result
    assert "Frente técnico" in result
    assert "submit_evaluacion_tecnica" in result


@pytest.mark.unit
def test_build_input_desde_frente_incluye_pendientes():
    result = ia.build_input_desde_frente(FRENTE_TEST, CASO_TEST, PENDIENTES_TEST)
    assert "Confirmar quién paga el flete" in result


# ── Unit: run_agent_desde_frente (mock) ─────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_agent_desde_frente_captura_submit_y_escribe_token_usage_en_frente():
    mock_tool_use = type("ToolUseBlock", (), {
        "type": "tool_use", "name": "submit_evaluacion_tecnica", "id": "tool_ev_01", "input": EVALUACION_MOCK,
    })()
    mock_usage = type("Usage", (), {"input_tokens": 800, "output_tokens": 400})()
    mock_response = type("Response", (), {
        "stop_reason": "tool_use", "content": [mock_tool_use], "usage": mock_usage,
    })()

    mock_actualizar = AsyncMock(return_value={"success": True})
    with patch("ingeniero_ambiental_agent._ai_complete", new=AsyncMock(return_value=mock_response)), \
         patch("ingeniero_ambiental_agent.obtener_frente_con_caso", new=AsyncMock(return_value={"frente": FRENTE_TEST, "caso": CASO_TEST})), \
         patch("ingeniero_ambiental_agent.obtener_pendientes_de_caso", new=AsyncMock(return_value=PENDIENTES_TEST)), \
         patch("ingeniero_ambiental_agent.motor_api.actualizar_props", new=mock_actualizar), \
         patch("ingeniero_ambiental_agent.aprendizaje.ensure_area", new=AsyncMock()), \
         patch("ingeniero_ambiental_agent.run_preflight", new=AsyncMock(return_value=_PREFLIGHT_OK)), \
         patch("ingeniero_ambiental_agent.aprendizaje.bloque_lecciones_para_prompt", new=AsyncMock(return_value="")):

        informe, evaluacion, lecciones = await ia.run_agent_desde_frente("frente-uuid-1", verbose=False)

    assert "Evaluación de Ingeniería" in informe
    assert evaluacion["evaluacion_tecnica"]["resumen"]["estado"] == "establecido"
    mock_actualizar.assert_awaited_once()
    args, kwargs = mock_actualizar.call_args
    assert args[0] == "frente-uuid-1"
    assert "token_usage" in args[1]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_agent_desde_frente_sin_frente_levanta_valueerror():
    with patch("ingeniero_ambiental_agent.obtener_frente_con_caso", new=AsyncMock(return_value={"frente": None, "caso": None})):
        with pytest.raises(ValueError, match="no encontrado"):
            await ia.run_agent_desde_frente("no-existe")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_agent_desde_frente_sin_caso_asociado_levanta_valueerror():
    with patch("ingeniero_ambiental_agent.obtener_frente_con_caso", new=AsyncMock(return_value={"frente": FRENTE_TEST, "caso": None})):
        with pytest.raises(ValueError, match="no tiene un caso asociado"):
            await ia.run_agent_desde_frente("frente-uuid-1")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_agent_desde_frente_despacha_buscar_corpus_cientifico():
    corpus_call = type("ToolUseBlock", (), {
        "type": "tool_use", "name": "buscar_corpus_cientifico", "id": "tool_corpus_01", "input": {"consulta": "concentración digestato"},
    })()
    mock_submit = type("ToolUseBlock", (), {
        "type": "tool_use", "name": "submit_evaluacion_tecnica", "id": "tool_ev_02", "input": EVALUACION_MOCK,
    })()
    mock_usage = type("Usage", (), {"input_tokens": 100, "output_tokens": 50})()
    mock_r1 = type("Response", (), {"stop_reason": "tool_use", "content": [corpus_call], "usage": mock_usage})()
    mock_r2 = type("Response", (), {"stop_reason": "tool_use", "content": [mock_submit], "usage": mock_usage})()
    corpus_result = {"resultados": []}

    with patch("ingeniero_ambiental_agent._ai_complete", new=AsyncMock(side_effect=[mock_r1, mock_r2])), \
         patch("ingeniero_ambiental_agent.obtener_frente_con_caso", new=AsyncMock(return_value={"frente": FRENTE_TEST, "caso": CASO_TEST})), \
         patch("ingeniero_ambiental_agent.obtener_pendientes_de_caso", new=AsyncMock(return_value=[])), \
         patch("ingeniero_ambiental_agent.motor_api.actualizar_props", new=AsyncMock()), \
         patch("ingeniero_ambiental_agent.aprendizaje.ensure_area", new=AsyncMock()), \
         patch("ingeniero_ambiental_agent.run_preflight", new=AsyncMock(return_value=_PREFLIGHT_OK)), \
         patch("ingeniero_ambiental_agent.aprendizaje.bloque_lecciones_para_prompt", new=AsyncMock(return_value="")), \
         patch("ingeniero_ambiental_agent._buscar_corpus_cientifico_fn", new=AsyncMock(return_value=corpus_result)) as mock_corpus:

        await ia.run_agent_desde_frente("frente-uuid-1", verbose=False)

    mock_corpus.assert_awaited_once_with(consulta="concentración digestato", limit=100)


# ── Unit: _derive_confidence ──────────────────────────────────────────────────

@pytest.mark.unit
def test_derive_confidence_alto_con_enfoque_maduro_sin_brechas():
    evaluacion = {
        "evaluacion_tecnica": {
            "enfoques_tecnicos_identificados": [{"madurez": "maduro"}],
            "brechas_de_conocimiento": [],
        }
    }
    assert ia._derive_confidence(evaluacion) == "alto"


@pytest.mark.unit
def test_derive_confidence_bajo_sin_enfoques():
    evaluacion = {"evaluacion_tecnica": {"enfoques_tecnicos_identificados": [], "brechas_de_conocimiento": []}}
    assert ia._derive_confidence(evaluacion) == "bajo"


# ── Unit: run() — contrato SEB-115, solo frente_id ──────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_contract_requiere_frente_id():
    with pytest.raises(ValueError, match="frente_id"):
        await ia.run(contract_input={"conocimiento": {}}, verbose=False)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_contract_no_acepta_oportunidad_id():
    """A diferencia del Microbiólogo, este especialista NO tiene camino oportunidad_id —
    pasar solo oportunidad_id (sin frente_id) debe fallar igual que no pasar nada."""
    with pytest.raises(ValueError, match="frente_id"):
        await ia.run(contract_input={"conocimiento": {"oportunidad_id": "x"}}, verbose=False)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_contract_formato_output():
    with patch("ingeniero_ambiental_agent.run_agent_desde_frente", new=AsyncMock(
        return_value=(EVALUACION_MOCK["informe_completo"], EVALUACION_MOCK, ["leccion 1"])
    )):
        result = await ia.run(contract_input={"conocimiento": {"frente_id": "x"}}, verbose=False)

    assert result["análisis"]["informe_completo"] == EVALUACION_MOCK["informe_completo"]
    assert result["nivel_confianza"] in ("alto", "medio", "bajo")
    assert result["próximo_agente"] is None
    assert result["nuevo_conocimiento"] == ["leccion 1"]


# ── Chat conversacional (Etapa 10, 2026-08-16) ──────────────────────────────────

@pytest.mark.unit
def test_tools_chat_excluye_submit_evaluacion_tecnica():
    nombres = {t["name"] for t in ia.TOOLS_CHAT}
    assert "submit_evaluacion_tecnica" not in nombres
    assert nombres == {t["name"] for t in ia.TOOLS} - {"submit_evaluacion_tecnica"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_iniciar_sesion_arma_primer_mensaje_con_contexto_del_frente():
    with (
        patch("ingeniero_ambiental_agent.obtener_frente_con_caso", new=AsyncMock(return_value={"frente": FRENTE_TEST, "caso": CASO_TEST})),
        patch("ingeniero_ambiental_agent.obtener_pendientes_de_caso", new=AsyncMock(return_value=PENDIENTES_TEST)),
    ):
        messages = await ia.iniciar_sesion("frente-uuid-1")

    assert len(messages) == 1
    assert messages[0]["role"] == "user"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enviar_mensaje_chat_mantiene_historial():
    mock_text = type("TextBlock", (), {"type": "text", "text": "El balance de masa da..."})()
    mock_usage = type("Usage", (), {"input_tokens": 10, "output_tokens": 5})()
    mock_response = type("Response", (), {"stop_reason": "end_turn", "content": [mock_text], "usage": mock_usage})()

    with (
        patch("ingeniero_ambiental_agent._ai_complete", new=AsyncMock(return_value=mock_response)) as mock_ai,
        patch("ingeniero_ambiental_agent.obtener_frente_con_caso", new=AsyncMock(return_value={"frente": FRENTE_TEST, "caso": CASO_TEST})),
        patch("ingeniero_ambiental_agent.aprendizaje.ensure_area", new=AsyncMock()),
        patch("ingeniero_ambiental_agent.aprendizaje.bloque_lecciones_para_prompt", new=AsyncMock(return_value="")),
    ):
        respuesta, messages = await ia.enviar_mensaje([{"role": "user", "content": "contexto"}], "¿Se puede construir?", "frente-uuid-1")

    assert respuesta == "El balance de masa da..."
    assert len(messages) == 3
    _, kwargs = mock_ai.call_args
    assert kwargs["tools"] == ia.TOOLS_CHAT


# ── Integration: corrida real (contra staging) ──────────────────────────────────

@pytest.mark.integration
@pytest.mark.asyncio
async def test_invocar_agente_caso_real_helios_via_costura():
    """
    Corrida real de PUNTA A PUNTA (agente + costura), contra Anthropic + corpus INTA/CONICET +
    KM real, sobre el 'Frente técnico' real de Helios — corre contra STAGING (docs/STAGING.md),
    no producción. Pasa por invocar_agente() (no llama run_agent_desde_frente directo) porque
    ESTE agente no persiste nada por sí mismo — la costura es quien escribe el documento_caso;
    llamar la función del agente sola no prueba que el stack completo funciona. Se skippea si
    DATABASE_URL_STAGING no está configurado.
    """
    import os
    from knowledge_module.db import reset_engine
    from knowledge_module.motor import api as motor_api
    from orquestador.invocador import invocar_agente
    from orquestador.registry import AgentSpec

    staging_url = os.getenv("DATABASE_URL_STAGING")
    if not staging_url:
        pytest.skip("DATABASE_URL_STAGING no configurado — ver docs/STAGING.md")

    database_url_original = os.getenv("DATABASE_URL", "")
    os.environ["DATABASE_URL"] = staging_url
    reset_engine()
    try:
        casos_reales = await motor_api.listar(area="casos", tipo="caso", tenant="criza", limit=10)
        helios = next(c for c in casos_reales if "Helios" in c["props"].get("nombre", ""))
        frentes = await motor_api.conexiones_de(helios["id"], tipo_conexion="tiene_frente", tenant="criza")
        frente_tecnico = next(f for f in frentes if "técnico" in f["props"].get("nombre", "").lower())

        spec = AgentSpec(
            nombre="ingeniero_ambiental", modulo="ingeniero_ambiental_agent.ingeniero_ambiental_agent",
            descripcion="", prop_key="ingeniero_ambiental", activo=True, run_fn=ia.run,
        )

        output = await invocar_agente(
            spec=spec,
            contract_input={
                "conocimiento": {"frente_id": frente_tecnico["id"]},
                "tarea": "Evaluar la factibilidad de ingeniería de las rutas de concentración/valorización del efluente ya identificadas por el especialista microbiólogo.",
            },
            tenant="criza",
            frente_id=frente_tecnico["id"],
            verbose=True,
        )

        assert output["análisis"]["informe_completo"]

        # Verificación leyendo el KM (DoD del proyecto): el documento_caso quedó persistido y
        # conectado al frente real — no confiar solo en el valor de retorno.
        documentos = await motor_api.conexiones_de(
            frente_tecnico["id"], tipo_conexion="frente_produce_documento", tenant="criza"
        )
        doc_de_este_agente = [d for d in documentos if d["props"].get("agente") == "ingeniero_ambiental"]
        assert len(doc_de_este_agente) >= 1, "No se encontró ningún documento_caso del ingeniero_ambiental conectado al frente"
        assert doc_de_este_agente[-1]["props"]["contenido"] == output["análisis"]["informe_completo"]
    finally:
        os.environ["DATABASE_URL"] = database_url_original
        reset_engine()
