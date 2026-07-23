"""
Tests del Evidence Generalista — CRIZA.

Unit: estructura de tools, SYSTEM_PROMPT, build_input, run_agent mock.
Integration: corrida real contra Anthropic + OpenAlex + KM.

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

import evidence_generalista as eg
from knowledge_module.preflight import PreflightResult

_PREFLIGHT_OK = PreflightResult(
    ok=True, bloqueantes=[], advertencias=[],
    fuentes_ok=["INTA corpus", "OpenAlex"], fuentes_no_disponibles=[],
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

OPORTUNIDAD_CON_MERCADO = {
    "id": "test-uuid-1234",
    "tipo": "oportunidad",
    "props": {
        "nombre": "Reducción de olor en efluentes porcinos",
        "descripcion": "Productores porcinos con problemas de olor en efluentes.",
        "mercado": {
            "cruce_1": {
                "dolor": {
                    "descripcion": "Olor intenso de efluentes porcinos que genera conflictos con vecinos",
                    "quien_lo_sufre": "Productores porcinos en zonas rurales/periurbanas",
                    "impacto_economico": {"valor": "Multas y pérdida de habilitaciones", "estado": "asumido"}
                }
            },
            "informe_completo": "## Análisis de Mercado\n\nHay demanda real..."
        }
    }
}

OPORTUNIDAD_SIN_MERCADO = {
    "id": "test-uuid-5678",
    "tipo": "oportunidad",
    "props": {
        "nombre": "Test sin mercado",
        "descripcion": "Una oportunidad de prueba sin análisis de mercado previo."
    }
}

EVIDENCIA_MOCK = {
    "cruce_2": {
        "solucion_propuesta": {
            "valor": "Reducción biológica de compuestos azufrados volátiles",
            "estado": "asumido",
            "fuente": "doi:10.1234/test"
        },
        "estado_cientifico": {
            "valor": "emergente",
            "justificacion": "Estudios en escala laboratorio, sin escalado industrial probado",
            "estado": "establecido",
            "fuente": "doi:10.1234/test"
        },
        "factibilidad_produccion": {
            "valor": "socio",
            "que_requiere": "Proceso de control microbiológico en condiciones anaeróbicas",
            "estado": "a-confirmar"
        },
        "ventaja_vs_incumbente": {
            "valor": "Mayor selectividad con menor impacto ambiental vs. tratamiento químico",
            "estado": "asumido"
        },
        "brechas_tecnicas": [
            {"brecha": "Escalado industrial no probado", "impacto_en_decision": "alto", "donde_confirmar": "Literatura de bioreactores industriales"},
            {"brecha": "Estabilidad en condiciones variables", "impacto_en_decision": "medio"}
        ],
        "evidencia": {
            "fuentes": ["doi:10.1234/test", "doi:10.5678/test2"],
            "estado": "establecido"
        }
    },
    "especialista_recomendado": {
        "si_no": True,
        "descripcion": "Se necesita análisis profundo de escalado de proceso y condiciones de producción",
        "razon": "La literatura de screening no permite evaluar viabilidad de producción a escala"
    },
    "informe_completo": (
        "## Análisis de Evidencia — Reducción de Olor en Efluentes Porcinos\n\n"
        "### Pregunta técnica central\n\n"
        "¿Existe base científica para reducir compuestos odoríferos en efluentes porcinos?\n\n"
        "### Búsquedas realizadas\n\n"
        "1. 'swine manure odor reduction biological'\n"
        "2. 'hydrogen sulfide ammonia livestock waste treatment'\n\n"
        "### Hallazgos\n\n"
        "La evidencia indica que la reducción biológica es factible a nivel laboratorio..."
    ),
    "lecciones_caso": [
        "Buscar en inglés 'odor' en lugar de 'olor' devuelve muchos más resultados relevantes"
    ]
}


# ── Unit: estructura de tools ─────────────────────────────────────────────────

@pytest.mark.unit
def test_tools_count():
    assert len(eg.TOOLS) == 5, f"Esperado 5 tools, tiene {len(eg.TOOLS)}"

@pytest.mark.unit
def test_tools_names():
    nombres = {t["name"] for t in eg.TOOLS}
    assert nombres == {"search_literature", "buscar_corpus_cientifico", "search_corpus_inta", "expand_agrovoc", "submit_evidencia"}

@pytest.mark.unit
def test_expand_agrovoc_required_fields():
    tool = next(t for t in eg.TOOLS if t["name"] == "expand_agrovoc")
    assert "term" in tool["input_schema"]["required"]

@pytest.mark.unit
def test_system_prompt_menciona_agrovoc():
    assert "expand_agrovoc" in eg.SYSTEM_PROMPT or "AGROVOC" in eg.SYSTEM_PROMPT

@pytest.mark.unit
def test_search_corpus_inta_required_fields():
    tool = next(t for t in eg.TOOLS if t["name"] == "search_corpus_inta")
    assert "query" in tool["input_schema"]["required"]
    props = tool["input_schema"]["properties"]
    assert "tipo" in props
    assert "limit" in props
    assert props["tipo"]["enum"] == ["paper", "reporte", "norma", "patente", "otro",
                                       "tesis", "ponencia", "libro", "parte_libro", "divulgacion", "folleto"]

@pytest.mark.unit
def test_system_prompt_menciona_corpus_inta():
    assert "search_corpus_inta" in eg.SYSTEM_PROMPT

@pytest.mark.unit
def test_submit_evidencia_required_fields():
    submit = next(t for t in eg.TOOLS if t["name"] == "submit_evidencia")
    required = submit["input_schema"].get("required", [])
    for field in ("cruce_2", "especialista_recomendado", "informe_completo"):
        assert field in required, f"submit_evidencia no tiene '{field}' en required"

@pytest.mark.unit
def test_cruce_2_required_fields():
    submit = next(t for t in eg.TOOLS if t["name"] == "submit_evidencia")
    cruce_2_props = submit["input_schema"]["properties"]["cruce_2"]
    required = cruce_2_props.get("required", [])
    for field in ("solucion_propuesta", "estado_cientifico", "factibilidad_produccion",
                  "ventaja_vs_incumbente", "brechas_tecnicas", "evidencia"):
        assert field in required, f"cruce_2 no tiene '{field}' en required"

@pytest.mark.unit
def test_especialista_recomendado_has_si_no():
    submit = next(t for t in eg.TOOLS if t["name"] == "submit_evidencia")
    esp_schema = submit["input_schema"]["properties"]["especialista_recomendado"]
    assert "si_no" in esp_schema.get("required", [])
    assert esp_schema["properties"]["si_no"]["type"] == "boolean"

@pytest.mark.unit
def test_estado_cientifico_enum_values():
    """estado_cientifico.valor debe tener los 4 niveles del gate."""
    submit = next(t for t in eg.TOOLS if t["name"] == "submit_evidencia")
    ec = submit["input_schema"]["properties"]["cruce_2"]["properties"]["estado_cientifico"]
    enums = ec["properties"]["valor"]["enum"]
    assert set(enums) == {"maduro", "emergente", "experimental", "conceptual"}

@pytest.mark.unit
def test_factibilidad_produccion_enum_values():
    submit = next(t for t in eg.TOOLS if t["name"] == "submit_evidencia")
    fp = submit["input_schema"]["properties"]["cruce_2"]["properties"]["factibilidad_produccion"]
    enums = fp["properties"]["valor"]["enum"]
    assert set(enums) == {"propia", "socio", "hibrida", "a-confirmar"}


# ── Unit: SYSTEM_PROMPT ───────────────────────────────────────────────────────

@pytest.mark.unit
def test_system_prompt_technology_agnostic():
    """SYSTEM_PROMPT no debe mencionar tecnologías específicas (principio 7b)."""
    sp_lower = eg.SYSTEM_PROMPT.lower()
    tecnologias = ["fermentación", "enzima", "fitasa", "bioreactor", "antibiótico",
                   "probiótico", "proteína recombinante", "crispr", "pcr"]
    for tech in tecnologias:
        assert tech not in sp_lower, f"SYSTEM_PROMPT menciona '{tech}' — viola principio 7b"

@pytest.mark.unit
def test_system_prompt_solucion_puede_no_existir():
    """SYSTEM_PROMPT debe indicar que la solución puede no existir o no tener base conocida aún."""
    sp_lower = eg.SYSTEM_PROMPT.lower()
    assert "puede no tener" in sp_lower or "puede no existir" in sp_lower or "no existe" in sp_lower

@pytest.mark.unit
def test_system_prompt_menciona_submit_evidencia():
    assert "submit_evidencia" in eg.SYSTEM_PROMPT

@pytest.mark.unit
def test_system_prompt_veracidad_por_dato():
    """SYSTEM_PROMPT debe instruir veracidad por dato (establecido/asumido/a-confirmar)."""
    sp = eg.SYSTEM_PROMPT
    assert "establecido" in sp and "asumido" in sp and "a-confirmar" in sp


# ── Unit: build_input ─────────────────────────────────────────────────────────

@pytest.mark.unit
def test_build_input_incluye_nombre():
    result = eg.build_input("test-uuid-1234", OPORTUNIDAD_CON_MERCADO)
    assert "Reducción de olor en efluentes porcinos" in result

@pytest.mark.unit
def test_build_input_incluye_cruce_1():
    result = eg.build_input("test-uuid-1234", OPORTUNIDAD_CON_MERCADO)
    assert "cruce_1" in result or "dolor" in result.lower()

@pytest.mark.unit
def test_build_input_informe_no_aparece_como_clave_json():
    """informe_completo debe aparecer como texto, no como clave JSON."""
    result = eg.build_input("test-uuid-1234", OPORTUNIDAD_CON_MERCADO)
    assert '"informe_completo"' not in result

@pytest.mark.unit
def test_build_input_sin_mercado_no_falla():
    result = eg.build_input("test-uuid-5678", OPORTUNIDAD_SIN_MERCADO)
    assert "Test sin mercado" in result
    assert "submit_evidencia" in result

@pytest.mark.unit
def test_build_input_include_instruccion_final():
    result = eg.build_input("test-uuid-1234", OPORTUNIDAD_CON_MERCADO)
    assert "submit_evidencia" in result


# ── Unit: run_agent (mock) ────────────────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_agent_captura_submit_evidencia():
    """run_agent debe capturar submit_evidencia y retornar la estructura correcta."""
    mock_tool_use = type("ToolUseBlock", (), {
        "type": "tool_use",
        "name": "submit_evidencia",
        "id": "tool_ev_01",
        "input": EVIDENCIA_MOCK,
    })()
    mock_usage = type("Usage", (), {"input_tokens": 800, "output_tokens": 400})()
    mock_response = type("Response", (), {
        "stop_reason": "tool_use",
        "content": [mock_tool_use],
        "usage": mock_usage,
    })()

    mock_oportunidad = {
        "id": "test-uuid-1234", "tipo": "oportunidad",
        "props": {"nombre": "Test", "descripcion": "desc"}
    }

    with patch("evidence_generalista.anthropic.Anthropic") as mock_anthropic, \
         patch("evidence_generalista.motor_api.obtener", new=AsyncMock(return_value=mock_oportunidad)), \
         patch("evidence_generalista.motor_api.actualizar_props", new=AsyncMock(return_value={"success": True})), \
         patch("evidence_generalista.aprendizaje.ensure_area", new=AsyncMock()), \
         patch("evidence_generalista.run_preflight", new=AsyncMock(return_value=_PREFLIGHT_OK)), \
         patch("evidence_generalista.aprendizaje.bloque_lecciones_para_prompt", new=AsyncMock(return_value="")):
        mock_anthropic.return_value.messages.create.return_value = mock_response

        informe, evidencia, lecciones = await eg.run_agent("test-uuid-1234", verbose=False)

    assert "Análisis de Evidencia" in informe
    assert evidencia["cruce_2"]["estado_cientifico"]["valor"] == "emergente"
    assert evidencia["especialista_recomendado"]["si_no"] is True
    assert lecciones == ["Buscar en inglés 'odor' en lugar de 'olor' devuelve muchos más resultados relevantes"]

@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_agent_escribe_evidencia_al_km():
    """run_agent debe llamar actualizar_props con la clave 'evidencia'."""
    mock_tool_use = type("ToolUseBlock", (), {
        "type": "tool_use", "name": "submit_evidencia", "id": "tool_ev_02",
        "input": EVIDENCIA_MOCK,
    })()
    mock_usage = type("Usage", (), {"input_tokens": 100, "output_tokens": 50})()
    mock_response = type("Response", (), {
        "stop_reason": "tool_use", "content": [mock_tool_use], "usage": mock_usage,
    })()
    mock_oportunidad = {"id": "uuid-km", "tipo": "oportunidad", "props": {"nombre": "T", "descripcion": "d"}}
    mock_actualizar = AsyncMock(return_value={"success": True})

    with patch("evidence_generalista.anthropic.Anthropic") as mock_anthropic, \
         patch("evidence_generalista.motor_api.obtener", new=AsyncMock(return_value=mock_oportunidad)), \
         patch("evidence_generalista.motor_api.actualizar_props", new=mock_actualizar), \
         patch("evidence_generalista.aprendizaje.ensure_area", new=AsyncMock()), \
         patch("evidence_generalista.run_preflight", new=AsyncMock(return_value=_PREFLIGHT_OK)), \
         patch("evidence_generalista.aprendizaje.bloque_lecciones_para_prompt", new=AsyncMock(return_value="")):
        mock_anthropic.return_value.messages.create.return_value = mock_response

        await eg.run_agent("uuid-km", verbose=False)

    # Verificar que se escribió 'evidencia' al KM
    keys_escritas = set()
    for call in mock_actualizar.call_args_list:
        if call.args and len(call.args) >= 2:
            keys_escritas.update(call.args[1].keys())
    assert "evidencia" in keys_escritas, f"'evidencia' no fue escrita al KM. Keys: {keys_escritas}"
    assert "token_usage" in keys_escritas, f"'token_usage' no fue escrita al KM. Keys: {keys_escritas}"

@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_agent_despacha_expand_agrovoc():
    """run_agent debe llamar _expand_agrovoc_fn cuando el agente usa expand_agrovoc."""
    agrovoc_call = type("ToolUseBlock", (), {
        "type": "tool_use", "name": "expand_agrovoc", "id": "tool_agrovoc_01",
        "input": {"term": "tick biocontrol"},
    })()
    mock_submit = type("ToolUseBlock", (), {
        "type": "tool_use", "name": "submit_evidencia", "id": "tool_ev_04",
        "input": EVIDENCIA_MOCK,
    })()
    mock_usage = type("Usage", (), {"input_tokens": 100, "output_tokens": 50})()
    mock_r1 = type("Response", (), {"stop_reason": "tool_use", "content": [agrovoc_call], "usage": mock_usage})()
    mock_r2 = type("Response", (), {"stop_reason": "tool_use", "content": [mock_submit], "usage": mock_usage})()
    mock_oportunidad = {"id": "uuid-agrovoc", "tipo": "oportunidad", "props": {"nombre": "T", "descripcion": "d"}}
    agrovoc_result = {"uri": "c_b9625ac6", "prefLabel_es": "Garrapata", "prefLabel_en": "ticks"}

    with patch("evidence_generalista.anthropic.Anthropic") as mock_anthropic, \
         patch("evidence_generalista.motor_api.obtener", new=AsyncMock(return_value=mock_oportunidad)), \
         patch("evidence_generalista.motor_api.actualizar_props", new=AsyncMock(return_value={"success": True})), \
         patch("evidence_generalista.aprendizaje.ensure_area", new=AsyncMock()), \
         patch("evidence_generalista.aprendizaje.bloque_lecciones_para_prompt", new=AsyncMock(return_value="")), \
         patch("evidence_generalista.run_preflight", new=AsyncMock(return_value=_PREFLIGHT_OK)), \
         patch("evidence_generalista._expand_agrovoc_fn", return_value=agrovoc_result) as mock_agrovoc:
        mock_anthropic.return_value.messages.create.side_effect = [mock_r1, mock_r2]

        await eg.run_agent("uuid-agrovoc", verbose=False)

    mock_agrovoc.assert_called_once_with("tick biocontrol")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_agent_despacha_search_corpus_inta():
    """run_agent debe llamar _search_inta_fn cuando el agente usa search_corpus_inta."""
    mock_inta_call = type("ToolUseBlock", (), {
        "type": "tool_use", "name": "search_corpus_inta", "id": "tool_inta_01",
        "input": {"query": "garrapata biocontrol", "limit": 5},
    })()
    mock_submit = type("ToolUseBlock", (), {
        "type": "tool_use", "name": "submit_evidencia", "id": "tool_ev_03",
        "input": EVIDENCIA_MOCK,
    })()
    mock_usage = type("Usage", (), {"input_tokens": 100, "output_tokens": 50})()
    mock_r1 = type("Response", (), {"stop_reason": "tool_use", "content": [mock_inta_call], "usage": mock_usage})()
    mock_r2 = type("Response", (), {"stop_reason": "tool_use", "content": [mock_submit], "usage": mock_usage})()
    mock_oportunidad = {"id": "uuid-inta", "tipo": "oportunidad", "props": {"nombre": "T", "descripcion": "d"}}
    inta_mock_result = {"success": True, "data": {"query": "garrapata biocontrol", "total": 2, "results": []}}

    with patch("evidence_generalista.anthropic.Anthropic") as mock_anthropic, \
         patch("evidence_generalista.motor_api.obtener", new=AsyncMock(return_value=mock_oportunidad)), \
         patch("evidence_generalista.motor_api.actualizar_props", new=AsyncMock(return_value={"success": True})), \
         patch("evidence_generalista.aprendizaje.ensure_area", new=AsyncMock()), \
         patch("evidence_generalista.aprendizaje.bloque_lecciones_para_prompt", new=AsyncMock(return_value="")), \
         patch("evidence_generalista.run_preflight", new=AsyncMock(return_value=_PREFLIGHT_OK)), \
         patch("evidence_generalista._search_inta_fn", new=AsyncMock(return_value=inta_mock_result)) as mock_inta:
        mock_anthropic.return_value.messages.create.side_effect = [mock_r1, mock_r2]

        await eg.run_agent("uuid-inta", verbose=False)

    mock_inta.assert_called_once_with(query="garrapata biocontrol", tipo=None, limit=5, tenant_id="criza")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_agent_sin_submit_devuelve_texto():
    """Si el agente no llama submit_evidencia, run_agent devuelve el texto raw."""
    mock_text = type("TextBlock", (), {"type": "text", "text": "Sin evidencia estructurada."})()
    mock_usage = type("Usage", (), {"input_tokens": 50, "output_tokens": 20})()
    mock_response = type("Response", (), {
        "stop_reason": "end_turn", "content": [mock_text], "usage": mock_usage,
    })()
    mock_oportunidad = {"id": "uuid-test", "tipo": "oportunidad", "props": {"nombre": "T", "descripcion": "d"}}

    with patch("evidence_generalista.anthropic.Anthropic") as mock_anthropic, \
         patch("evidence_generalista.motor_api.obtener", new=AsyncMock(return_value=mock_oportunidad)), \
         patch("evidence_generalista.motor_api.actualizar_props", new=AsyncMock(return_value={"success": True})), \
         patch("evidence_generalista.aprendizaje.ensure_area", new=AsyncMock()), \
         patch("evidence_generalista.run_preflight", new=AsyncMock(return_value=_PREFLIGHT_OK)), \
         patch("evidence_generalista.aprendizaje.bloque_lecciones_para_prompt", new=AsyncMock(return_value="")):
        mock_anthropic.return_value.messages.create.return_value = mock_response

        informe, evidencia, lecciones = await eg.run_agent("uuid-test", verbose=False)

    assert "Sin evidencia estructurada" in informe
    assert evidencia == {}
    assert lecciones == []


# ── Unit: contrato estándar (SEB-115) ────────────────────────────────────────

@pytest.mark.unit
def test_input_contract_tiene_campos_requeridos():
    """INPUT_CONTRACT debe exponer los 5 campos del contrato estándar."""
    assert set(eg.INPUT_CONTRACT["fields"].keys()) == {"caso", "tarea", "contexto", "conocimiento", "herramientas"}
    assert eg.INPUT_CONTRACT["agent"] == "evidencia"


@pytest.mark.unit
def test_output_contract_tiene_campos_requeridos():
    """OUTPUT_CONTRACT debe exponer los 5 campos del contrato estándar."""
    assert set(eg.OUTPUT_CONTRACT["fields"].keys()) == {"análisis", "nivel_confianza", "recomendaciones", "próximo_agente", "nuevo_conocimiento"}


@pytest.mark.unit
def test_output_contract_proximo_agente_puede_ser_especialista():
    assert "cientifico_especialista" in eg.OUTPUT_CONTRACT["fields"]["próximo_agente"]


# ── Unit: patrón anti-sesgo por estructura (orchestration-layer.md Decisión 6) ──

@pytest.mark.unit
def test_system_prompt_carga_marco_blue_ocean():
    """El marco blue ocean debe estar prependido al SYSTEM_PROMPT."""
    assert "sustitución de importación" in eg.SYSTEM_PROMPT.lower()


@pytest.mark.unit
def test_submit_evidencia_requiere_fuentes_y_cobertura():
    submit = next(t for t in eg.TOOLS if t["name"] == "submit_evidencia")
    assert "fuentes_y_cobertura" in submit["input_schema"]["required"]


@pytest.mark.unit
def test_search_corpus_inta_default_es_exhaustivo():
    """El default de limit debe ser alto (no muestrea) — ver orchestration-layer.md Decisión 6."""
    tool = next(t for t in eg.TOOLS if t["name"] == "search_corpus_inta")
    assert tool["input_schema"]["properties"]["limit"]["default"] >= 1000


def _make_db_mock(count: int):
    from unittest.mock import MagicMock
    mock_result = MagicMock()
    mock_result.scalar.return_value = count

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    mock_factory_instance = MagicMock(return_value=mock_cm)
    return MagicMock(return_value=mock_factory_instance)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_inta_corpus_ok():
    with patch("evidence_generalista.get_session_factory", return_value=_make_db_mock(1643)()):
        resultado = await eg._check_inta_corpus()
    assert resultado.ok is True
    assert resultado.conteo == 1643


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_inta_corpus_vacio_bloquea():
    with patch("evidence_generalista.get_session_factory", return_value=_make_db_mock(0)()):
        resultado = await eg._check_inta_corpus()
    assert resultado.ok is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_corpus_cientifico_ok():
    with patch("evidence_generalista.get_session_factory", return_value=_make_db_mock(2268)()):
        resultado = await eg._check_corpus_cientifico()
    assert resultado.ok is True
    assert resultado.conteo == 2268


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_corpus_cientifico_vacio_bloquea():
    with patch("evidence_generalista.get_session_factory", return_value=_make_db_mock(0)()):
        resultado = await eg._check_corpus_cientifico()
    assert resultado.ok is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_openalex_caido_es_advertencia():
    with patch("evidence_generalista._search_literature_fn", side_effect=Exception("503")):
        resultado = await eg._check_openalex()
    assert resultado.ok is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_agent_frena_si_preflight_bloqueante():
    """Pre-flight bloqueante debe abortar antes del loop agéntico (objective-first)."""
    from knowledge_module.preflight import PreflightResult

    bloqueado = PreflightResult(ok=False, bloqueantes=["INTA corpus: 0 documentos"], advertencias=[])
    mock_oportunidad = {"id": "uuid-x", "tipo": "oportunidad", "props": {"nombre": "T", "descripcion": "d"}}

    with (
        patch("evidence_generalista.motor_api.obtener", new=AsyncMock(return_value=mock_oportunidad)),
        patch("evidence_generalista.run_preflight", new=AsyncMock(return_value=bloqueado)),
    ):
        with pytest.raises(RuntimeError, match="Pre-flight bloqueante"):
            await eg.run_agent("uuid-x", verbose=False)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_inta_fn_es_exhaustivo_via_get_sector_corpus():
    """_search_inta_fn debe delegar en get_sector_corpus (OR sin límite artificial), no en FTS con LIMIT."""
    corpus_exhaustivo = {
        "success": True,
        "data": {
            "terminos_buscados": ["garrapata", "biocontrol"],
            "total": 3,
            "docs_con_texto_completo": 2,
            "documentos": [
                {"id": "1", "titulo": "Paper 1", "tipo": "paper"},
                {"id": "2", "titulo": "Paper 2", "tipo": "tesis"},
                {"id": "3", "titulo": "Paper 3", "tipo": "paper"},
            ],
        },
    }
    with patch("evidence_generalista._get_sector_corpus_fn", new=AsyncMock(return_value=corpus_exhaustivo)) as mock_fn:
        resultado = await eg._search_inta_fn("garrapata biocontrol")

    mock_fn.assert_called_once()
    llamado_con = mock_fn.call_args[0][0]
    assert set(llamado_con) == {"garrapata", "biocontrol"}
    assert resultado["data"]["total"] == 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_search_inta_fn_filtra_por_tipo_en_python():
    """El filtro por tipo se aplica sobre el resultado exhaustivo, no en la query SQL."""
    corpus_exhaustivo = {
        "success": True,
        "data": {"documentos": [
            {"id": "1", "titulo": "Paper 1", "tipo": "paper"},
            {"id": "2", "titulo": "Tesis 1", "tipo": "tesis"},
        ]},
    }
    with patch("evidence_generalista._get_sector_corpus_fn", new=AsyncMock(return_value=corpus_exhaustivo)):
        resultado = await eg._search_inta_fn("garrapata", tipo="tesis")

    assert resultado["data"]["total"] == 1
    assert resultado["data"]["results"][0]["tipo"] == "tesis"


@pytest.mark.unit
def test_derive_confidence_establecido_sin_brechas():
    evidencia = {
        "cruce_2": {
            "estado_cientifico": {"estado": "establecido"},
            "brechas_tecnicas": [],
        }
    }
    assert eg._derive_confidence(evidencia) == "alto"


@pytest.mark.unit
def test_derive_confidence_brecha_alta():
    evidencia = {
        "cruce_2": {
            "estado_cientifico": {"estado": "establecido"},
            "brechas_tecnicas": [{"brecha": "X", "impacto_en_decision": "alto"}],
        }
    }
    assert eg._derive_confidence(evidencia) == "medio"


@pytest.mark.unit
def test_derive_confidence_a_confirmar():
    evidencia = {
        "cruce_2": {
            "estado_cientifico": {"estado": "a-confirmar"},
            "brechas_tecnicas": [{"brecha": "X", "impacto_en_decision": "alto"}, {"brecha": "Y", "impacto_en_decision": "alto"}],
        }
    }
    assert eg._derive_confidence(evidencia) == "bajo"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_contract_formato_output():
    """run() retorna el formato estándar de contrato."""
    informe = "## Análisis de evidencia"
    evidencia_mock = {
        "cruce_2": {
            "estado_cientifico": {"estado": "establecido"},
            "brechas_tecnicas": [{"brecha": "Escalado", "impacto_en_decision": "alto"}],
        },
        "especialista_recomendado": {"si_no": True},
    }
    lecciones = ["lección de prueba"]

    with patch("evidence_generalista.run_agent", new=AsyncMock(return_value=(informe, evidencia_mock, lecciones))):
        result = await eg.run({"conocimiento": {"oportunidad_id": "uuid-abc"}})

    assert "análisis" in result
    assert result["análisis"]["informe"] == informe
    assert result["nivel_confianza"] == "medio"
    assert result["recomendaciones"] == ["Escalado"]
    assert result["próximo_agente"] == "cientifico_especialista"
    assert result["nuevo_conocimiento"] == lecciones


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_contract_sin_oportunidad_id_falla():
    """run() sin oportunidad_id debe lanzar ValueError."""
    with pytest.raises(ValueError, match="oportunidad_id"):
        await eg.run({"caso": "test", "conocimiento": {}})


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_contract_proximo_agente_none_si_no_especialista():
    """run() retorna próximo_agente=None si especialista_recomendado.si_no=False."""
    evidencia_mock = {
        "cruce_2": {"estado_cientifico": {"estado": "establecido"}, "brechas_tecnicas": []},
        "especialista_recomendado": {"si_no": False},
    }

    with patch("evidence_generalista.run_agent", new=AsyncMock(return_value=("informe", evidencia_mock, []))):
        result = await eg.run({"conocimiento": {"oportunidad_id": "uuid-xyz"}})

    assert result["próximo_agente"] is None


# ── Integration ───────────────────────────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.asyncio
async def test_run_agent_caso_real():
    """[INTEGRATION] Corre contra Anthropic + OpenAlex + KM reales."""
    oportunidad_id = "COMPLETAR_CON_ID_REAL"
    informe, evidencia, lecciones = await eg.run_agent(oportunidad_id, verbose=True)
    assert len(informe) > 100
    assert "cruce_2" in evidencia
    assert "especialista_recomendado" in evidencia
    assert "estado_cientifico" in evidencia.get("cruce_2", {})


# ── _bloque_instruccion (cable tarea/contexto/foco, 2026-07-22) ───────────────

@pytest.mark.unit
def test_bloque_instruccion_vacio_si_no_hay_nada():
    assert eg._bloque_instruccion(None, None, None) == ""


@pytest.mark.unit
def test_bloque_instruccion_incluye_los_tres_campos():
    bloque = eg._bloque_instruccion("Llenar cruce 2", "contexto extra", "candidato X")
    assert "Llenar cruce 2" in bloque
    assert "contexto extra" in bloque
    assert "candidato X" in bloque


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_agent_system_prompt_con_cache_control():
    """Prompt caching (2026-07-22): el loop reenvía el mismo system+tools en cada
    vuelta — sin cache_control, ese prefijo se factura a precio pleno todas las veces."""
    mock_tool_use = type("ToolUseBlock", (), {
        "type": "tool_use", "name": "submit_evidencia", "id": "tool_cache", "input": EVIDENCIA_MOCK,
    })()
    mock_response = type("Response", (), {
        "stop_reason": "tool_use", "content": [mock_tool_use],
        "usage": type("Usage", (), {"input_tokens": 100, "output_tokens": 50})(),
    })()
    mock_oportunidad = {"id": "uuid-cache", "tipo": "oportunidad", "props": {"nombre": "T", "descripcion": "d"}}

    with patch("evidence_generalista.anthropic.Anthropic") as mock_anthropic, \
         patch("evidence_generalista.motor_api.obtener", new=AsyncMock(return_value=mock_oportunidad)), \
         patch("evidence_generalista.motor_api.actualizar_props", new=AsyncMock(return_value={"success": True})), \
         patch("evidence_generalista.aprendizaje.ensure_area", new=AsyncMock()), \
         patch("evidence_generalista.run_preflight", new=AsyncMock(return_value=_PREFLIGHT_OK)), \
         patch("evidence_generalista.aprendizaje.bloque_lecciones_para_prompt", new=AsyncMock(return_value="")):
        mock_create = mock_anthropic.return_value.messages.create
        mock_create.return_value = mock_response

        await eg.run_agent("uuid-cache", verbose=False)

    _, kwargs = mock_create.call_args
    system = kwargs["system"]
    assert isinstance(system, list)
    assert system[0]["cache_control"] == {"type": "ephemeral"}
    assert eg.SYSTEM_PROMPT in system[0]["text"]
