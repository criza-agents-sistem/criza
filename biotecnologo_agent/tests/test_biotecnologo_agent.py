"""
Tests del Especialista Biotecnólogo — CRIZA.

Unit: estructura de tools, SYSTEM_PROMPT (checklist anti-sesgo), build_input_desde_frente,
run_agent_desde_frente mock, run() solo acepta frente_id, dispatch de las tools nuevas
(search_pubchem/search_chebi) y reusadas (search_kegg/search_rhea).
Integration: corrida real contra Anthropic + corpus INTA/CONICET + KM (producción), vía la costura.

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

import biotecnologo_agent as bt
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
            "valor": "El digestato es un buen sustrato de bioproceso para producir PHA (bioplástico) vía bacterias acumuladoras.",
            "estado": "establecido",
            "fuente": "doi:10.1234/test",
        },
        "microorganismos_o_procesos_relevantes": [
            {"nombre": "Producción de PHA a partir de VFA", "rol": "Biosíntesis del bioplástico", "estado": "establecido", "fuente": "doi:10.1234/test"},
        ],
        "enfoques_tecnicos_identificados": [
            {"enfoque": "Fermentación de VFA a PHA con cultivos mixtos", "madurez": "emergente", "fuente": "doi:10.1234/test"},
        ],
        "riesgos_o_limitaciones": [
            {"riesgo": "Rendimiento de conversión variable según composición del VFA", "estado": "asumido"},
        ],
        "brechas_de_conocimiento": [
            {"brecha": "Falta caracterización del perfil de VFA específico de este efluente", "impacto_en_decision": "alto", "donde_confirmar": "Análisis de laboratorio"},
        ],
    },
    "especialista_adicional_recomendado": {
        "si_no": False,
        "descripcion": "",
        "razon": "",
    },
    "informe_completo": (
        "## Evaluación Biotecnológica — PHA a partir del digestato de Helios\n\n"
        "### Pregunta central\n\n"
        "¿Qué producto de valor se puede fabricar a partir del efluente vía bioproceso?\n\n"
        "### Búsquedas realizadas\n\n"
        "1. 'PHA production volatile fatty acids mixed culture'\n\n"
        "### Hallazgos\n\nLa producción de PHA a partir de VFA es una ruta emergente..."
    ),
    "lecciones_caso": [
        "Buscar 'VFA to PHA' en vez de 'effluent bioplastic' devuelve resultados más específicos de ruta"
    ],
}


# ── Unit: estructura de tools ─────────────────────────────────────────────────

@pytest.mark.unit
def test_tools_count():
    assert len(bt.TOOLS) == 11, f"Esperado 11 tools, tiene {len(bt.TOOLS)}"


@pytest.mark.unit
def test_tools_names():
    nombres = {t["name"] for t in bt.TOOLS}
    assert nombres == {
        "search_literature", "buscar_corpus_cientifico", "search_corpus_inta", "expand_agrovoc",
        "buscar_web_tecnico", "search_kegg", "search_rhea", "search_pubchem", "search_chebi",
        "ver_informe_especialista", "submit_evaluacion_tecnica",
    }


@pytest.mark.unit
def test_submit_evaluacion_tecnica_required_fields():
    submit = next(t for t in bt.TOOLS if t["name"] == "submit_evaluacion_tecnica")
    required = submit["input_schema"].get("required", [])
    for field in ("evaluacion_tecnica", "especialista_adicional_recomendado", "informe_completo", "fuentes_y_cobertura"):
        assert field in required


# ── Unit: SYSTEM_PROMPT — checklist anti-sesgo ─────────────────────────────────

@pytest.mark.unit
def test_system_prompt_sin_menciones_de_caso():
    """Mismo control que los otros 3 especialistas — cero menciones de Helios/biogás/biodigestor/
    Mateo/Andrés (checklist central contra el sesgo de specialist_proteins.py)."""
    sp_lower = bt.SYSTEM_PROMPT.lower()
    prohibidas = ["helios", "biogás", "biogas", "biodigestor", "mateo", "andrés", "buenas maltas"]
    for termino in prohibidas:
        assert termino not in sp_lower, f"SYSTEM_PROMPT menciona '{termino}' — viola el checklist anti-sesgo"


@pytest.mark.unit
def test_system_prompt_no_nombra_tipo_de_especialista():
    sp_lower = bt.SYSTEM_PROMPT.lower()
    assert "sin nombrar" in sp_lower


@pytest.mark.unit
def test_system_prompt_menciona_submit_evaluacion_tecnica():
    assert "submit_evaluacion_tecnica" in bt.SYSTEM_PROMPT


@pytest.mark.unit
def test_system_prompt_veracidad_por_dato():
    sp = bt.SYSTEM_PROMPT
    assert "establecido" in sp and "asumido" in sp and "a-confirmar" in sp


@pytest.mark.unit
def test_system_prompt_distingue_producto_de_tratamiento_e_ingenieria():
    """El prompt debe dejar claro que evalúa QUÉ FABRICAR vía bioproceso — no tratamiento del
    material ni ingeniería de planta ni uso agronómico, el ángulo distinto de los otros 3."""
    sp_lower = bt.SYSTEM_PROMPT.lower()
    assert "bioproceso" in sp_lower
    assert "fabricar" in sp_lower or "biosíntesis" in sp_lower


# ── Unit: build_input_desde_frente ──────────────────────────────────────────────

@pytest.mark.unit
def test_build_input_desde_frente_incluye_caso_y_frente():
    result = bt.build_input_desde_frente(FRENTE_TEST, CASO_TEST, [])
    assert "Efluentes biogás (Helios)" in result
    assert "Frente técnico" in result
    assert "submit_evaluacion_tecnica" in result


@pytest.mark.unit
def test_build_input_desde_frente_incluye_pendientes():
    result = bt.build_input_desde_frente(FRENTE_TEST, CASO_TEST, PENDIENTES_TEST)
    assert "Confirmar quién paga el flete" in result


@pytest.mark.unit
def test_build_input_desde_frente_incluye_documentos_aportados():
    aportados = [{"props": {"titulo": "Helios_Informe_Tecnico_Digerido.pdf", "contenido": "N amonio: 1200 mg/L"}}]
    result = bt.build_input_desde_frente(FRENTE_TEST, CASO_TEST, [], aportados)
    assert "Helios_Informe_Tecnico_Digerido.pdf" in result
    assert "N amonio: 1200 mg/L" in result


@pytest.mark.unit
def test_build_input_desde_frente_incluye_documentos_producidos():
    """Etapa 20, 2026-09-05 -- Sebas: 'estaría bueno que todos puedan ver qué está realizando
    el resto'. Solo la lista liviana (título/agente/fecha/id), no el contenido completo."""
    producidos = [
        {"id": "doc-1", "props": {"titulo": "Evaluación — biotecnologo", "agente": "biotecnologo"}, "creado_en": "2026-08-17T22:28:04"},
    ]
    result = bt.build_input_desde_frente(FRENTE_TEST, CASO_TEST, [], None, producidos)
    assert "doc-1" in result
    assert "Evaluación — biotecnologo" in result
    assert "biotecnologo" in result
    assert "ver_informe_especialista" in result


