"""
Tests del Agente Financiero (Etapa 21, 2026-09-07).

Unit: estructura de tools, SYSTEM_PROMPT (checklist anti-sesgo genérico + chequeo anti-sesgo
específico del dominio financiero pedido por Sebas), build_input_desde_frente, dispatch,
contrato run(). Integration: corrida real contra un frente real del KM.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_CRIZA = Path(__file__).parent.parent.parent
if str(_CRIZA) not in sys.path:
    sys.path.insert(0, str(_CRIZA))

from financiero_agent import financiero_agent as fa

CASO_TEST = {
    "id": "caso-uuid-1",
    "tipo": "caso",
    "props": {"nombre": "Caso de prueba", "descripcion": "Descripción de prueba."},
}
FRENTE_TEST = {
    "id": "frente-uuid-1",
    "tipo": "frente",
    "props": {"nombre": "Frente técnico", "descripcion": "Frente de prueba.", "estado": "activo"},
}
PENDIENTES_TEST = [
    {"id": "pend-1", "props": {"descripcion": "Confirmar costo del equipo X.", "estado": "abierto"}},
]
DOCUMENTOS_PRODUCIDOS_TEST = [
    {"id": "doc-biotec-1", "props": {"titulo": "Evaluación técnica", "agente": "biotecnologo"}, "creado_en": "2026-09-01T10:00:00"},
]

MODELO_MOCK = {
    "supuestos": [{"variable": "precio de venta", "valor": "USD 500/kg", "estado": "establecido", "fuente": "web_search"}],
    "capex": {"items": [{"concepto": "reactor", "monto": 100000, "moneda": "USD", "estado": "asumido"}], "total": 100000, "estado": "asumido"},
    "opex": {"items": [{"concepto": "insumos", "monto_mensual": 5000, "moneda": "USD", "estado": "asumido"}], "total_mensual": 5000, "estado": "asumido"},
    "ingresos_proyectados": {"supuesto_precio": "USD 500/kg", "supuesto_volumen": "10kg/mes", "proyeccion_anual": [{"año": 1, "monto": 60000, "moneda": "USD"}], "estado": "asumido"},
    "pyl_multianual": [{"año": 1, "ingresos": 60000, "costos": 60000, "resultado": 0}],
    "flujo_de_caja": [{"año": 0, "flujo_neto": -100000}, {"año": 1, "flujo_neto": 0}],
    "tasa_descuento": {"valor_pct": 30.0, "justificacion": "BADLAR + prima de riesgo", "fuente_bcra": "BADLAR bancos privados (id 7), 23.25% n.a.", "estado": "establecido"},
    "van": {"valor": -50000, "moneda": "USD", "estado": "asumido"},
    "tir": {"valor_pct": 5.0, "estado": "asumido"},
    "payback": {"años": 8, "estado": "asumido"},
    "riesgo_cambiario": {"aplica": True, "descripcion": "Ingresos en USD, costos locales en ARS."},
    "analisis_sensibilidad": {
        "optimista": {"van": 20000, "tir_pct": 15, "supuestos_clave": "precio +20%"},
        "base": {"van": -50000, "tir_pct": 5, "supuestos_clave": "caso base"},
        "pesimista": {"van": -150000, "tir_pct": -10, "supuestos_clave": "precio -20%, costos +15%"},
    },
    "informacion_faltante_pedida": [],
    "fuentes_y_cobertura": {"fuentes_consultadas": [], "cobertura_declarada": "muestreada"},
    "agente": "financiero",
    "informe_completo": "# Modelo financiero de prueba",
}


# ── Unit: tool set ────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_tools_requeridas_presentes():
    nombres = {t["name"] for t in fa.TOOLS if "name" in t}
    esperadas = {
        "ver_informe_especialista", "search_bcra", "get_bcra_values", "search_series",
        "get_series_values", "search_official_stats", "search_comtrade",
        "buscar_corpus_cientifico", "fetch_page_text", "pedir_informacion_faltante",
        "submit_modelo_financiero",
    }
    faltantes = esperadas - nombres
    assert not faltantes, f"Tools faltantes en el agente: {faltantes}"


@pytest.mark.unit
def test_web_search_nativo_presente():
    tipos = {t.get("type") for t in fa.TOOLS}
    assert "web_search_20250305" in tipos


@pytest.mark.unit
def test_tools_chat_excluye_submit():
    nombres = {t.get("name") for t in fa.TOOLS_CHAT}
    assert "submit_modelo_financiero" not in nombres


# ── Unit: SYSTEM_PROMPT — checklist anti-sesgo genérico ────────────────────────

@pytest.mark.unit
def test_system_prompt_sin_caso_concreto():
    """Mismo control que los otros 5 especialistas — cero menciones de Helios/biogás/
    biodigestor/Mateo/Andrés (checklist central contra el sesgo de specialist_proteins.py)."""
    sp_lower = fa.SYSTEM_PROMPT.lower()
    prohibidas = ["helios", "biogás", "biogas", "biodigestor", "mateo", "andrés", "buenas maltas"]
    for termino in prohibidas:
        assert termino not in sp_lower, f"SYSTEM_PROMPT menciona '{termino}' — viola el checklist anti-sesgo"


# ── Unit: SYSTEM_PROMPT — chequeo anti-sesgo financiero, pedido explícito de Sebas ──
# "sólo te pido último chequeo de que no tenga sesgos" — ver docs/DESIGN_GATE.md decisión D.

@pytest.mark.unit
def test_system_prompt_no_tiene_tasa_de_descuento_hardcodeada():
    """El prompt no debe sugerir un % de manual de finanzas como default — cualquier número de
    tasa mencionado en el prompt tiene que estar en un ejemplo de BCRA real, no como default
    genérico tipo '10-12%'."""
    sp = fa.SYSTEM_PROMPT
    assert "10-12%" not in sp
    assert "10%-12%" not in sp
    assert "estándar" not in sp.lower() or "manual de finanzas" in sp.lower()  # solo aparece para prohibirlo


@pytest.mark.unit
def test_system_prompt_exige_fuente_bcra_para_tasa_descuento():
    sp_lower = fa.SYSTEM_PROMPT.lower()
    assert "search_bcra" in sp_lower
    assert "tasa de descuento" in sp_lower
    assert "nunca" in sp_lower  # instrucción prohibitiva explícita presente


@pytest.mark.unit
def test_system_prompt_exige_costos_con_fuente():
    sp_lower = fa.SYSTEM_PROMPT.lower()
    assert "recordado" in sp_lower  # instrucción explícita contra el sesgo de anclaje


@pytest.mark.unit
def test_system_prompt_exige_escenario_pesimista_real():
    sp_lower = fa.SYSTEM_PROMPT.lower()
    assert "pesimista" in sp_lower
    assert "adverso" in sp_lower


@pytest.mark.unit
def test_system_prompt_exige_riesgo_cambiario():
    assert "riesgo cambiario" in fa.SYSTEM_PROMPT.lower()


@pytest.mark.unit
def test_system_prompt_comtrade_no_para_decidir_importacion():
    """COMTRADE se suma como precio de referencia (decisión E) — el prompt tiene que dejar claro
    que no es para razonar si conviene importar/sustituir, esa decisión es de Mercado."""
    sp_lower = fa.SYSTEM_PROMPT.lower()
    assert "search_comtrade" in sp_lower
    assert "sustituir importación" in sp_lower or "sustituir importaci" in sp_lower


@pytest.mark.unit
def test_system_prompt_no_decide_solo_arma():
    sp_lower = fa.SYSTEM_PROMPT.lower()
    assert "nunca concluís" in sp_lower or "nunca concluis" in sp_lower


@pytest.mark.unit
def test_submit_modelo_financiero_exige_tasa_descuento_y_riesgo_cambiario():
    submit = next(t for t in fa.TOOLS if t.get("name") == "submit_modelo_financiero")
    props = submit["input_schema"]["properties"]
    required = submit["input_schema"]["required"]
    assert "tasa_descuento" in required
    assert "fuente_bcra" in props["tasa_descuento"]["properties"]
    assert "fuente_bcra" in props["tasa_descuento"]["required"]
    assert "riesgo_cambiario" in required
    assert "analisis_sensibilidad" in required
    assert set(props["analisis_sensibilidad"]["required"]) == {"optimista", "base", "pesimista"}


# ── Unit: build_input_desde_frente ──────────────────────────────────────────────

@pytest.mark.unit
def test_build_input_incluye_caso_y_frente():
    result = fa.build_input_desde_frente(FRENTE_TEST, CASO_TEST, [])
    assert "Caso de prueba" in result
    assert "Frente técnico" in result


@pytest.mark.unit
def test_build_input_incluye_pendientes():
    result = fa.build_input_desde_frente(FRENTE_TEST, CASO_TEST, PENDIENTES_TEST)
    assert "Confirmar costo del equipo X." in result


@pytest.mark.unit
def test_build_input_incluye_documentos_producidos():
    result = fa.build_input_desde_frente(FRENTE_TEST, CASO_TEST, [], documentos_producidos=DOCUMENTOS_PRODUCIDOS_TEST)
    assert "doc-biotec-1" in result
    assert "Evaluación técnica" in result
    assert "ver_informe_especialista" in result


@pytest.mark.unit
def test_build_input_sin_documentos_producidos_no_falla():
    result = fa.build_input_desde_frente(FRENTE_TEST, CASO_TEST, [])
    assert "Caso de prueba" in result


# ── Unit: dispatch ────────────────────────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_dispatch_search_bcra():
    with patch("financiero_agent.financiero_agent.search_bcra_variables", return_value={"success": True, "variables": []}) as mock_fn:
        result = await fa._dispatch("search_bcra", {"query": "badlar"}, caso_id="caso-1", verbose=False)
    mock_fn.assert_called_once_with(query="badlar", max_results=15)
    assert '"success": true' in result.lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_dispatch_get_bcra_values():
    with patch("financiero_agent.financiero_agent.get_bcra_values", return_value={"success": True, "valores": []}) as mock_fn:
        await fa._dispatch("get_bcra_values", {"id_variable": 4}, caso_id="caso-1", verbose=False)
    mock_fn.assert_called_once_with(id_variable=4, desde=None, hasta=None, limit=30)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_dispatch_ver_informe_especialista():
    with patch("financiero_agent.financiero_agent.obtener_documento_por_id", new=AsyncMock(return_value={"contenido": "x"})) as mock_fn:
        result = await fa._dispatch("ver_informe_especialista", {"documento_id": "doc-1"}, caso_id="caso-1", verbose=False)
    mock_fn.assert_awaited_once_with("doc-1", tenant="criza")
    assert "contenido" in result


@pytest.mark.unit
@pytest.mark.asyncio
async def test_dispatch_search_comtrade():
    with patch("financiero_agent.financiero_agent.get_import_data", return_value={"success": True, "data": []}) as mock_fn:
        await fa._dispatch("search_comtrade", {"hs_code": "3105"}, caso_id="caso-1", verbose=False)
    mock_fn.assert_called_once_with(hs_code="3105", year=None, partner_country=None, max_results=20)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_dispatch_pedir_informacion_faltante_con_caso():
    with patch("financiero_agent.financiero_agent.crear_pendiente", new=AsyncMock(return_value={"success": True, "pendiente_id": "pend-1", "error": None})) as mock_fn:
        result = await fa._dispatch("pedir_informacion_faltante", {"descripcion": "falta el costo"}, caso_id="caso-1", verbose=False)
    mock_fn.assert_awaited_once_with("caso-1", "falta el costo", tenant="criza")
    assert '"pendiente_id": "pend-1"' in result


@pytest.mark.unit
@pytest.mark.asyncio
async def test_dispatch_pedir_informacion_faltante_sin_caso_no_revienta():
    """Modo consulta libre (frente_id=None en el chat) — sin caso_id, no puede crear un
    pendiente real; declara el error en vez de fallar mudo o inventar un id."""
    result = await fa._dispatch("pedir_informacion_faltante", {"descripcion": "falta el costo"}, caso_id="", verbose=False)
    assert "error" in result.lower()


# ── Unit: run() — contrato SEB-115 ───────────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_contract_requiere_frente_id():
    with pytest.raises(ValueError, match="frente_id"):
        await fa.run({"conocimiento": {}})


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_contract_no_acepta_oportunidad_id():
    with pytest.raises(ValueError, match="oportunidad_id"):
        await fa.run({"conocimiento": {"oportunidad_id": "op-1"}})


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_contract_formato_output():
    with patch(
        "financiero_agent.financiero_agent.run_agent_desde_frente",
        new=AsyncMock(return_value=("informe", MODELO_MOCK, ["lección 1"])),
    ) as mock_run:
        result = await fa.run({"conocimiento": {"frente_id": "frente-1"}})

    mock_run.assert_awaited_once()
    assert result["análisis"] == MODELO_MOCK
    assert result["nivel_confianza"] in {"alto", "medio", "bajo"}
    assert result["próximo_agente"] is None
    assert result["nuevo_conocimiento"] == ["lección 1"]


@pytest.mark.unit
def test_derive_confidence_alto_sin_a_confirmar():
    modelo = {
        "tasa_descuento": {"estado": "establecido"},
        "van": {"estado": "establecido"},
        "tir": {"estado": "establecido"},
    }
    assert fa._derive_confidence(modelo) == "alto"


@pytest.mark.unit
def test_derive_confidence_bajo_sin_modelo():
    assert fa._derive_confidence({}) == "bajo"


@pytest.mark.unit
def test_derive_confidence_bajo_con_multiples_a_confirmar():
    modelo = {
        "tasa_descuento": {"estado": "a-confirmar"},
        "van": {"estado": "a-confirmar"},
        "tir": {"estado": "establecido"},
    }
    assert fa._derive_confidence(modelo) == "bajo"


# ── Unit: run_agent_desde_frente — guardas de frente/caso ──────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_agent_desde_frente_sin_frente_levanta_valueerror():
    with patch("financiero_agent.financiero_agent.obtener_frente_con_caso", new=AsyncMock(return_value={"frente": None, "caso": None})):
        with pytest.raises(ValueError, match="no encontrado"):
            await fa.run_agent_desde_frente("frente-inexistente")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_agent_desde_frente_sin_caso_asociado_levanta_valueerror():
    with patch("financiero_agent.financiero_agent.obtener_frente_con_caso", new=AsyncMock(return_value={"frente": FRENTE_TEST, "caso": None})):
        with pytest.raises(ValueError, match="caso asociado"):
            await fa.run_agent_desde_frente("frente-1")


# ── Integration: corrida real contra el KM ──────────────────────────────────────

@pytest.mark.integration
@pytest.mark.asyncio
async def test_run_agent_desde_frente_real_contra_helios():
    """Corrida real vía la costura, sobre el 'Frente técnico' real de Helios — mismo criterio de
    verificación que los otros 5 especialistas (corrida real de punta a punta, no solo mocks)."""
    from knowledge_module.db import reset_engine
    from knowledge_module.motor import api as motor_api
    from orquestador.registry import get_registry
    from orquestador.invocador import invocar_agente

    reset_engine()
    casos_reales = await motor_api.listar(area="casos", tipo="caso", tenant="criza", limit=10)
    helios = next(c for c in casos_reales if "Helios" in c["props"].get("nombre", ""))
    frentes = await motor_api.conexiones_de(helios["id"], tipo_conexion="tiene_frente", tenant="criza")
    frente_tecnico = next(f for f in frentes if "técnico" in f["props"].get("nombre", "").lower())

    spec = get_registry()["financiero"]
    output = await invocar_agente(
        spec=spec,
        contract_input={"conocimiento": {"frente_id": frente_tecnico["id"]}},
        tenant="criza",
        frente_id=frente_tecnico["id"],
        verbose=True,
    )

    assert output["análisis"]["van"]
    assert output["análisis"]["tasa_descuento"]["fuente_bcra"]
