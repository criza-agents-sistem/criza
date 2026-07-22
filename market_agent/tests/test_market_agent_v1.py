"""
Tests del Agente de Mercado v1 (SEB-148).

Unit: estructura de tools, buscar_corpus_cientifico con mock FTS, dispatch de search_series.
Integration: corrida real contra corpus INTA y KM.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_KM = Path(__file__).parent.parent.parent.parent / "knowledge_module"
_AGENT = Path(__file__).parent.parent
# KM primero, luego directorio del agente — agente queda en 0 (toma precedencia sobre KM/tools)
sys.path.insert(0, str(_KM))
sys.path.insert(0, str(_AGENT))

import market_agent as ma
from utils.corpus import buscar_corpus_cientifico


def _fts_response(results):
    """Helper: construye una respuesta tipo search_fuentes_externas."""
    return {
        "success": True,
        "data": {
            "query": "test",
            "total": len(results),
            "results": results,
        },
    }


def _fts_paper(titulo="Paper test", url="https://hdl.handle.net/test/1",
               abstract="Abstract de prueba", año=2023, rank=0.076):
    return {
        "id": "test-id",
        "titulo": titulo,
        "abstract": abstract,
        "fuente_url": url,
        "autores": ["García, M.", "López, R."],
        "subjects": ["biotecnología"],
        "año": año,
        "tipo": "paper",
        "rank": rank,
    }


# ── Unit: tool set ────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_no_comtrade_en_tools():
    """COMTRADE eliminado — no debe aparecer en ninguna tool del agente."""
    nombres = {t["name"] for t in ma.TOOLS}
    assert "get_import_data" not in nombres, "COMTRADE sigue en el tool set — debe eliminarse"


@pytest.mark.unit
def test_tools_requeridas_presentes():
    """Las 7 tools del gate v1 deben estar definidas."""
    nombres = {t["name"] for t in ma.TOOLS}
    esperadas = {
        "buscar_corpus_cientifico",
        "search_series",
        "get_series_values",
        "search_official_stats",
        "fetch_page_text",
        "draft_outreach_email",
        "submit_analysis",
    }
    faltantes = esperadas - nombres
    assert not faltantes, f"Tools faltantes en el agente: {faltantes}"


@pytest.mark.unit
def test_system_prompt_no_comtrade():
    """El system prompt no debe referenciar COMTRADE (sesga al agente)."""
    assert "COMTRADE" not in ma.SYSTEM_PROMPT, "System prompt referencia COMTRADE — debe eliminarse"


@pytest.mark.unit
def test_system_prompt_demand_first():
    """El system prompt debe orientar al agente hacia demanda primero."""
    sp = ma.SYSTEM_PROMPT.upper()
    assert "DEMANDA" in sp or "DEMAND" in sp, "System prompt no menciona demanda como eje principal"
    assert "BLUE OCEAN" in sp, "System prompt no menciona blue ocean"


@pytest.mark.unit
def test_submit_analysis_tiene_campos_cruces():
    """submit_analysis debe incluir cruce_1, cruce_3, cruce_4 como required."""
    submit = next(t for t in ma.TOOLS if t["name"] == "submit_analysis")
    required = submit["input_schema"].get("required", [])
    for cruce in ("cruce_1", "cruce_3", "cruce_4", "resumen_markdown"):
        assert cruce in required, f"submit_analysis no tiene '{cruce}' como required"


# ── Unit: buscar_corpus_cientifico ────────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_buscar_corpus_retorna_formato_correcto():
    """Con resultados del motor, buscar_corpus_cientifico devuelve el formato esperado."""
    mock_resultados = [
        {
            "id": "abc-123",
            "tipo": "fuente",
            "similitud": 0.87,
            "props": {
                "titulo": "Manejo de efluentes porcinos en Argentina",
                "abstract": "Este trabajo analiza el impacto ambiental del estiércol porcino...",
                "autores": "García, M.; López, R.",
                "anio": "2023",
                "url": "https://ri.conicet.gov.ar/handle/11336/12345",
                "repositorio": "CONICET",
            },
        }
    ]

    with patch("utils.corpus.motor_api.buscar", new=AsyncMock(return_value=mock_resultados)):
        result = await buscar_corpus_cientifico("estiércol porcino olor", limit=5)

    assert result["success"] is True
    assert result["total"] == 1
    assert len(result["papers"]) == 1
    paper = result["papers"][0]
    assert paper["titulo"] == "Manejo de efluentes porcinos en Argentina"
    assert paper["similitud"] == 0.87
    assert len(paper["abstract"]) <= 500
    assert "corpus_cientifico" in result["source"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_buscar_corpus_vacio_no_falla():
    """Con corpus vacío, buscar_corpus_cientifico devuelve lista vacía sin error."""
    with patch("utils.corpus.motor_api.buscar", new=AsyncMock(return_value=[])):
        result = await buscar_corpus_cientifico("tema sin resultados", limit=5)

    assert result["success"] is True
    assert result["total"] == 0
    assert result["papers"] == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_buscar_corpus_trunca_abstract():
    """Abstract largo debe truncarse a 500 chars."""
    abstract_largo = "X" * 1000
    mock_resultados = [
        {
            "id": "abc-456",
            "tipo": "fuente",
            "similitud": 0.75,
            "props": {
                "titulo": "Paper largo",
                "abstract": abstract_largo,
                "autores": "",
                "anio": "2022",
                "url": "",
                "repositorio": "CONICET",
            },
        }
    ]

    with patch("utils.corpus.motor_api.buscar", new=AsyncMock(return_value=mock_resultados)):
        result = await buscar_corpus_cientifico("test", limit=1)

    assert len(result["papers"][0]["abstract"]) == 500


# ── Unit: search_series / get_series_values dispatch ─────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_dispatch_search_series():
    """_dispatch llama search_series con los parámetros correctos."""
    mock_result = {"success": True, "series": [{"id": "abc", "descripcion": "Test"}]}
    with patch("market_agent.search_series", return_value=mock_result) as mock_fn:
        result_str = await ma._dispatch("search_series", {"query": "faena porcina", "max_results": 5})

    mock_fn.assert_called_once_with(query="faena porcina", max_results=5)
    import json
    parsed = json.loads(result_str)
    assert parsed["success"] is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_dispatch_get_series_values():
    """_dispatch llama get_series_values con series_id y last."""
    mock_result = {"success": True, "valores": [{"fecha": "2024-Q1", "valor": 1234}]}
    with patch("market_agent.get_series_values", return_value=mock_result) as mock_fn:
        result_str = await ma._dispatch("get_series_values", {"series_id": "MAGyP_FAENA_1", "last": 8})

    mock_fn.assert_called_once_with(series_id="MAGyP_FAENA_1", last=8)
    import json
    parsed = json.loads(result_str)
    assert parsed["success"] is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_dispatch_search_series_default_max_results():
    """_dispatch usa default max_results=10 si no se pasa."""
    with patch("market_agent.search_series", return_value={"success": True, "series": []}) as mock_fn:
        await ma._dispatch("search_series", {"query": "stock bovino"})

    _, kwargs = mock_fn.call_args
    assert kwargs.get("max_results", 10) == 10


# ── Unit: contrato estándar (SEB-115) ────────────────────────────────────────

@pytest.mark.unit
def test_input_contract_tiene_campos_requeridos():
    """INPUT_CONTRACT debe exponer los 5 campos del contrato estándar."""
    assert set(ma.INPUT_CONTRACT["fields"].keys()) == {"caso", "tarea", "contexto", "conocimiento", "herramientas"}
    assert ma.INPUT_CONTRACT["agent"] == "mercado"


@pytest.mark.unit
def test_output_contract_tiene_campos_requeridos():
    """OUTPUT_CONTRACT debe exponer los 5 campos del contrato estándar."""
    assert set(ma.OUTPUT_CONTRACT["fields"].keys()) == {"análisis", "nivel_confianza", "recomendaciones", "próximo_agente", "nuevo_conocimiento"}
    assert ma.OUTPUT_CONTRACT["fields"]["próximo_agente"] is None


@pytest.mark.unit
def test_derive_confidence_sin_gaps():
    assert ma._derive_confidence({"gaps_prioritarios": []}) == "alto"


@pytest.mark.unit
def test_derive_confidence_cruces_vacio_es_bajo():
    """Corrida fallida (truncada o sin submit_analysis) => cruces={} => 'bajo'.

    Distinto de test_derive_confidence_sin_gaps: ahí el agente SÍ corrió y no
    encontró gaps ('alto' legítimo). Acá nunca llegó a buscarlos. Sin la guarda,
    len(gaps)==0 hacía que una corrida fallida reportara confianza 'alto'.
    """
    assert ma._derive_confidence({}) == "bajo"


@pytest.mark.unit
def test_derive_confidence_un_gap():
    assert ma._derive_confidence({"gaps_prioritarios": ["uno"]}) == "medio"


@pytest.mark.unit
def test_derive_confidence_muchos_gaps():
    assert ma._derive_confidence({"gaps_prioritarios": ["a", "b", "c"]}) == "bajo"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_contract_formato_output():
    """run() retorna el formato estándar de contrato."""
    resumen = "# Análisis de mercado"
    cruces = {"cruce_1": {}, "cruce_3": {}, "cruce_4": {}, "gaps_prioritarios": ["gap1"]}
    lecciones = ["leccion 1"]

    with patch("market_agent.run_agent", new=AsyncMock(return_value=(resumen, cruces, lecciones))):
        result = await ma.run({"caso": "estiércol porcino olor", "conocimiento": None})

    assert "análisis" in result
    assert result["análisis"]["resumen"] == resumen
    assert result["nivel_confianza"] == "medio"
    assert result["recomendaciones"] == ["gap1"]
    assert result["próximo_agente"] is None
    assert result["nuevo_conocimiento"] == lecciones


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_contract_con_oportunidad_id():
    """run() extrae oportunidad_id de conocimiento y lo pasa a run_agent."""
    with patch("market_agent.run_agent", new=AsyncMock(return_value=("", {}, []))) as mock_fn:
        await ma.run({"caso": "test", "conocimiento": {"oportunidad_id": "uuid-123"}})

    mock_fn.assert_called_once()
    _, kwargs = mock_fn.call_args
    assert kwargs.get("oportunidad_id") == "uuid-123"
    assert kwargs.get("texto_libre") is None


# ── Integration ───────────────────────────────────────────────────────────────

# ── Unit: patrón anti-sesgo por estructura (orchestration-layer.md Decisión 6) ──

def _make_db_mock(count: int):
    """Construye mock de get_session_factory que devuelve `count` para COUNT(*)."""
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
def test_web_search_es_tool_nativo_server_side():
    """web_search debe ser el tool nativo de Anthropic, no un tool custom con dispatch propio."""
    web_search = next((t for t in ma.TOOLS if t.get("name") == "web_search"), None)
    assert web_search is not None, "web_search no está en TOOLS"
    assert web_search["type"] == "web_search_20250305"
    assert "input_schema" not in web_search, "web_search es server-side — no debe tener input_schema custom"


@pytest.mark.unit
def test_submit_analysis_campos_nuevos_required():
    """submit_analysis debe requerir sustitucion_importacion, valor_cliente y fuentes_y_cobertura."""
    submit = next(t for t in ma.TOOLS if t["name"] == "submit_analysis")
    required = submit["input_schema"].get("required", [])
    for campo in ("sustitucion_importacion", "valor_cliente", "fuentes_y_cobertura"):
        assert campo in required, f"submit_analysis no tiene '{campo}' como required"


@pytest.mark.unit
def test_valor_cliente_tiene_las_6_dimensiones():
    """valor_cliente debe forzar las 6 maneras de aportar valor del marco blue ocean."""
    submit = next(t for t in ma.TOOLS if t["name"] == "submit_analysis")
    valor_cliente = submit["input_schema"]["properties"]["valor_cliente"]
    esperadas = {"productividad", "reduccion_riesgo", "conveniencia", "simplicidad", "imagen", "cuidado_ambiente"}
    assert set(valor_cliente["required"]) == esperadas


@pytest.mark.unit
def test_system_prompt_carga_marco_blue_ocean():
    """El marco blue ocean debe estar prependido al SYSTEM_PROMPT (mismo patrón que investigacion_amplia)."""
    assert "sustitución de importación" in ma.SYSTEM_PROMPT.lower()
    assert "12" in ma.SYSTEM_PROMPT  # referencia a las 12 condiciones must


@pytest.mark.unit
def test_derive_confidence_bajo_si_sustitucion_importacion():
    """Condición 12 (sin excepción) fuerza nivel_confianza='bajo' aunque no haya gaps."""
    cruces = {
        "gaps_prioritarios": [],
        "sustitucion_importacion": {"es_sustitucion": True, "justificacion": "se importa y se consigue"},
    }
    assert ma._derive_confidence(cruces) == "bajo"


@pytest.mark.unit
def test_derive_confidence_normal_si_no_es_sustitucion():
    """Sin sustitución de importación, la lógica de gaps aplica normalmente."""
    cruces = {
        "gaps_prioritarios": [],
        "sustitucion_importacion": {"es_sustitucion": False, "justificacion": "no se importa hoy"},
    }
    assert ma._derive_confidence(cruces) == "alto"


@pytest.mark.unit
def test_merge_web_search_coverage_agrega_entrada_nueva():
    fuentes = {"fuentes_consultadas": [], "cobertura_declarada": "exhaustiva"}
    ma._merge_web_search_coverage(fuentes, calls=3, results_total=12)

    entrada = next(e for e in fuentes["fuentes_consultadas"] if e["nombre"] == "web_search")
    assert entrada["disponible"] is True
    assert entrada["unidades_procesadas"] == 12


@pytest.mark.unit
def test_merge_web_search_coverage_pisa_autoreporte_del_modelo():
    """Si el modelo autoreportó un número distinto, el conteo objetivo lo pisa."""
    fuentes = {
        "fuentes_consultadas": [{"nombre": "web_search", "disponible": True, "unidades_procesadas": 999}],
        "cobertura_declarada": "exhaustiva",
    }
    ma._merge_web_search_coverage(fuentes, calls=1, results_total=4)

    entrada = next(e for e in fuentes["fuentes_consultadas"] if e["nombre"] == "web_search")
    assert entrada["unidades_procesadas"] == 4


@pytest.mark.unit
def test_merge_web_search_coverage_sin_llamadas_marca_no_disponible():
    fuentes = {"fuentes_consultadas": [], "cobertura_declarada": "exhaustiva"}
    ma._merge_web_search_coverage(fuentes, calls=0, results_total=0)

    entrada = next(e for e in fuentes["fuentes_consultadas"] if e["nombre"] == "web_search")
    assert entrada["disponible"] is False
    assert entrada["motivo_si_no_disponible"] is not None


# ── Unit: pre-flight ─────────────────────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_corpus_cientifico_ok():
    with patch("market_agent.get_session_factory", return_value=_make_db_mock(2268)()):
        resultado = await ma._check_corpus_cientifico()
    assert resultado.ok is True
    assert resultado.conteo == 2268


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_corpus_cientifico_vacio_bloquea():
    with patch("market_agent.get_session_factory", return_value=_make_db_mock(0)()):
        resultado = await ma._check_corpus_cientifico()
    assert resultado.ok is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_datos_gob_ar_ok():
    with patch("market_agent.search_official_stats", return_value={"success": True}):
        resultado = await ma._check_datos_gob_ar()
    assert resultado.ok is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_datos_gob_ar_caido():
    with patch("market_agent.search_official_stats", return_value={"success": False, "error": "timeout"}):
        resultado = await ma._check_datos_gob_ar()
    assert resultado.ok is False
    assert "timeout" in resultado.detalle


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_web_search_sin_api_key_bloquea():
    with patch("market_agent.os.getenv", return_value=None):
        resultado = await ma._check_web_search()
    assert resultado.ok is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_agent_frena_si_preflight_bloqueante():
    """Pre-flight bloqueante debe abortar antes del loop agéntico (objective-first)."""
    from preflight import PreflightResult

    bloqueado = PreflightResult(ok=False, bloqueantes=["corpus_cientifico: 0 fichas"], advertencias=[])
    with (
        patch("market_agent.run_preflight", new=AsyncMock(return_value=bloqueado)),
        patch("market_agent.aprendizaje.ensure_area", new=AsyncMock()),
    ):
        with pytest.raises(RuntimeError, match="Pre-flight bloqueante"):
            await ma.run_agent(texto_libre="control biológico de garrapatas", verbose=False)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_buscar_corpus_contra_km_real():
    """Buscar en el corpus real de Neon — verifica que la función conecta y devuelve lista."""
    from db import reset_engine
    reset_engine()

    result = await buscar_corpus_cientifico("fitasa enzima fósforo", limit=3)

    assert result["success"] is True
    assert isinstance(result["papers"], list)
    # Puede estar vacío si no hay corpus cargado en el área corpus_cientifico — no bloquea
    for paper in result["papers"]:
        assert "titulo" in paper
        assert "similitud" in paper


# ── _bloque_instruccion (cable tarea/contexto/foco, 2026-07-22) ───────────────

@pytest.mark.unit
def test_bloque_instruccion_vacio_si_no_hay_nada():
    assert ma._bloque_instruccion(None, None, None) == ""


@pytest.mark.unit
def test_bloque_instruccion_incluye_tarea_y_contexto():
    bloque = ma._bloque_instruccion("Evaluar cruces 1, 3 y 4", "Consulta CREA", None)
    assert "Evaluar cruces 1, 3 y 4" in bloque
    assert "Consulta CREA" in bloque


@pytest.mark.unit
def test_bloque_instruccion_foco_es_la_respuesta_del_gate_humano():
    """En pipeline_sector el `caso` es {gate.candidato_elegido} — la elección del humano.

    Hasta 2026-07-22 se descartaba (había oportunidad_id, así que texto_libre quedaba
    en None) y los agentes re-analizaban el sector entero, ignorando la elección.
    """
    bloque = ma._bloque_instruccion(None, None, "inhibidores de metanogénesis")
    assert "inhibidores de metanogénesis" in bloque
    assert "FOCO DE ESTA INVOCACIÓN" in bloque