@pytest.mark.unit
def test_build_input_desde_frente_sin_documentos_producidos_no_falla():
    result = bt.build_input_desde_frente(FRENTE_TEST, CASO_TEST, [])
    assert "Informes ya producidos" not in result


@pytest.mark.unit
@pytest.mark.asyncio
async def test_despachar_tool_ver_informe_especialista():
    with patch("biotecnologo_agent.obtener_documento_por_id", new=AsyncMock(return_value={"titulo": "t", "contenido": "c"})) as mock_fn:
        result = await bt._despachar_tool("ver_informe_especialista", {"documento_id": "doc-1"}, verbose=False)
    mock_fn.assert_awaited_once_with("doc-1", tenant=bt._TENANT)
    assert result == {"titulo": "t", "contenido": "c"}


@pytest.mark.unit
def test_build_input_desde_frente_sin_documentos_aportados_no_falla():
    result = bt.build_input_desde_frente(FRENTE_TEST, CASO_TEST, [])
    assert "Documentos aportados" not in result


# ── Unit: dispatch de tools nuevas/reusadas ─────────────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_despachar_tool_search_pubchem():
    with patch("biotecnologo_agent._search_pubchem_fn", return_value={"encontrado": True, "formula": "H16MgNO10P"}) as mock_fn:
        result = await bt._despachar_tool("search_pubchem", {"query": "struvite"}, verbose=False)
    mock_fn.assert_called_once_with(query="struvite")
    assert result["formula"] == "H16MgNO10P"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_despachar_tool_search_chebi():
    with patch("biotecnologo_agent._search_chebi_fn", return_value={"total_encontrados": 1}) as mock_fn:
        result = await bt._despachar_tool("search_chebi", {"query": "glucose", "max_results": 3}, verbose=False)
    mock_fn.assert_called_once_with(query="glucose", max_results=3)
    assert result["total_encontrados"] == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_despachar_tool_search_kegg_reusado():
    with patch("biotecnologo_agent._search_kegg_fn", return_value={"resultados": []}) as mock_fn:
        await bt._despachar_tool("search_kegg", {"query": "PHA biosynthesis"}, verbose=False)
    mock_fn.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_despachar_tool_search_rhea_reusado():
    with patch("biotecnologo_agent._search_rhea_fn", return_value={"resultados": []}) as mock_fn:
        await bt._despachar_tool("search_rhea", {"query": "PHA synthase"}, verbose=False)
    mock_fn.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_despachar_tool_pubchem_captura_excepcion():
    with patch("biotecnologo_agent._search_pubchem_fn", side_effect=Exception("timeout")):
        result = await bt._despachar_tool("search_pubchem", {"query": "x"}, verbose=False)
    assert "error" in result


