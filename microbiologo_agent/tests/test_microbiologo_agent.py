"""
Tests del Especialista Microbiólogo — CRIZA.

Unit: estructura de tools, SYSTEM_PROMPT (incluido el checklist anti-sesgo del Design Gate),
build_input, run_agent mock.
Integration: corrida real contra Anthropic + corpus INTA/CONICET + KM.

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

import microbiologo_agent as ma
from knowledge_module.preflight import PreflightResult

_PREFLIGHT_OK = PreflightResult(
    ok=True, bloqueantes=[], advertencias=[],
    fuentes_ok=["INTA corpus", "OpenAlex"], fuentes_no_disponibles=[],
)

OPORTUNIDAD_TEST = {
    "id": "test-uuid-1234",
    "tipo": "oportunidad",
    "props": {
        "nombre": "Tratamiento de efluentes con alta carga orgánica",
        "descripcion": "Un productor busca reducir la carga orgánica de un efluente líquido antes de su disposición final.",
    },
}

EVALUACION_MOCK = {
    "evaluacion_tecnica": {
        "resumen": {
            "valor": "Existen enfoques biológicos maduros para reducir carga orgánica en efluentes líquidos.",
            "estado": "establecido",
            "fuente": "doi:10.1234/test",
        },
        "microorganismos_o_procesos_relevantes": [
            {"nombre": "Consorcios anaeróbicos", "rol": "Degradación de materia orgánica", "estado": "establecido", "fuente": "doi:10.1234/test"},
        ],
        "enfoques_tecnicos_identificados": [
            {"enfoque": "Digestión anaeróbica en dos fases", "madurez": "maduro", "fuente": "doi:10.1234/test"},
        ],
        "riesgos_o_limitaciones": [
            {"riesgo": "Sensibilidad a variaciones de carga", "estado": "asumido"},
        ],
        "brechas_de_conocimiento": [
            {"brecha": "Rendimiento a escala industrial no documentado para esta composición específica", "impacto_en_decision": "alto", "donde_confirmar": "Ensayo piloto"},
        ],
    },
    "especialista_adicional_recomendado": {
        "si_no": True,
        "descripcion": "Se necesita análisis de ingeniería de procesos para dimensionar el sistema",
        "razon": "El análisis de literatura no permite dimensionar equipos ni estimar costos de instalación",
    },
    "informe_completo": (
        "## Evaluación Técnica — Tratamiento de Efluentes\n\n"
        "### Pregunta técnica central\n\n"
        "¿Qué enfoques biológicos existen para reducir carga orgánica en el efluente?\n\n"
        "### Búsquedas realizadas\n\n"
        "1. 'anaerobic digestion organic load wastewater treatment'\n\n"
        "### Hallazgos\n\nLa digestión anaeróbica en dos fases es un enfoque maduro..."
    ),
    "lecciones_caso": [
        "Buscar 'organic load' en vez de 'organic matter' devuelve resultados más específicos de tratamiento"
    ],
}


# ── Unit: estructura de tools ─────────────────────────────────────────────────

@pytest.mark.unit
def test_tools_count():
    assert len(ma.TOOLS) == 9, f"Esperado 9 tools, tiene {len(ma.TOOLS)}"


@pytest.mark.unit
def test_tools_names():
    nombres = {t["name"] for t in ma.TOOLS}
    assert nombres == {
        "search_literature", "buscar_corpus_cientifico", "search_corpus_inta", "expand_agrovoc",
        "search_kegg", "search_rhea", "search_uniprot", "search_bacdive",
        "submit_evaluacion_tecnica",
    }


@pytest.mark.unit
def test_search_kegg_schema():
    tool = next(t for t in ma.TOOLS if t["name"] == "search_kegg")
    assert "query" in tool["input_schema"]["required"]
    assert set(tool["input_schema"]["properties"]["database"]["enum"]) == {
        "pathway", "module", "compound", "ko", "genome",
    }


@pytest.mark.unit
def test_search_rhea_schema():
    tool = next(t for t in ma.TOOLS if t["name"] == "search_rhea")
    assert "query" in tool["input_schema"]["required"]


@pytest.mark.unit
def test_search_uniprot_schema():
    tool = next(t for t in ma.TOOLS if t["name"] == "search_uniprot")
    assert "query" in tool["input_schema"]["required"]
    assert "organism" in tool["input_schema"]["properties"]


@pytest.mark.unit
def test_search_bacdive_schema():
    tool = next(t for t in ma.TOOLS if t["name"] == "search_bacdive")
    assert "organism" in tool["input_schema"]["required"]


@pytest.mark.unit
def test_expand_agrovoc_required_fields():
    tool = next(t for t in ma.TOOLS if t["name"] == "expand_agrovoc")
    assert "term" in tool["input_schema"]["required"]


@pytest.mark.unit
def test_search_corpus_inta_required_fields():
    tool = next(t for t in ma.TOOLS if t["name"] == "search_corpus_inta")
    assert "query" in tool["input_schema"]["required"]
    props = tool["input_schema"]["properties"]
    assert "tipo" in props
    assert "limit" in props


@pytest.mark.unit
def test_submit_evaluacion_tecnica_required_fields():
    submit = next(t for t in ma.TOOLS if t["name"] == "submit_evaluacion_tecnica")
    required = submit["input_schema"].get("required", [])
    for field in ("evaluacion_tecnica", "especialista_adicional_recomendado", "informe_completo", "fuentes_y_cobertura"):
        assert field in required, f"submit_evaluacion_tecnica no tiene '{field}' en required"


@pytest.mark.unit
def test_evaluacion_tecnica_required_fields():
    submit = next(t for t in ma.TOOLS if t["name"] == "submit_evaluacion_tecnica")
    et_props = submit["input_schema"]["properties"]["evaluacion_tecnica"]
    required = et_props.get("required", [])
    for field in (
        "resumen", "microorganismos_o_procesos_relevantes",
        "enfoques_tecnicos_identificados", "riesgos_o_limitaciones", "brechas_de_conocimiento",
    ):
        assert field in required, f"evaluacion_tecnica no tiene '{field}' en required"


@pytest.mark.unit
def test_especialista_adicional_recomendado_has_si_no():
    submit = next(t for t in ma.TOOLS if t["name"] == "submit_evaluacion_tecnica")
    esp_schema = submit["input_schema"]["properties"]["especialista_adicional_recomendado"]
    assert "si_no" in esp_schema.get("required", [])
    assert esp_schema["properties"]["si_no"]["type"] == "boolean"


@pytest.mark.unit
def test_madurez_enum_values():
    submit = next(t for t in ma.TOOLS if t["name"] == "submit_evaluacion_tecnica")
    enfoque = submit["input_schema"]["properties"]["evaluacion_tecnica"]["properties"]["enfoques_tecnicos_identificados"]
    enums = enfoque["items"]["properties"]["madurez"]["enum"]
    assert set(enums) == {"maduro", "emergente", "experimental", "conceptual"}


# ── Unit: SYSTEM_PROMPT — incluye el checklist anti-sesgo del Design Gate ──────

@pytest.mark.unit
def test_system_prompt_sin_menciones_de_caso():
    """Checklist explícito del Design Gate: cero menciones de Helios/biodigestores/biogás.

    Es el control concreto contra repetir el sesgo de scientific_agent/specialist_proteins.py
    (SYSTEM_PROMPT clavado al caso cancelado 'Andrés — Buenas Maltas'). El caso entra SOLO por
    contract_input, nunca por el prompt.
    """
    sp_lower = ma.SYSTEM_PROMPT.lower()
    prohibidas = ["helios", "biogás", "biogas", "biodigestor", "mateo", "andrés", "buenas maltas"]
    for termino in prohibidas:
        assert termino not in sp_lower, f"SYSTEM_PROMPT menciona '{termino}' — viola el checklist anti-sesgo del Design Gate"


@pytest.mark.unit
def test_system_prompt_no_nombra_tipo_de_especialista():
    """Principio 7b: describe QUÉ análisis falta, no qué tipo de especialista — mismo patrón
    que evidence_generalista."""
    sp_lower = ma.SYSTEM_PROMPT.lower()
    assert "sin nombrar" in sp_lower or "sin nombrar qué tipo" in sp_lower


@pytest.mark.unit
def test_system_prompt_solucion_puede_no_ser_madura():
    sp_lower = ma.SYSTEM_PROMPT.lower()
    assert "no tener solución conocida madura" in sp_lower or "no tener" in sp_lower


@pytest.mark.unit
def test_system_prompt_menciona_submit_evaluacion_tecnica():
    assert "submit_evaluacion_tecnica" in ma.SYSTEM_PROMPT


@pytest.mark.unit
def test_system_prompt_veracidad_por_dato():
    sp = ma.SYSTEM_PROMPT
    assert "establecido" in sp and "asumido" in sp and "a-confirmar" in sp


@pytest.mark.unit
def test_system_prompt_menciona_las_4_fuentes():
    sp = ma.SYSTEM_PROMPT
    for fuente in ("search_literature", "buscar_corpus_cientifico", "search_corpus_inta", "expand_agrovoc"):
        assert fuente in sp


@pytest.mark.unit
def test_system_prompt_menciona_las_4_fuentes_bioquimicas():
    sp = ma.SYSTEM_PROMPT
    for fuente in ("search_kegg", "search_rhea", "search_uniprot", "search_bacdive"):
        assert fuente in sp


# ── Unit: build_input ─────────────────────────────────────────────────────────

@pytest.mark.unit
def test_build_input_incluye_nombre():
    result = ma.build_input("test-uuid-1234", OPORTUNIDAD_TEST)
    assert "Tratamiento de efluentes con alta carga orgánica" in result


@pytest.mark.unit
def test_build_input_incluye_instruccion():
    result = ma.build_input("test-uuid-1234", OPORTUNIDAD_TEST)
    assert "submit_evaluacion_tecnica" in result


@pytest.mark.unit
def test_build_input_sin_props_no_falla():
    oportunidad_vacia = {"id": "x", "tipo": "oportunidad", "props": {}}
    result = ma.build_input("x", oportunidad_vacia)
    assert "submit_evaluacion_tecnica" in result


# ── Unit: run_agent (mock) ──────────────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_agent_captura_submit_evaluacion_tecnica():
    mock_tool_use = type("ToolUseBlock", (), {
        "type": "tool_use", "name": "submit_evaluacion_tecnica", "id": "tool_ev_01", "input": EVALUACION_MOCK,
    })()
    mock_usage = type("Usage", (), {"input_tokens": 800, "output_tokens": 400})()
    mock_response = type("Response", (), {
        "stop_reason": "tool_use", "content": [mock_tool_use], "usage": mock_usage,
    })()

    mock_oportunidad = {"id": "test-uuid-1234", "tipo": "oportunidad", "props": {"nombre": "Test", "descripcion": "desc"}}

    with patch("microbiologo_agent._ai_complete", new=AsyncMock(return_value=mock_response)), \
         patch("microbiologo_agent.motor_api.obtener", new=AsyncMock(return_value=mock_oportunidad)), \
         patch("microbiologo_agent.motor_api.actualizar_props", new=AsyncMock(return_value={"success": True})), \
         patch("microbiologo_agent.aprendizaje.ensure_area", new=AsyncMock()), \
         patch("microbiologo_agent.run_preflight", new=AsyncMock(return_value=_PREFLIGHT_OK)), \
         patch("microbiologo_agent.aprendizaje.bloque_lecciones_para_prompt", new=AsyncMock(return_value="")):

        informe, evaluacion, lecciones = await ma.run_agent("test-uuid-1234", verbose=False)

    assert "Evaluación Técnica" in informe
    assert evaluacion["evaluacion_tecnica"]["resumen"]["estado"] == "establecido"
    assert evaluacion["especialista_adicional_recomendado"]["si_no"] is True
    assert lecciones == ["Buscar 'organic load' en vez de 'organic matter' devuelve resultados más específicos de tratamiento"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_agent_devuelve_evaluacion_lista_para_persistir():
    """run_agent NO escribe props.microbiologo al KM directamente — eso lo hace la costura,
    siempre. Acá solo se verifica que el dict devuelto está listo para que la costura lo
    persista tal cual (con informe_completo adentro)."""
    mock_tool_use = type("ToolUseBlock", (), {
        "type": "tool_use", "name": "submit_evaluacion_tecnica", "id": "tool_ev_02", "input": EVALUACION_MOCK,
    })()
    mock_usage = type("Usage", (), {"input_tokens": 100, "output_tokens": 50})()
    mock_response = type("Response", (), {
        "stop_reason": "tool_use", "content": [mock_tool_use], "usage": mock_usage,
    })()
    mock_oportunidad = {"id": "uuid-km", "tipo": "oportunidad", "props": {"nombre": "T", "descripcion": "d"}}
    mock_actualizar = AsyncMock(return_value={"success": True})

    with patch("microbiologo_agent._ai_complete", new=AsyncMock(return_value=mock_response)), \
         patch("microbiologo_agent.motor_api.obtener", new=AsyncMock(return_value=mock_oportunidad)), \
         patch("microbiologo_agent.motor_api.actualizar_props", new=mock_actualizar), \
         patch("microbiologo_agent.aprendizaje.ensure_area", new=AsyncMock()), \
         patch("microbiologo_agent.run_preflight", new=AsyncMock(return_value=_PREFLIGHT_OK)), \
         patch("microbiologo_agent.aprendizaje.bloque_lecciones_para_prompt", new=AsyncMock(return_value="")):

        informe, evaluacion_dict, _ = await ma.run_agent("uuid-km", verbose=False)

    assert "informe_completo" in evaluacion_dict
    assert evaluacion_dict["informe_completo"] == informe
    assert "evaluacion_tecnica" in evaluacion_dict

    keys_escritas = set()
    for call in mock_actualizar.call_args_list:
        if call.args and len(call.args) >= 2:
            keys_escritas.update(call.args[1].keys())
    assert "token_usage" in keys_escritas, f"'token_usage' no fue escrita al KM. Keys: {keys_escritas}"
    assert "microbiologo" not in keys_escritas, (
        "run_agent no debería escribir 'microbiologo' directamente — eso es de la costura"
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_agent_despacha_expand_agrovoc():
    agrovoc_call = type("ToolUseBlock", (), {
        "type": "tool_use", "name": "expand_agrovoc", "id": "tool_agrovoc_01", "input": {"term": "efluente"},
    })()
    mock_submit = type("ToolUseBlock", (), {
        "type": "tool_use", "name": "submit_evaluacion_tecnica", "id": "tool_ev_04", "input": EVALUACION_MOCK,
    })()
    mock_usage = type("Usage", (), {"input_tokens": 100, "output_tokens": 50})()
    mock_r1 = type("Response", (), {"stop_reason": "tool_use", "content": [agrovoc_call], "usage": mock_usage})()
    mock_r2 = type("Response", (), {"stop_reason": "tool_use", "content": [mock_submit], "usage": mock_usage})()
    mock_oportunidad = {"id": "uuid-agrovoc", "tipo": "oportunidad", "props": {"nombre": "T", "descripcion": "d"}}
    agrovoc_result = {"uri": "c_test", "prefLabel_es": "Efluente", "prefLabel_en": "Effluent"}

    with patch("microbiologo_agent._ai_complete", new=AsyncMock(side_effect=[mock_r1, mock_r2])), \
         patch("microbiologo_agent.motor_api.obtener", new=AsyncMock(return_value=mock_oportunidad)), \
         patch("microbiologo_agent.motor_api.actualizar_props", new=AsyncMock(return_value={"success": True})), \
         patch("microbiologo_agent.aprendizaje.ensure_area", new=AsyncMock()), \
         patch("microbiologo_agent.aprendizaje.bloque_lecciones_para_prompt", new=AsyncMock(return_value="")), \
         patch("microbiologo_agent.run_preflight", new=AsyncMock(return_value=_PREFLIGHT_OK)), \
         patch("microbiologo_agent._expand_agrovoc_fn", return_value=agrovoc_result) as mock_agrovoc:

        await ma.run_agent("uuid-agrovoc", verbose=False)

    mock_agrovoc.assert_called_once_with("efluente")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_agent_despacha_search_kegg():
    kegg_call = type("ToolUseBlock", (), {
        "type": "tool_use", "name": "search_kegg", "id": "tool_kegg_01",
        "input": {"query": "methane metabolism", "database": "pathway"},
    })()
    mock_submit = type("ToolUseBlock", (), {
        "type": "tool_use", "name": "submit_evaluacion_tecnica", "id": "tool_ev_05", "input": EVALUACION_MOCK,
    })()
    mock_usage = type("Usage", (), {"input_tokens": 100, "output_tokens": 50})()
    mock_r1 = type("Response", (), {"stop_reason": "tool_use", "content": [kegg_call], "usage": mock_usage})()
    mock_r2 = type("Response", (), {"stop_reason": "tool_use", "content": [mock_submit], "usage": mock_usage})()
    mock_oportunidad = {"id": "uuid-kegg", "tipo": "oportunidad", "props": {"nombre": "T", "descripcion": "d"}}
    kegg_result = {"query": "methane metabolism", "database": "pathway", "resultados": [{"id": "map00680", "nombre": "Methane metabolism"}]}

    with patch("microbiologo_agent._ai_complete", new=AsyncMock(side_effect=[mock_r1, mock_r2])), \
         patch("microbiologo_agent.motor_api.obtener", new=AsyncMock(return_value=mock_oportunidad)), \
         patch("microbiologo_agent.motor_api.actualizar_props", new=AsyncMock(return_value={"success": True})), \
         patch("microbiologo_agent.aprendizaje.ensure_area", new=AsyncMock()), \
         patch("microbiologo_agent.aprendizaje.bloque_lecciones_para_prompt", new=AsyncMock(return_value="")), \
         patch("microbiologo_agent.run_preflight", new=AsyncMock(return_value=_PREFLIGHT_OK)), \
         patch("microbiologo_agent._search_kegg_fn", return_value=kegg_result) as mock_kegg:

        await ma.run_agent("uuid-kegg", verbose=False)

    mock_kegg.assert_called_once_with(query="methane metabolism", database="pathway", max_results=10)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_agent_despacha_search_rhea():
    rhea_call = type("ToolUseBlock", (), {
        "type": "tool_use", "name": "search_rhea", "id": "tool_rhea_01", "input": {"query": "methane"},
    })()
    mock_submit = type("ToolUseBlock", (), {
        "type": "tool_use", "name": "submit_evaluacion_tecnica", "id": "tool_ev_06", "input": EVALUACION_MOCK,
    })()
    mock_usage = type("Usage", (), {"input_tokens": 100, "output_tokens": 50})()
    mock_r1 = type("Response", (), {"stop_reason": "tool_use", "content": [rhea_call], "usage": mock_usage})()
    mock_r2 = type("Response", (), {"stop_reason": "tool_use", "content": [mock_submit], "usage": mock_usage})()
    mock_oportunidad = {"id": "uuid-rhea", "tipo": "oportunidad", "props": {"nombre": "T", "descripcion": "d"}}
    rhea_result = {"query": "methane", "resultados": [{"rhea_id": "RHEA:13637", "ecuacion": "methane + ... = methanol"}]}

    with patch("microbiologo_agent._ai_complete", new=AsyncMock(side_effect=[mock_r1, mock_r2])), \
         patch("microbiologo_agent.motor_api.obtener", new=AsyncMock(return_value=mock_oportunidad)), \
         patch("microbiologo_agent.motor_api.actualizar_props", new=AsyncMock(return_value={"success": True})), \
         patch("microbiologo_agent.aprendizaje.ensure_area", new=AsyncMock()), \
         patch("microbiologo_agent.aprendizaje.bloque_lecciones_para_prompt", new=AsyncMock(return_value="")), \
         patch("microbiologo_agent.run_preflight", new=AsyncMock(return_value=_PREFLIGHT_OK)), \
         patch("microbiologo_agent._search_rhea_fn", return_value=rhea_result) as mock_rhea:

        await ma.run_agent("uuid-rhea", verbose=False)

    mock_rhea.assert_called_once_with(query="methane", max_results=10)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_agent_despacha_search_uniprot():
    uniprot_call = type("ToolUseBlock", (), {
        "type": "tool_use", "name": "search_uniprot", "id": "tool_uniprot_01",
        "input": {"query": "methane monooxygenase", "organism": "Methylococcus capsulatus"},
    })()
    mock_submit = type("ToolUseBlock", (), {
        "type": "tool_use", "name": "submit_evaluacion_tecnica", "id": "tool_ev_07", "input": EVALUACION_MOCK,
    })()
    mock_usage = type("Usage", (), {"input_tokens": 100, "output_tokens": 50})()
    mock_r1 = type("Response", (), {"stop_reason": "tool_use", "content": [uniprot_call], "usage": mock_usage})()
    mock_r2 = type("Response", (), {"stop_reason": "tool_use", "content": [mock_submit], "usage": mock_usage})()
    mock_oportunidad = {"id": "uuid-uniprot", "tipo": "oportunidad", "props": {"nombre": "T", "descripcion": "d"}}
    uniprot_result = {"query": "methane monooxygenase", "resultados": [{"accession": "G1UBD1", "ec_number": "1.14.18.3"}]}

    with patch("microbiologo_agent._ai_complete", new=AsyncMock(side_effect=[mock_r1, mock_r2])), \
         patch("microbiologo_agent.motor_api.obtener", new=AsyncMock(return_value=mock_oportunidad)), \
         patch("microbiologo_agent.motor_api.actualizar_props", new=AsyncMock(return_value={"success": True})), \
         patch("microbiologo_agent.aprendizaje.ensure_area", new=AsyncMock()), \
         patch("microbiologo_agent.aprendizaje.bloque_lecciones_para_prompt", new=AsyncMock(return_value="")), \
         patch("microbiologo_agent.run_preflight", new=AsyncMock(return_value=_PREFLIGHT_OK)), \
         patch("microbiologo_agent._search_uniprot_fn", return_value=uniprot_result) as mock_uniprot:

        await ma.run_agent("uuid-uniprot", verbose=False)

    mock_uniprot.assert_called_once_with(query="methane monooxygenase", organism="Methylococcus capsulatus", max_results=5)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_agent_despacha_search_bacdive():
    bacdive_call = type("ToolUseBlock", (), {
        "type": "tool_use", "name": "search_bacdive", "id": "tool_bacdive_01", "input": {"organism": "Methanosarcina"},
    })()
    mock_submit = type("ToolUseBlock", (), {
        "type": "tool_use", "name": "submit_evaluacion_tecnica", "id": "tool_ev_08", "input": EVALUACION_MOCK,
    })()
    mock_usage = type("Usage", (), {"input_tokens": 100, "output_tokens": 50})()
    mock_r1 = type("Response", (), {"stop_reason": "tool_use", "content": [bacdive_call], "usage": mock_usage})()
    mock_r2 = type("Response", (), {"stop_reason": "tool_use", "content": [mock_submit], "usage": mock_usage})()
    mock_oportunidad = {"id": "uuid-bacdive", "tipo": "oportunidad", "props": {"nombre": "T", "descripcion": "d"}}
    bacdive_result = {"organism": "Methanosarcina", "resultados": [{"bacdive_id": "590", "nombre_cientifico": "Methanosarcina barkeri"}]}

    with patch("microbiologo_agent._ai_complete", new=AsyncMock(side_effect=[mock_r1, mock_r2])), \
         patch("microbiologo_agent.motor_api.obtener", new=AsyncMock(return_value=mock_oportunidad)), \
         patch("microbiologo_agent.motor_api.actualizar_props", new=AsyncMock(return_value={"success": True})), \
         patch("microbiologo_agent.aprendizaje.ensure_area", new=AsyncMock()), \
         patch("microbiologo_agent.aprendizaje.bloque_lecciones_para_prompt", new=AsyncMock(return_value="")), \
         patch("microbiologo_agent.run_preflight", new=AsyncMock(return_value=_PREFLIGHT_OK)), \
         patch("microbiologo_agent._search_bacdive_fn", return_value=bacdive_result) as mock_bacdive:

        await ma.run_agent("uuid-bacdive", verbose=False)

    mock_bacdive.assert_called_once_with(organism="Methanosarcina", max_results=5)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_agent_sin_submit_devuelve_texto():
    mock_text = type("TextBlock", (), {"type": "text", "text": "Sin evaluación estructurada."})()
    mock_usage = type("Usage", (), {"input_tokens": 50, "output_tokens": 20})()
    mock_response = type("Response", (), {
        "stop_reason": "end_turn", "content": [mock_text], "usage": mock_usage,
    })()
    mock_oportunidad = {"id": "uuid-test", "tipo": "oportunidad", "props": {"nombre": "T", "descripcion": "d"}}

    with patch("microbiologo_agent._ai_complete", new=AsyncMock(return_value=mock_response)), \
         patch("microbiologo_agent.motor_api.obtener", new=AsyncMock(return_value=mock_oportunidad)), \
         patch("microbiologo_agent.motor_api.actualizar_props", new=AsyncMock(return_value={"success": True})), \
         patch("microbiologo_agent.aprendizaje.ensure_area", new=AsyncMock()), \
         patch("microbiologo_agent.run_preflight", new=AsyncMock(return_value=_PREFLIGHT_OK)), \
         patch("microbiologo_agent.aprendizaje.bloque_lecciones_para_prompt", new=AsyncMock(return_value="")):

        informe, evaluacion, lecciones = await ma.run_agent("uuid-test", verbose=False)

    assert "Sin evaluación estructurada" in informe
    assert evaluacion == {}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_agent_system_prompt_con_cache_control():
    mock_tool_use = type("ToolUseBlock", (), {
        "type": "tool_use", "name": "submit_evaluacion_tecnica", "id": "tool_cache", "input": EVALUACION_MOCK,
    })()
    mock_response = type("Response", (), {
        "stop_reason": "tool_use", "content": [mock_tool_use],
        "usage": type("Usage", (), {"input_tokens": 100, "output_tokens": 50})(),
    })()
    mock_oportunidad = {"id": "uuid-cache", "tipo": "oportunidad", "props": {"nombre": "T", "descripcion": "d"}}

    mock_complete = AsyncMock(return_value=mock_response)
    with patch("microbiologo_agent._ai_complete", new=mock_complete), \
         patch("microbiologo_agent.motor_api.obtener", new=AsyncMock(return_value=mock_oportunidad)), \
         patch("microbiologo_agent.motor_api.actualizar_props", new=AsyncMock(return_value={"success": True})), \
         patch("microbiologo_agent.aprendizaje.ensure_area", new=AsyncMock()), \
         patch("microbiologo_agent.run_preflight", new=AsyncMock(return_value=_PREFLIGHT_OK)), \
         patch("microbiologo_agent.aprendizaje.bloque_lecciones_para_prompt", new=AsyncMock(return_value="")):

        await ma.run_agent("uuid-cache", verbose=False)

    _, kwargs = mock_complete.call_args
    system = kwargs["system"]
    assert isinstance(system, list)
    assert system[0]["cache_control"] == {"type": "ephemeral"}
    assert ma.SYSTEM_PROMPT in system[0]["text"]


# ── Unit: run() — contrato SEB-115 ────────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_contract_requiere_oportunidad_id():
    with pytest.raises(ValueError, match="oportunidad_id"):
        await ma.run(contract_input={"conocimiento": {}}, verbose=False)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_contract_formato_output():
    with patch("microbiologo_agent.run_agent", new=AsyncMock(
        return_value=(EVALUACION_MOCK["informe_completo"], EVALUACION_MOCK, ["leccion 1"])
    )):
        result = await ma.run(contract_input={"conocimiento": {"oportunidad_id": "x"}}, verbose=False)

    assert result["análisis"]["informe_completo"] == EVALUACION_MOCK["informe_completo"]
    assert result["análisis"]["evaluacion_tecnica"] == EVALUACION_MOCK["evaluacion_tecnica"]
    assert result["nivel_confianza"] in ("alto", "medio", "bajo")
    assert result["próximo_agente"] is None
    assert result["nuevo_conocimiento"] == ["leccion 1"]


# ── Unit: _derive_confidence ──────────────────────────────────────────────────

@pytest.mark.unit
def test_derive_confidence_alto_con_enfoque_maduro_sin_brechas():
    evaluacion = {
        "evaluacion_tecnica": {
            "enfoques_tecnicos_identificados": [{"madurez": "maduro"}],
            "brechas_de_conocimiento": [],
        }
    }
    assert ma._derive_confidence(evaluacion) == "alto"


@pytest.mark.unit
def test_derive_confidence_bajo_sin_enfoques():
    evaluacion = {"evaluacion_tecnica": {"enfoques_tecnicos_identificados": [], "brechas_de_conocimiento": []}}
    assert ma._derive_confidence(evaluacion) == "bajo"


@pytest.mark.unit
def test_derive_confidence_medio_con_enfoque_y_una_brecha_alta():
    evaluacion = {
        "evaluacion_tecnica": {
            "enfoques_tecnicos_identificados": [{"madurez": "emergente"}],
            "brechas_de_conocimiento": [{"impacto_en_decision": "alto"}],
        }
    }
    assert ma._derive_confidence(evaluacion) == "medio"


# ── build_input_desde_frente + run_agent_desde_frente — Etapa 4 (2026-08-16) ────

FRENTE_TEST = {
    "id": "frente-uuid-1",
    "tipo": "frente",
    "props": {"nombre": "Frente técnico", "descripcion": "Definir enfoque biológico para el efluente.", "estado": "activo"},
}
CASO_TEST = {
    "id": "caso-uuid-1",
    "tipo": "caso",
    "props": {"nombre": "Efluentes biogás (Helios)", "descripcion": "Biodigestor con efluente de alta carga orgánica."},
}
PENDIENTES_TEST = [
    {"id": "pend-1", "props": {"descripcion": "Confirmar quién paga el flete.", "estado": "abierto"}},
]


@pytest.mark.unit
def test_build_input_desde_frente_incluye_caso_y_frente():
    result = ma.build_input_desde_frente(FRENTE_TEST, CASO_TEST, [])
    assert "Efluentes biogás (Helios)" in result
    assert "Frente técnico" in result
    assert "submit_evaluacion_tecnica" in result


@pytest.mark.unit
def test_build_input_desde_frente_incluye_pendientes():
    result = ma.build_input_desde_frente(FRENTE_TEST, CASO_TEST, PENDIENTES_TEST)
    assert "Confirmar quién paga el flete" in result


@pytest.mark.unit
def test_build_input_desde_frente_sin_pendientes_no_falla():
    result = ma.build_input_desde_frente(FRENTE_TEST, CASO_TEST, [])
    assert "submit_evaluacion_tecnica" in result


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_agent_desde_frente_captura_submit_y_escribe_token_usage_en_frente():
    mock_tool_use = type("ToolUseBlock", (), {
        "type": "tool_use", "name": "submit_evaluacion_tecnica", "id": "tool_ev_frente", "input": EVALUACION_MOCK,
    })()
    mock_usage = type("Usage", (), {"input_tokens": 800, "output_tokens": 400})()
    mock_response = type("Response", (), {
        "stop_reason": "tool_use", "content": [mock_tool_use], "usage": mock_usage,
    })()

    mock_actualizar = AsyncMock(return_value={"success": True})
    with patch("microbiologo_agent._ai_complete", new=AsyncMock(return_value=mock_response)), \
         patch("microbiologo_agent.obtener_frente_con_caso", new=AsyncMock(return_value={"frente": FRENTE_TEST, "caso": CASO_TEST})), \
         patch("microbiologo_agent.obtener_pendientes_de_caso", new=AsyncMock(return_value=PENDIENTES_TEST)), \
         patch("microbiologo_agent.motor_api.actualizar_props", new=mock_actualizar), \
         patch("microbiologo_agent.aprendizaje.ensure_area", new=AsyncMock()), \
         patch("microbiologo_agent.run_preflight", new=AsyncMock(return_value=_PREFLIGHT_OK)), \
         patch("microbiologo_agent.aprendizaje.bloque_lecciones_para_prompt", new=AsyncMock(return_value="")):

        informe, evaluacion, lecciones = await ma.run_agent_desde_frente("frente-uuid-1", verbose=False)

    assert "Evaluación Técnica" in informe
    assert evaluacion["evaluacion_tecnica"]["resumen"]["estado"] == "establecido"
    # token_usage se escribe sobre el FRENTE, no sobre ninguna oportunidad
    mock_actualizar.assert_awaited_once()
    args, kwargs = mock_actualizar.call_args
    assert args[0] == "frente-uuid-1"
    assert "token_usage" in args[1]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_agent_desde_frente_sin_frente_levanta_valueerror():
    with patch("microbiologo_agent.obtener_frente_con_caso", new=AsyncMock(return_value={"frente": None, "caso": None})):
        with pytest.raises(ValueError, match="no encontrado"):
            await ma.run_agent_desde_frente("no-existe")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_agent_desde_frente_sin_caso_asociado_levanta_valueerror():
    with patch("microbiologo_agent.obtener_frente_con_caso", new=AsyncMock(return_value={"frente": FRENTE_TEST, "caso": None})):
        with pytest.raises(ValueError, match="no tiene un caso asociado"):
            await ma.run_agent_desde_frente("frente-uuid-1")


# ── run() — dispatch oportunidad_id vs. frente_id (Etapa 4) ────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_contract_con_frente_id_llama_run_agent_desde_frente():
    with patch("microbiologo_agent.run_agent_desde_frente", new=AsyncMock(
        return_value=(EVALUACION_MOCK["informe_completo"], EVALUACION_MOCK, [])
    )) as mock_desde_frente, patch("microbiologo_agent.run_agent", new=AsyncMock()) as mock_oportunidad:

        result = await ma.run(contract_input={"conocimiento": {"frente_id": "frente-1"}}, verbose=False)

    mock_desde_frente.assert_awaited_once()
    mock_oportunidad.assert_not_awaited()
    assert result["análisis"]["informe_completo"] == EVALUACION_MOCK["informe_completo"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_contract_ambos_ids_a_la_vez_es_error():
    with pytest.raises(ValueError, match="mutuamente excluyentes"):
        await ma.run(contract_input={"conocimiento": {"oportunidad_id": "x", "frente_id": "y"}}, verbose=False)


# ── Chat conversacional (Etapa 10, 2026-08-16) ──────────────────────────────────

@pytest.mark.unit
def test_tools_chat_excluye_submit_evaluacion_tecnica():
    nombres = {t["name"] for t in ma.TOOLS_CHAT}
    assert "submit_evaluacion_tecnica" not in nombres
    assert nombres == {t["name"] for t in ma.TOOLS} - {"submit_evaluacion_tecnica"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_iniciar_sesion_arma_primer_mensaje_con_contexto_del_frente():
    with (
        patch("microbiologo_agent.obtener_frente_con_caso", new=AsyncMock(return_value={"frente": FRENTE_TEST, "caso": CASO_TEST})),
        patch("microbiologo_agent.obtener_pendientes_de_caso", new=AsyncMock(return_value=PENDIENTES_TEST)),
    ):
        messages = await ma.iniciar_sesion("frente-uuid-1")

    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert "Frente técnico" in messages[0]["content"]
    assert "Confirmar quién paga el flete" in messages[0]["content"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_iniciar_sesion_frente_no_encontrado_levanta_valueerror():
    with patch("microbiologo_agent.obtener_frente_con_caso", new=AsyncMock(return_value={"frente": None, "caso": None})):
        with pytest.raises(ValueError, match="no encontrado"):
            await ma.iniciar_sesion("no-existe")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enviar_mensaje_chat_mantiene_historial_y_no_usa_tools_de_submit():
    mock_text = type("TextBlock", (), {"type": "text", "text": "El enfoque de microalgas es viable si..."})()
    mock_usage = type("Usage", (), {"input_tokens": 10, "output_tokens": 5})()
    mock_response = type("Response", (), {"stop_reason": "end_turn", "content": [mock_text], "usage": mock_usage})()

    with (
        patch("microbiologo_agent._ai_complete", new=AsyncMock(return_value=mock_response)) as mock_ai,
        patch("microbiologo_agent.obtener_frente_con_caso", new=AsyncMock(return_value={"frente": FRENTE_TEST, "caso": CASO_TEST})),
        patch("microbiologo_agent.aprendizaje.ensure_area", new=AsyncMock()),
        patch("microbiologo_agent.aprendizaje.bloque_lecciones_para_prompt", new=AsyncMock(return_value="")),
    ):
        respuesta, messages = await ma.enviar_mensaje([{"role": "user", "content": "contexto inicial"}], "¿Qué opinás de microalgas?", "frente-uuid-1")

    assert respuesta == "El enfoque de microalgas es viable si..."
    assert len(messages) == 3  # contexto inicial + pregunta + respuesta
    assert messages[1] == {"role": "user", "content": "¿Qué opinás de microalgas?"}
    _, kwargs = mock_ai.call_args
    assert kwargs["tools"] == ma.TOOLS_CHAT


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enviar_mensaje_chat_despacha_tool_sin_forzar_submit():
    tool_call = type("ToolUseBlock", (), {"type": "tool_use", "name": "expand_agrovoc", "id": "t1", "input": {"term": "biodigestor"}})()
    mock_usage = type("Usage", (), {"input_tokens": 10, "output_tokens": 5})()
    r1 = type("Response", (), {"stop_reason": "tool_use", "content": [tool_call], "usage": mock_usage})()
    mock_text = type("TextBlock", (), {"type": "text", "text": "Según AGROVOC, biodigestor se relaciona con..."})()
    r2 = type("Response", (), {"stop_reason": "end_turn", "content": [mock_text], "usage": mock_usage})()

    with (
        patch("microbiologo_agent._ai_complete", new=AsyncMock(side_effect=[r1, r2])),
        patch("microbiologo_agent.obtener_frente_con_caso", new=AsyncMock(return_value={"frente": FRENTE_TEST, "caso": CASO_TEST})),
        patch("microbiologo_agent.aprendizaje.ensure_area", new=AsyncMock()),
        patch("microbiologo_agent.aprendizaje.bloque_lecciones_para_prompt", new=AsyncMock(return_value="")),
        patch("microbiologo_agent._expand_agrovoc_fn", return_value={"found": True, "term": "biodigestor"}) as mock_expand,
    ):
        respuesta, messages = await ma.enviar_mensaje([], "¿Qué significa biodigestor en AGROVOC?", "frente-uuid-1")

    mock_expand.assert_called_once()
    assert respuesta == "Según AGROVOC, biodigestor se relaciona con..."


# ── Integration: corrida real ─────────────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.asyncio
async def test_run_agent_caso_real():
    """Corrida real contra Anthropic + corpus INTA/CONICET + KM real."""
    from knowledge_module.db import reset_engine
    from knowledge_module.motor import api as motor_api

    reset_engine()

    creada = await motor_api.guardar_ficha(
        area="descubrimiento", tipo="oportunidad", tenant="criza",
        campos={
            "nombre": "TEST microbiologo_agent — borrar",
            "descripcion": (
                "Prueba de integración del Especialista Microbiólogo — tratamiento biológico "
                "de un efluente líquido con alta carga orgánica proveniente de un proceso "
                "industrial de fermentación."
            ),
        },
    )
    oportunidad_id = creada["id"]

    informe, evaluacion, lecciones = await ma.run_agent(oportunidad_id, verbose=True)

    assert isinstance(informe, str) and len(informe) > 100
    assert "evaluacion_tecnica" in evaluacion
    assert "enfoques_tecnicos_identificados" in evaluacion["evaluacion_tecnica"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_run_agent_desde_frente_caso_real_helios():
    """
    Corrida real contra Anthropic + corpus INTA/CONICET + KM, vía el modelo de casos.yaml
    (frente_id) en vez de oportunidad_id — Etapa 4 del plan (2026-08-16).

    Corre contra el branch de STAGING (docs/STAGING.md), no producción — escribe un
    documento_caso real conectado al 'Frente técnico' real de Helios. Se skippea si
    DATABASE_URL_STAGING no está configurado, en vez de arriesgar escribir contra producción.
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

        spec = AgentSpec(nombre="microbiologo", modulo="microbiologo_agent.microbiologo_agent",
                          descripcion="", prop_key="microbiologo", activo=True, run_fn=ma.run)

        output = await invocar_agente(
            spec=spec,
            contract_input={"conocimiento": {"frente_id": frente_tecnico["id"]}},
            tenant="criza",
            frente_id=frente_tecnico["id"],
            verbose=True,
        )

        assert output["análisis"]["informe_completo"]

        # Verificación leyendo el KM (DoD del proyecto): el documento_caso quedó persistido y
        # conectado al frente real.
        documentos = await motor_api.conexiones_de(
            frente_tecnico["id"], tipo_conexion="frente_produce_documento", tenant="criza"
        )
        assert len(documentos) >= 1
        assert documentos[-1]["props"]["contenido"] == output["análisis"]["informe_completo"]
    finally:
        os.environ["DATABASE_URL"] = database_url_original
        reset_engine()