# ── Unit: exhaustividad (Etapa 22, 2026-09-14) ──────────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_despachar_tool_search_literature_usa_variante_exhaustiva():
    with patch("biotecnologo_agent._search_literature_exhaustivo_fn", return_value={"results": []}) as mock_fn:
        await bt._despachar_tool("search_literature", {"query": "PHA production", "max_results": 5}, verbose=False)
    mock_fn.assert_called_once_with(query="PHA production", max_total=40)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_despachar_tool_search_literature_registra_en_el_tracker():
    tracker: dict = {}
    with patch("biotecnologo_agent._search_literature_exhaustivo_fn", return_value={"results": []}):
        await bt._despachar_tool("search_literature", {"query": "PHA production"}, verbose=False, consultas_tracker=tracker)
        await bt._despachar_tool("search_literature", {"query": "bioplastic from waste"}, verbose=False, consultas_tracker=tracker)
    assert tracker["search_literature"] == ["PHA production", "bioplastic from waste"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_despachar_tool_buscar_corpus_cientifico_ignora_limit_del_modelo():
    with patch("biotecnologo_agent._buscar_corpus_cientifico_fn", new=AsyncMock(return_value={"papers": []})) as mock_fn:
        await bt._despachar_tool("buscar_corpus_cientifico", {"consulta": "digestato", "limit": 5}, verbose=False)
    mock_fn.assert_awaited_once_with(consulta="digestato", limit=150)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_despachar_tool_search_corpus_inta_ignora_limit_del_modelo():
    with patch("biotecnologo_agent._search_inta_fn", new=AsyncMock(return_value={"success": True, "data": {"results": []}})) as mock_fn:
        await bt._despachar_tool("search_corpus_inta", {"query": "digestato", "limit": 5000}, verbose=False)
    mock_fn.assert_awaited_once_with(query="digestato", tipo=None, limit=150, tenant_id=bt._TENANT)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_despachar_tool_buscar_web_tecnico():
    with patch("biotecnologo_agent._buscar_web_tecnico_fn", return_value={"results": [{"titulo": "x"}]}) as mock_fn:
        result = await bt._despachar_tool("buscar_web_tecnico", {"query": "ectoine product", "idioma": "en", "pais": "us"}, verbose=False)
    mock_fn.assert_called_once_with(query="ectoine product", idioma="en", pais="us", max_total=30)
    assert result["results"][0]["titulo"] == "x"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_despachar_tool_buscar_web_tecnico_registra_en_el_tracker():
    tracker: dict = {}
    with patch("biotecnologo_agent._buscar_web_tecnico_fn", return_value={"results": []}):
        await bt._despachar_tool("buscar_web_tecnico", {"query": "en inglés", "idioma": "en"}, verbose=False, consultas_tracker=tracker)
        await bt._despachar_tool("buscar_web_tecnico", {"query": "en español", "idioma": "es"}, verbose=False, consultas_tracker=tracker)
    assert tracker["buscar_web_tecnico"] == ["en inglés", "en español"]


@pytest.mark.unit
def test_chequear_exhaustividad_rechaza_sin_ninguna_busqueda():
    error = bt._chequear_exhaustividad({})
    assert error is not None
    assert "search_literature" in error


@pytest.mark.unit
def test_chequear_exhaustividad_rechaza_con_pocas_variantes():
    tracker = {"search_literature": ["PHA production", "PHA production "]}  # 1 sola distinta tras normalizar
    error = bt._chequear_exhaustividad(tracker)
    assert error is not None


@pytest.mark.unit
def test_chequear_exhaustividad_rechaza_sin_corpus_cientifico():
    tracker = {"search_literature": [f"query {i}" for i in range(4)]}
    error = bt._chequear_exhaustividad(tracker)
    assert error is not None
    assert "buscar_corpus_cientifico" in error


@pytest.mark.unit
def test_chequear_exhaustividad_rechaza_sin_corpus_inta():
    tracker = {
        "search_literature": [f"query {i}" for i in range(4)],
        "buscar_corpus_cientifico": ["digestato"],
    }
    error = bt._chequear_exhaustividad(tracker)
    assert error is not None
    assert "search_corpus_inta" in error


@pytest.mark.unit
def test_chequear_exhaustividad_rechaza_sin_suficientes_variantes_web():
    tracker = {
        "search_literature": [f"query {i}" for i in range(4)],
        "buscar_corpus_cientifico": ["digestato"],
        "search_corpus_inta": ["digestato"],
        "buscar_web_tecnico": ["digestate valorization"],  # solo 1, hace falta 2
    }
    error = bt._chequear_exhaustividad(tracker)
    assert error is not None
    assert "buscar_web_tecnico" in error


@pytest.mark.unit
def test_chequear_exhaustividad_ok_con_el_minimo_cumplido():
    tracker = {
        "search_literature": [f"query {i}" for i in range(4)],
        "buscar_corpus_cientifico": ["digestato"],
        "search_corpus_inta": ["digestato"],
        "buscar_web_tecnico": ["digestate valorization products", "productos valorización digestato"],
    }
    assert bt._chequear_exhaustividad(tracker) is None


@pytest.mark.unit
def test_resumen_corto_para_poda_incluye_query_y_tool():
    resumen = bt._resumen_corto_para_poda("search_literature", {"query": "PHA production"})
    assert "search_literature" in resumen
    assert "PHA production" in resumen


@pytest.mark.unit
def test_resumen_corto_para_poda_sin_query_no_falla():
    resumen = bt._resumen_corto_para_poda("ver_informe_especialista", {"documento_id": "doc-1"})
    assert "doc-1" in resumen


@pytest.mark.unit
def test_podar_tool_results_viejos_reemplaza_solo_lo_que_esta_en_resumenes():
    messages = [
        {"role": "user", "content": "input inicial"},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "search_literature"}]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": "{\"muchos\": \"datos\", \"papers\": [1, 2, 3]}"},
        ]},
    ]
    resumenes = {"t1": "[search_literature('x') — resumido]"}
    bt._podar_tool_results_viejos(messages, resumenes)

    assert messages[2]["content"][0]["content"] == "[search_literature('x') — resumido]"
    assert messages[0]["content"] == "input inicial"  # el mensaje de texto plano no se toca


@pytest.mark.unit
def test_podar_tool_results_viejos_no_toca_lo_que_no_esta_en_resumenes():
    """El batch del turno actual (todavía no agregado a `resumenes`) queda intacto — es
    justamente lo que no hay que podar todavía."""
    messages = [
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t2", "content": "{\"dato\": \"fresco\"}"},
        ]},
    ]
    bt._podar_tool_results_viejos(messages, {})  # t2 no está en resumenes todavía
    assert messages[0]["content"][0]["content"] == "{\"dato\": \"fresco\"}"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_loop_poda_resultados_de_turnos_anteriores():
    """Encontrado real (2026-09-14): sin podar, una corrida real llegó al 96% del límite de
    contexto con solo 8 búsquedas — este test confirma que el historial se poda de verdad, no
    solo que la función existe.

    3 turnos: (1) todo lo que exige el gate, de una — 4 variantes de search_literature +
    corpus_cientifico + corpus_inta, con contenido "pesado" simulado; (2) una búsqueda extra
    cualquiera, cuyo único propósito es disparar la poda del turno 1 antes del 3er llamado;
    (3) submit (el gate ya estaba satisfecho desde el turno 1)."""
    busquedas_turno_1 = [
        type("ToolUseBlock", (), {"type": "tool_use", "name": "search_literature", "id": f"tl{i}", "input": {"query": f"query {i}"}})()
        for i in range(4)
    ] + [
        type("ToolUseBlock", (), {"type": "tool_use", "name": "buscar_corpus_cientifico", "id": "tc1", "input": {"consulta": "digestato"}})(),
        type("ToolUseBlock", (), {"type": "tool_use", "name": "search_corpus_inta", "id": "ti1", "input": {"query": "digestato"}})(),
        type("ToolUseBlock", (), {"type": "tool_use", "name": "buscar_web_tecnico", "id": "wt1", "input": {"query": "digestate product", "idioma": "en"}})(),
        type("ToolUseBlock", (), {"type": "tool_use", "name": "buscar_web_tecnico", "id": "wt2", "input": {"query": "producto digestato", "idioma": "es"}})(),
    ]
    busqueda_turno_2 = type("ToolUseBlock", (), {"type": "tool_use", "name": "search_literature", "id": "tl_extra", "input": {"query": "query extra"}})()
    submit = type("ToolUseBlock", (), {"type": "tool_use", "name": "submit_evaluacion_tecnica", "id": "s1", "input": EVALUACION_MOCK})()
    mock_usage = type("Usage", (), {"input_tokens": 100, "output_tokens": 50})()

    respuestas = [
        type("Response", (), {"stop_reason": "tool_use", "content": busquedas_turno_1, "usage": mock_usage})(),
        type("Response", (), {"stop_reason": "tool_use", "content": [busqueda_turno_2], "usage": mock_usage})(),
        type("Response", (), {"stop_reason": "tool_use", "content": [submit], "usage": mock_usage})(),
    ]

    mensajes_vistos_por_turno = []

    async def fake_ai_complete(**kwargs):
        mensajes_vistos_por_turno.append([dict(m) for m in kwargs["messages"]])
        return respuestas[len(mensajes_vistos_por_turno) - 1]

    contenido_pesado = {"results": [{"title": "x" * 500}], "total_traido": 1}
    with (
        patch("biotecnologo_agent._ai_complete", new=fake_ai_complete),
        patch("biotecnologo_agent._search_literature_exhaustivo_fn", return_value=contenido_pesado),
        patch("biotecnologo_agent._buscar_corpus_cientifico_fn", new=AsyncMock(return_value={"papers": []})),
        patch("biotecnologo_agent._search_inta_fn", new=AsyncMock(return_value={"success": True, "data": {"results": []}})),
        patch("biotecnologo_agent._buscar_web_tecnico_fn", return_value={"results": []}),
    ):
        await bt._run_loop("op-1", [{"type": "text", "text": "system"}], "input", bt.DEFAULT_MODEL, verbose=False)

    assert len(mensajes_vistos_por_turno) == 3

    # Lo que se manda en el 3er llamado: el resultado de tl0 (turno 1) tiene que estar podado —
    # el modelo ya lo vio al generar la respuesta del turno 2.
    mensajes_del_3er_turno = mensajes_vistos_por_turno[2]
    tool_result_tl0 = next(
        b for m in mensajes_del_3er_turno if isinstance(m.get("content"), list)
        for b in m["content"] if isinstance(b, dict) and b.get("tool_use_id") == "tl0"
    )
    assert "query 0" in tool_result_tl0["content"]
    assert "x" * 500 not in tool_result_tl0["content"]  # el contenido pesado ya no está


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_loop_rechaza_submit_sin_busqueda_exhaustiva_y_reintenta():
    """El modelo intenta cerrar sin buscar nada — el gate lo rechaza, el loop sigue (no
    termina), y en el segundo intento (ya con las 3 fuentes usadas) se acepta."""
    submit_sin_buscar = type("ToolUseBlock", (), {
        "type": "tool_use", "name": "submit_evaluacion_tecnica", "id": "t1", "input": EVALUACION_MOCK,
    })()
    tool_calls = [
        type("ToolUseBlock", (), {"type": "tool_use", "name": "search_literature", "id": f"tl{i}", "input": {"query": f"query {i}"}})()
        for i in range(4)
    ] + [
        type("ToolUseBlock", (), {"type": "tool_use", "name": "buscar_corpus_cientifico", "id": "tc1", "input": {"consulta": "digestato"}})(),
        type("ToolUseBlock", (), {"type": "tool_use", "name": "search_corpus_inta", "id": "ti1", "input": {"query": "digestato"}})(),
        type("ToolUseBlock", (), {"type": "tool_use", "name": "buscar_web_tecnico", "id": "wt1", "input": {"query": "digestate product", "idioma": "en"}})(),
        type("ToolUseBlock", (), {"type": "tool_use", "name": "buscar_web_tecnico", "id": "wt2", "input": {"query": "producto digestato", "idioma": "es"}})(),
    ]
    submit_ok = type("ToolUseBlock", (), {
        "type": "tool_use", "name": "submit_evaluacion_tecnica", "id": "t2", "input": EVALUACION_MOCK,
    })()
    mock_usage = type("Usage", (), {"input_tokens": 100, "output_tokens": 50})()

    respuestas = [
        type("Response", (), {"stop_reason": "tool_use", "content": [submit_sin_buscar], "usage": mock_usage})(),
        type("Response", (), {"stop_reason": "tool_use", "content": tool_calls, "usage": mock_usage})(),
        type("Response", (), {"stop_reason": "tool_use", "content": [submit_ok], "usage": mock_usage})(),
    ]

    with (
        patch("biotecnologo_agent._ai_complete", new=AsyncMock(side_effect=respuestas)) as mock_ai,
        patch("biotecnologo_agent._search_literature_exhaustivo_fn", return_value={"results": []}),
        patch("biotecnologo_agent._buscar_corpus_cientifico_fn", new=AsyncMock(return_value={"papers": []})),
        patch("biotecnologo_agent._search_inta_fn", new=AsyncMock(return_value={"success": True, "data": {"results": []}})),
        patch("biotecnologo_agent._buscar_web_tecnico_fn", return_value={"results": []}),
    ):
        informe, evaluacion, lecciones, tracker = await bt._run_loop(
            "op-1", [{"type": "text", "text": "system"}], "input de prueba", bt.DEFAULT_MODEL, verbose=False,
        )

    assert mock_ai.call_count == 3  # rechazado, buscó, aceptado — no se coló en el primer intento
    assert evaluacion["evaluacion_tecnica"]["resumen"]["estado"] == "establecido"
    assert evaluacion["fuentes_y_cobertura"]["gate_exhaustividad"]["cumplido_de_verdad"] is True
    assert evaluacion["fuentes_y_cobertura"]["gate_exhaustividad"]["variantes_search_literature"] == 4


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_loop_valvula_de_seguridad_deja_pasar_tras_maximo_de_rechazos():
    """Si el modelo insiste en cerrar sin cumplir el mínimo, no queda en loop infinito — se lo
    deja pasar después de _MAX_RECHAZOS_EXHAUSTIVIDAD intentos, marcado como no cumplido de
    verdad en fuentes_y_cobertura (auditable, no oculto)."""
    submit_sin_buscar = type("ToolUseBlock", (), {
        "type": "tool_use", "name": "submit_evaluacion_tecnica", "id": "t1", "input": EVALUACION_MOCK,
    })()
    mock_usage = type("Usage", (), {"input_tokens": 100, "output_tokens": 50})()
    mock_response = type("Response", (), {"stop_reason": "tool_use", "content": [submit_sin_buscar], "usage": mock_usage})()

    with patch("biotecnologo_agent._ai_complete", new=AsyncMock(return_value=mock_response)) as mock_ai:
        informe, evaluacion, lecciones, tracker = await bt._run_loop(
            "op-1", [{"type": "text", "text": "system"}], "input de prueba", bt.DEFAULT_MODEL, verbose=False,
        )

    assert mock_ai.call_count == bt._MAX_RECHAZOS_EXHAUSTIVIDAD + 1  # 3 rechazos + el que se acepta
    assert evaluacion["fuentes_y_cobertura"]["gate_exhaustividad"]["cumplido_de_verdad"] is False


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
    with patch("biotecnologo_agent._ai_complete", new=AsyncMock(return_value=mock_response)), \
         patch("biotecnologo_agent.obtener_frente_con_caso", new=AsyncMock(return_value={"frente": FRENTE_TEST, "caso": CASO_TEST})), \
         patch("biotecnologo_agent.obtener_pendientes_de_caso", new=AsyncMock(return_value=PENDIENTES_TEST)), \
         patch("biotecnologo_agent.obtener_documentos_aportados_de_frente", new=AsyncMock(return_value=[])), \
         patch("biotecnologo_agent.obtener_documentos_de_frente", new=AsyncMock(return_value=[])), \
         patch("biotecnologo_agent.motor_api.actualizar_props", new=mock_actualizar), \
         patch("biotecnologo_agent.aprendizaje.ensure_area", new=AsyncMock()), \
         patch("biotecnologo_agent.run_preflight", new=AsyncMock(return_value=_PREFLIGHT_OK)), \
         patch("biotecnologo_agent.aprendizaje.bloque_lecciones_para_prompt", new=AsyncMock(return_value="")):

        informe, evaluacion, lecciones = await bt.run_agent_desde_frente("frente-uuid-1", verbose=False)

    assert "Evaluación Biotecnológica" in informe
    assert evaluacion["evaluacion_tecnica"]["resumen"]["estado"] == "establecido"
    mock_actualizar.assert_awaited_once()
    args, kwargs = mock_actualizar.call_args
    assert args[0] == "frente-uuid-1"
    assert "token_usage" in args[1]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_agent_desde_frente_sin_frente_levanta_valueerror():
    with patch("biotecnologo_agent.obtener_frente_con_caso", new=AsyncMock(return_value={"frente": None, "caso": None})):
        with pytest.raises(ValueError, match="no encontrado"):
            await bt.run_agent_desde_frente("no-existe")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_agent_desde_frente_sin_caso_asociado_levanta_valueerror():
    with patch("biotecnologo_agent.obtener_frente_con_caso", new=AsyncMock(return_value={"frente": FRENTE_TEST, "caso": None})):
        with pytest.raises(ValueError, match="no tiene un caso asociado"):
            await bt.run_agent_desde_frente("frente-uuid-1")


# ── Unit: _derive_confidence ──────────────────────────────────────────────────

@pytest.mark.unit
def test_derive_confidence_alto_con_enfoque_maduro_sin_brechas():
    evaluacion = {
        "evaluacion_tecnica": {
            "enfoques_tecnicos_identificados": [{"madurez": "maduro"}],
            "brechas_de_conocimiento": [],
        }
    }
    assert bt._derive_confidence(evaluacion) == "alto"


@pytest.mark.unit
def test_derive_confidence_bajo_sin_enfoques():
    evaluacion = {"evaluacion_tecnica": {"enfoques_tecnicos_identificados": [], "brechas_de_conocimiento": []}}
    assert bt._derive_confidence(evaluacion) == "bajo"


# ── Unit: run() — contrato SEB-115, solo frente_id ──────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_contract_requiere_frente_id():
    with pytest.raises(ValueError, match="frente_id"):
        await bt.run(contract_input={"conocimiento": {}}, verbose=False)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_contract_no_acepta_oportunidad_id():
    with pytest.raises(ValueError, match="frente_id"):
        await bt.run(contract_input={"conocimiento": {"oportunidad_id": "x"}}, verbose=False)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_contract_formato_output():
    with patch("biotecnologo_agent.run_agent_desde_frente", new=AsyncMock(
        return_value=(EVALUACION_MOCK["informe_completo"], EVALUACION_MOCK, ["leccion 1"])
    )):
        result = await bt.run(contract_input={"conocimiento": {"frente_id": "x"}}, verbose=False)

    assert result["análisis"]["informe_completo"] == EVALUACION_MOCK["informe_completo"]
    assert result["nivel_confianza"] in ("alto", "medio", "bajo")
    assert result["próximo_agente"] is None
    assert result["nuevo_conocimiento"] == ["leccion 1"]


# ── Chat conversacional ──────────────────────────────────────────────────────

@pytest.mark.unit
def test_tools_chat_excluye_submit_evaluacion_tecnica():
    nombres = {t["name"] for t in bt.TOOLS_CHAT}
    assert "submit_evaluacion_tecnica" not in nombres
    assert nombres == {t["name"] for t in bt.TOOLS} - {"submit_evaluacion_tecnica"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_iniciar_sesion_arma_primer_mensaje_con_contexto_del_frente():
    with (
        patch("biotecnologo_agent.obtener_frente_con_caso", new=AsyncMock(return_value={"frente": FRENTE_TEST, "caso": CASO_TEST})),
        patch("biotecnologo_agent.obtener_pendientes_de_caso", new=AsyncMock(return_value=PENDIENTES_TEST)),
        patch("biotecnologo_agent.obtener_documentos_aportados_de_frente", new=AsyncMock(return_value=[])),
        patch("biotecnologo_agent.obtener_documentos_de_frente", new=AsyncMock(return_value=[])),
    ):
        messages = await bt.iniciar_sesion("frente-uuid-1")

    assert len(messages) == 1
    assert messages[0]["role"] == "user"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enviar_mensaje_chat_mantiene_historial():
    mock_text = type("TextBlock", (), {"type": "text", "text": "Como bioplástico..."})()
    mock_usage = type("Usage", (), {"input_tokens": 10, "output_tokens": 5})()
    mock_response = type("Response", (), {"stop_reason": "end_turn", "content": [mock_text], "usage": mock_usage})()

    with (
        patch("biotecnologo_agent._ai_complete", new=AsyncMock(return_value=mock_response)) as mock_ai,
        patch("biotecnologo_agent.obtener_frente_con_caso", new=AsyncMock(return_value={"frente": FRENTE_TEST, "caso": CASO_TEST})),
        patch("biotecnologo_agent.aprendizaje.ensure_area", new=AsyncMock()),
        patch("biotecnologo_agent.aprendizaje.bloque_lecciones_para_prompt", new=AsyncMock(return_value="")),
    ):
        respuesta, messages = await bt.enviar_mensaje([{"role": "user", "content": "contexto"}], "¿Qué producto se puede fabricar?", "frente-uuid-1")

    assert respuesta == "Como bioplástico..."
    assert len(messages) == 3
    _, kwargs = mock_ai.call_args
    assert kwargs["tools"] == bt.TOOLS_CHAT


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enviar_mensaje_consulta_libre_sin_frente():
    """frente_id=None es consulta libre — no debe llamar obtener_frente_con_caso."""
    mock_text = type("TextBlock", (), {"type": "text", "text": "Depende del sustrato..."})()
    mock_usage = type("Usage", (), {"input_tokens": 10, "output_tokens": 5})()
    mock_response = type("Response", (), {"stop_reason": "end_turn", "content": [mock_text], "usage": mock_usage})()

    with (
        patch("biotecnologo_agent._ai_complete", new=AsyncMock(return_value=mock_response)),
        patch("biotecnologo_agent.obtener_frente_con_caso", new=AsyncMock()) as mock_frente,
        patch("biotecnologo_agent.aprendizaje.ensure_area", new=AsyncMock()),
        patch("biotecnologo_agent.aprendizaje.bloque_lecciones_para_prompt", new=AsyncMock(return_value="")),
    ):
        respuesta, messages = await bt.enviar_mensaje([], "¿Qué se puede fabricar con VFA?")

    assert respuesta == "Depende del sustrato..."
    mock_frente.assert_not_awaited()


# ── Integration: corrida real vía la costura (contra producción) ───────────────

@pytest.mark.integration
@pytest.mark.asyncio
async def test_invocar_agente_caso_real_helios_via_costura():
    """
    Corrida real de PUNTA A PUNTA (agente + costura) contra Anthropic + corpus INTA/CONICET +
    KM real, sobre el 'Frente técnico' real de Helios — corre contra STAGING (docs/STAGING.md),
    no producción, mismo criterio que agronomo_agent/ingeniero_ambiental_agent. Pasa por
    invocar_agente() (lección de la Etapa 7: el agente solo no persiste nada, hay que probar el
    stack completo). Se skippea si DATABASE_URL_STAGING no está configurado.
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
        await _correr_integration_test(motor_api, invocar_agente, AgentSpec)
    finally:
        os.environ["DATABASE_URL"] = database_url_original
        reset_engine()


async def _correr_integration_test(motor_api, invocar_agente, AgentSpec):
    casos_reales = await motor_api.listar(area="casos", tipo="caso", tenant="criza", limit=10)
    helios = next(c for c in casos_reales if "Helios" in c["props"].get("nombre", ""))
    frentes = await motor_api.conexiones_de(helios["id"], tipo_conexion="tiene_frente", tenant="criza")
    frente_tecnico = next(f for f in frentes if "técnico" in f["props"].get("nombre", "").lower())

    spec = AgentSpec(
        nombre="biotecnologo", modulo="biotecnologo_agent.biotecnologo_agent",
        descripcion="", prop_key="biotecnologo", activo=True, run_fn=bt.run,
    )

    output = await invocar_agente(
        spec=spec,
        contract_input={
            "conocimiento": {"frente_id": frente_tecnico["id"]},
            "tarea": "Evaluar qué producto de valor se puede fabricar vía bioproceso a partir del digestato/efluente de Helios, y con qué ruta biotecnológica.",
        },
        tenant="criza",
        frente_id=frente_tecnico["id"],
        verbose=True,
    )

    assert output["análisis"]["informe_completo"]

    documentos = await motor_api.conexiones_de(
        frente_tecnico["id"], tipo_conexion="frente_produce_documento", tenant="criza"
    )
    doc_de_este_agente = [d for d in documentos if d["props"].get("agente") == "biotecnologo"]
    assert len(doc_de_este_agente) >= 1, "No se encontró ningún documento_caso del biotecnologo conectado al frente"
    assert doc_de_este_agente[-1]["props"]["contenido"] == output["análisis"]["informe_completo"]
