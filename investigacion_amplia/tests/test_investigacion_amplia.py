"""
Tests — Agente Investigación Amplia

Markers:
  unit        → sin red, sin DB (mocks)
  integration → requiere API real / DB

Correr solo unitarios:
  pytest criza/investigacion_amplia/tests/ -m unit -v
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_CRIZA = Path(__file__).parent.parent.parent
_KM = _CRIZA.parent / "knowledge_module"
sys.path.insert(0, str(_KM))
sys.path.insert(0, str(_CRIZA))

from investigacion_amplia.investigacion_amplia import (
    INPUT_CONTRACT,
    OUTPUT_CONTRACT,
    TOOLS,
    _derive_confidence,
    _fetch_full_text_fn,
    _fetch_page_text,
    _check_inta_corpus_sector,
    _check_corpus_cientifico,
    _check_openalex,
    build_input,
    run,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

CRUCE_3_FUERTE = {
    "qué_existe": "Existen varios productos registrados para manejo de olor en porcicultura.",
    "registros": {"SENASA": ["producto-X"], "patentes": []},
    "intensidad": "fuerte",
    "evidencia": [
        {
            "competidor": "AcorFarm",
            "descripción": "Aditivo para reducir compuestos azufrados en purines",
            "estado": "establecido",
            "fuente": "https://acorfarm.com",
        }
    ],
}

CRUCE_3_VACIO = {
    "qué_existe": "No se encontraron soluciones formalizadas en el espacio.",
    "intensidad": "vacío",
    "evidencia": [],
}

MAPA_3_ESTABLECIDOS = [
    {"candidato": "Olor de estiércol porcino", "señal_demanda": "...", "intensidad_competencia": "vacío", "prioridad": "alta", "estado": "establecido"},
    {"candidato": "Resistencia antibióticos", "señal_demanda": "...", "intensidad_competencia": "débil", "prioridad": "alta", "estado": "establecido"},
    {"candidato": "Bioseguridad granjas", "señal_demanda": "...", "intensidad_competencia": "fuerte", "prioridad": "media", "estado": "establecido"},
]

MAPA_1_ASUMIDO = [
    {"candidato": "Control de moscas", "señal_demanda": "...", "intensidad_competencia": "débil", "prioridad": "alta", "estado": "asumido"},
]

MAPA_3_CON_TRL = [
    {"candidato": "Olor de estiércol porcino", "señal_demanda": "...", "intensidad_competencia": "vacío", "prioridad": "alta", "estado": "establecido", "estado_de_desarrollo": "lab", "papers_fuente": ["paper-001"]},
    {"candidato": "Resistencia antibióticos", "señal_demanda": "...", "intensidad_competencia": "débil", "prioridad": "alta", "estado": "establecido", "estado_de_desarrollo": "piloto", "papers_fuente": []},
    {"candidato": "Bioseguridad granjas", "señal_demanda": "...", "intensidad_competencia": "fuerte", "prioridad": "media", "estado": "establecido", "estado_de_desarrollo": "a-confirmar", "papers_fuente": []},
]

RESULTADO_COMPLETO = {
    "cruce_3": CRUCE_3_FUERTE,
    "mapa_candidatos": MAPA_3_ESTABLECIDOS,
    "gaps_prioritarios": ["Confirmar registros SENASA"],
    "informe_completo": "## Resumen\n\nAnálisis del sector porcino...",
    "lecciones_caso": ["El sector porcino tiene competencia establecida para manejo de olor"],
}

RESULTADO_CON_TRL = {
    **RESULTADO_COMPLETO,
    "mapa_candidatos": MAPA_3_CON_TRL,
}


# ── Contrato estándar ────────────────────────────────────────────────────────

@pytest.mark.unit
def test_input_contract_tiene_campos_requeridos():
    campos = INPUT_CONTRACT["fields"]
    for campo in ["caso", "tarea", "contexto", "conocimiento", "herramientas"]:
        assert campo in campos, f"Falta campo '{campo}' en INPUT_CONTRACT"


@pytest.mark.unit
def test_output_contract_tiene_campos_requeridos():
    campos = OUTPUT_CONTRACT["fields"]
    for campo in ["análisis", "nivel_confianza", "recomendaciones", "próximo_agente", "nuevo_conocimiento"]:
        assert campo in campos, f"Falta campo '{campo}' en OUTPUT_CONTRACT"


@pytest.mark.unit
def test_output_contract_proximo_agente_puede_ser_mercado():
    assert "mercado" in OUTPUT_CONTRACT["fields"]["próximo_agente"]


@pytest.mark.unit
def test_agent_name_es_investigacion_amplia():
    assert INPUT_CONTRACT["agent"] == "investigacion_amplia"
    assert OUTPUT_CONTRACT["agent"] == "investigacion_amplia"


# ── _derive_confidence ────────────────────────────────────────────────────────

@pytest.mark.unit
def test_derive_confidence_fuerte_con_establecidos():
    resultado = {
        "cruce_3": {"intensidad": "fuerte"},
        "mapa_candidatos": MAPA_3_ESTABLECIDOS,
    }
    assert _derive_confidence(resultado) == "alto"


@pytest.mark.unit
def test_derive_confidence_vacio_con_pocos_candidatos():
    resultado = {
        "cruce_3": {"intensidad": "vacío"},
        "mapa_candidatos": MAPA_1_ASUMIDO,
    }
    # intensidad conocida + ≥1 candidato → "medio"
    assert _derive_confidence(resultado) == "medio"


@pytest.mark.unit
def test_derive_confidence_a_confirmar_sin_establecidos():
    resultado = {
        "cruce_3": {"intensidad": "a-confirmar"},
        "mapa_candidatos": [
            {"candidato": "x", "estado": "a-confirmar", "prioridad": "baja", "señal_demanda": "", "intensidad_competencia": "vacío"}
        ],
    }
    assert _derive_confidence(resultado) == "bajo"


@pytest.mark.unit
def test_derive_confidence_sin_candidatos():
    resultado = {
        "cruce_3": {"intensidad": "a-confirmar"},
        "mapa_candidatos": [],
    }
    assert _derive_confidence(resultado) == "bajo"


@pytest.mark.unit
def test_derive_confidence_debil_con_tres_establecidos():
    resultado = {
        "cruce_3": {"intensidad": "débil"},
        "mapa_candidatos": MAPA_3_ESTABLECIDOS,
    }
    assert _derive_confidence(resultado) == "alto"


# ── _derive_confidence — cobertura_texto_completo (Decisión 6) ────────────────

@pytest.mark.unit
def test_derive_confidence_capado_si_alta_prioridad_sin_texto_completo():
    """Con candidatos alta prioridad pero cero texto completo leído, no puede ser 'alto'
    aunque el resto de las señales sean fuertes — el TRL sería una adivinanza."""
    resultado = {
        "cruce_3": {"intensidad": "fuerte"},
        "mapa_candidatos": MAPA_3_ESTABLECIDOS,  # tiene candidatos alta prioridad
        "cobertura_texto_completo": {"candidatos_alta_prioridad": 2, "con_texto_completo_leido": 0},
    }
    assert _derive_confidence(resultado) != "alto"


@pytest.mark.unit
def test_derive_confidence_alto_ok_si_texto_completo_leido():
    resultado = {
        "cruce_3": {"intensidad": "fuerte"},
        "mapa_candidatos": MAPA_3_ESTABLECIDOS,
        "cobertura_texto_completo": {"candidatos_alta_prioridad": 2, "con_texto_completo_leido": 2},
    }
    assert _derive_confidence(resultado) == "alto"


@pytest.mark.unit
def test_derive_confidence_sin_cobertura_declarada_no_rompe():
    """Resultados viejos (previos a la Decisión 6) sin cobertura_texto_completo no deben tirar KeyError."""
    resultado = {"cruce_3": {"intensidad": "fuerte"}, "mapa_candidatos": MAPA_3_ESTABLECIDOS}
    assert _derive_confidence(resultado) == "alto"


# ── Schema — cobertura de texto completo obligatoria ──────────────────────────

@pytest.mark.unit
def test_submit_requiere_cobertura_texto_completo():
    submit = next(t for t in TOOLS if t["name"] == "submit_investigacion_amplia")
    assert "cobertura_texto_completo" in submit["input_schema"]["required"]


@pytest.mark.unit
def test_mapa_candidatos_requiere_estado_de_desarrollo():
    """estado_de_desarrollo debe ser required (aunque el valor sea 'a-confirmar') —
    no puede omitirse en silencio."""
    submit = next(t for t in TOOLS if t["name"] == "submit_investigacion_amplia")
    item_schema = submit["input_schema"]["properties"]["mapa_candidatos"]["items"]
    assert "estado_de_desarrollo" in item_schema["required"]


@pytest.mark.unit
def test_fetch_paper_full_text_menciona_ambas_fuentes():
    tool = next(t for t in TOOLS if t["name"] == "fetch_paper_full_text")
    assert "search_corpus_cientifico" in tool["description"]
    assert "get_sector_corpus" in tool["description"]


# ── _fetch_full_text_fn — merge documento + ficha ──────────────────────────────

@pytest.mark.unit
def test_fetch_full_text_prueba_documento_primero():
    ok_documento = {"success": True, "data": {"id": "doc-1", "texto_completo": "texto INTA"}, "error": None}
    with (
        patch("investigacion_amplia.investigacion_amplia._get_paper_full_text_fn", new=AsyncMock(return_value=ok_documento)),
        patch("investigacion_amplia.investigacion_amplia._get_ficha_full_text_fn", new=AsyncMock()) as mock_ficha,
    ):
        import asyncio
        resultado = asyncio.get_event_loop().run_until_complete(_fetch_full_text_fn("doc-1"))

    assert resultado["success"] is True
    assert resultado["data"]["texto_completo"] == "texto INTA"
    mock_ficha.assert_not_called()  # encontrado en documento, ni se intenta ficha


@pytest.mark.unit
def test_fetch_full_text_cae_a_ficha_si_no_esta_en_documento():
    """Un ID de search_corpus_cientifico (CONICET) no existe en documento — debe
    intentar ficha/corpus_cientifico como fallback, no devolver 'no encontrado'."""
    no_encontrado = {"success": False, "data": None, "error": "Documento no encontrado"}
    ok_ficha = {"success": True, "data": {"id": "ficha-1", "texto_completo": "texto CONICET"}, "error": None}
    with (
        patch("investigacion_amplia.investigacion_amplia._get_paper_full_text_fn", new=AsyncMock(return_value=no_encontrado)),
        patch("investigacion_amplia.investigacion_amplia._get_ficha_full_text_fn", new=AsyncMock(return_value=ok_ficha)) as mock_ficha,
    ):
        import asyncio
        resultado = asyncio.get_event_loop().run_until_complete(_fetch_full_text_fn("ficha-1"))

    assert resultado["success"] is True
    assert resultado["data"]["texto_completo"] == "texto CONICET"
    mock_ficha.assert_called_once()


@pytest.mark.unit
def test_fetch_full_text_ninguna_fuente_lo_tiene():
    no_encontrado_doc = {"success": False, "data": None, "error": "Documento no encontrado"}
    no_encontrado_ficha = {"success": False, "data": None, "error": "Ficha no encontrada en corpus_cientifico"}
    with (
        patch("investigacion_amplia.investigacion_amplia._get_paper_full_text_fn", new=AsyncMock(return_value=no_encontrado_doc)),
        patch("investigacion_amplia.investigacion_amplia._get_ficha_full_text_fn", new=AsyncMock(return_value=no_encontrado_ficha)),
    ):
        import asyncio
        resultado = asyncio.get_event_loop().run_until_complete(_fetch_full_text_fn("id-inexistente"))

    assert resultado["success"] is False


# ── build_input ───────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_build_input_texto_libre():
    texto = build_input("porcicultura", None)
    assert "porcicultura" in texto
    # v2.0: el hint menciona get_sector_corpus (ya no lista el nombre del tool de submit)
    assert "get_sector_corpus" in texto


@pytest.mark.unit
def test_build_input_con_oportunidad_dict():
    oportunidad = {
        "nombre": "Sector Porcino",
        "props": {"descripcion": "Crianza de cerdos en Argentina."},
    }
    texto = build_input("porcicultura", oportunidad)
    assert "Sector Porcino" in texto
    assert "Crianza de cerdos" in texto


# ── _fetch_page_text ──────────────────────────────────────────────────────────

@pytest.mark.unit
def test_fetch_page_text_url_invalida():
    result = _fetch_page_text("http://localhost:9999/no-existe")
    assert result["success"] is False
    assert "error" in result


# ── run() — contrato estándar ─────────────────────────────────────────────────

@pytest.mark.unit
def test_run_contract_formato_output():
    mock_informe = "# Análisis\n\nSector porcino..."

    with (
        patch("investigacion_amplia.investigacion_amplia.run_agent", new_callable=AsyncMock) as mock_agent,
    ):
        mock_agent.return_value = (mock_informe, RESULTADO_COMPLETO, ["lección 1"])

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            run({"caso": "porcicultura"})
        )

    assert "análisis" in result
    assert "nivel_confianza" in result
    assert "recomendaciones" in result
    assert "próximo_agente" in result
    assert "nuevo_conocimiento" in result

    assert result["nivel_confianza"] in ("alto", "medio", "bajo")
    assert isinstance(result["recomendaciones"], list)
    assert result["nuevo_conocimiento"] == ["lección 1"]


@pytest.mark.unit
def test_run_contract_sin_caso_ni_oportunidad_falla():
    import asyncio

    with pytest.raises(ValueError, match="requiere"):
        asyncio.get_event_loop().run_until_complete(run({}))


@pytest.mark.unit
def test_run_contract_proximo_agente_mercado_si_hay_alta_prio():
    with patch("investigacion_amplia.investigacion_amplia.run_agent", new_callable=AsyncMock) as mock_agent:
        mock_agent.return_value = ("informe", RESULTADO_COMPLETO, [])

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            run({"caso": "porcicultura"})
        )

    assert result["próximo_agente"] == "mercado"


@pytest.mark.unit
def test_run_contract_proximo_agente_none_si_no_hay_alta_prio():
    resultado_sin_alta = {
        **RESULTADO_COMPLETO,
        "mapa_candidatos": [
            {"candidato": "x", "señal_demanda": "...", "intensidad_competencia": "fuerte", "prioridad": "baja", "estado": "asumido"}
        ],
    }
    with patch("investigacion_amplia.investigacion_amplia.run_agent", new_callable=AsyncMock) as mock_agent:
        mock_agent.return_value = ("informe", resultado_sin_alta, [])

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            run({"caso": "sector sin prioridad alta"})
        )

    assert result["próximo_agente"] is None


@pytest.mark.unit
def test_run_contract_recomendaciones_ordenadas_por_prioridad():
    mapa_mixto = [
        {"candidato": "C", "señal_demanda": "...", "intensidad_competencia": "vacío", "prioridad": "baja", "estado": "establecido"},
        {"candidato": "A", "señal_demanda": "...", "intensidad_competencia": "vacío", "prioridad": "alta", "estado": "establecido"},
        {"candidato": "B", "señal_demanda": "...", "intensidad_competencia": "débil", "prioridad": "media", "estado": "establecido"},
    ]
    resultado = {**RESULTADO_COMPLETO, "mapa_candidatos": mapa_mixto}

    with patch("investigacion_amplia.investigacion_amplia.run_agent", new_callable=AsyncMock) as mock_agent:
        mock_agent.return_value = ("informe", resultado, [])

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            run({"caso": "sector mixto"})
        )

    prioridades = [c.get("prioridad") for c in result["recomendaciones"]]
    assert prioridades[0] == "alta"
    assert prioridades[-1] == "baja"


@pytest.mark.unit
def test_run_contract_con_oportunidad_id():
    with patch("investigacion_amplia.investigacion_amplia.run_agent", new_callable=AsyncMock) as mock_agent:
        mock_agent.return_value = ("informe", RESULTADO_COMPLETO, [])

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            run({
                "caso": "porcicultura",
                "conocimiento": {"oportunidad_id": "uuid-123"},
            })
        )

    # Verifica que se pasó oportunidad_id al run_agent
    call_kwargs = mock_agent.call_args
    assert call_kwargs.kwargs.get("oportunidad_id") == "uuid-123"


# ── v2.0 — Contrato ──────────────────────────────────────────────────────────

@pytest.mark.unit
def test_contract_version_es_2_1():
    assert INPUT_CONTRACT["version"] == "2.1"
    assert OUTPUT_CONTRACT["version"] == "2.1"


@pytest.mark.unit
def test_submit_investigacion_amplia_requiere_fuentes_y_cobertura():
    """Detectado por el auditor (2026-07-02): faltaba el campo estándar de
    orchestration-layer.md Decisión 6 — cobertura_texto_completo no lo reemplaza,
    mide otra cosa (lectura de texto completo, no disponibilidad de fuente)."""
    tool = next(t for t in TOOLS if t["name"] == "submit_investigacion_amplia")
    required = tool["input_schema"]["required"]
    assert "fuentes_y_cobertura" in required


@pytest.mark.unit
def test_input_contract_herramientas_v2():
    tools = INPUT_CONTRACT["fields"]["herramientas"]
    for esperada in ["get_sector_corpus", "search_corpus_cientifico", "fetch_paper_full_text"]:
        assert esperada in tools, f"Falta '{esperada}' en herramientas v2.0"
    # La tool de v1.0 ya no debe estar
    assert "search_corpus_inta" not in tools


# ── v2.1 — pre-flight (migrado a knowledge_module/preflight.py genérico) ──────

def _make_db_mock(conicet_count: int):
    """Construye mock de get_session_factory que devuelve conicet_count para COUNT(*)."""
    mock_result = MagicMock()
    mock_result.scalar.return_value = conicet_count

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    mock_factory_instance = MagicMock(return_value=mock_cm)
    return MagicMock(return_value=mock_factory_instance)


# ── v2.0 — estado_de_desarrollo ───────────────────────────────────────────────

@pytest.mark.unit
def test_run_pasa_estado_de_desarrollo_en_recomendaciones():
    """estado_de_desarrollo del mapa_candidatos llega a recomendaciones sin modificarse."""
    with patch("investigacion_amplia.investigacion_amplia.run_agent", new_callable=AsyncMock) as mock_agent:
        mock_agent.return_value = ("informe", RESULTADO_CON_TRL, [])

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            run({"caso": "porcicultura"})
        )

    recomendaciones = result["recomendaciones"]
    altas = [r for r in recomendaciones if r.get("prioridad") == "alta"]
    assert altas, "Debe haber candidatos de alta prioridad"
    for c in altas:
        assert "estado_de_desarrollo" in c, "estado_de_desarrollo debe estar en recomendaciones"
    assert altas[0]["estado_de_desarrollo"] in ("idea", "lab", "piloto", "comercial", "a-confirmar")


# ── v2.1 — pre-flight (migrado a knowledge_module/preflight.py genérico) ──────
# Nota: estos tests van DESPUÉS de los que usan asyncio.get_event_loop().run_until_complete()
# a propósito — pytest-asyncio gestiona su propio event loop y cerrarlo antes de un test legacy
# rompe 'get_event_loop()' en ese test (RuntimeError: no current event loop). Mismo orden que
# ya se estableció para market_agent/evidence_generalista en esta sesión.

@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_inta_corpus_sector_ok():
    inta_ok = {"success": True, "data": {"total": 50, "docs_con_texto_completo": 30, "documentos": []}}
    with patch("investigacion_amplia.investigacion_amplia._get_sector_corpus_fn", new_callable=AsyncMock, return_value=inta_ok):
        resultado = await _check_inta_corpus_sector(["bovinos", "cattle"])
    assert resultado.ok is True
    assert resultado.conteo == 50


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_inta_corpus_sector_vacio_bloquea():
    inta_vacio = {"success": True, "data": {"total": 0, "docs_con_texto_completo": 0, "documentos": []}}
    with patch("investigacion_amplia.investigacion_amplia._get_sector_corpus_fn", new_callable=AsyncMock, return_value=inta_vacio):
        resultado = await _check_inta_corpus_sector(["termino-inventado"])
    assert resultado.ok is False
    assert "0 documentos" in resultado.detalle


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_corpus_cientifico_insuficiente_bloquea():
    with patch("investigacion_amplia.investigacion_amplia.get_session_factory", return_value=_make_db_mock(87)()):
        resultado = await _check_corpus_cientifico()
    assert resultado.ok is False
    assert resultado.conteo == 87
    assert "87" in resultado.detalle


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_corpus_cientifico_suficiente_ok():
    with patch("investigacion_amplia.investigacion_amplia.get_session_factory", return_value=_make_db_mock(150)()):
        resultado = await _check_corpus_cientifico()
    assert resultado.ok is True
    assert resultado.conteo == 150


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_openalex_caido_es_advertencia_no_bloqueante():
    """OpenAlex caído → check falla, pero run_preflight lo trata como advertencia (no bloqueante)."""
    with patch("investigacion_amplia.investigacion_amplia._search_literature_fn", side_effect=Exception("503 Service Unavailable")):
        resultado = await _check_openalex()
    assert resultado.ok is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_preflight_ok_cuando_inta_y_conicet_suficientes():
    """Integración de los 3 checks vía run_preflight — reproduce el comportamiento agregado
    que antes tenía _preflight_check (migrado a preflight.py genérico, 2026-07-02)."""
    from preflight import FuenteCheck, run_preflight

    inta_ok = {"success": True, "data": {"total": 341, "docs_con_texto_completo": 198, "documentos": []}}
    with (
        patch("investigacion_amplia.investigacion_amplia._get_sector_corpus_fn", new_callable=AsyncMock, return_value=inta_ok),
        patch("investigacion_amplia.investigacion_amplia.get_session_factory", return_value=_make_db_mock(150)()),
        patch("investigacion_amplia.investigacion_amplia._search_literature_fn", return_value={"results": []}),
    ):
        resultado = await run_preflight([
            FuenteCheck("INTA corpus", bloqueante=True, check_fn=lambda: _check_inta_corpus_sector(["bovinos"])),
            FuenteCheck("corpus_cientifico (CONICET+INTA)", bloqueante=True, check_fn=_check_corpus_cientifico),
            FuenteCheck("OpenAlex", bloqueante=False, check_fn=_check_openalex),
        ])
    assert resultado.ok is True
    assert resultado.bloqueantes == []


# ── Integration ───────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_fetch_page_text_real():
    """Smoke test: descarga una página real."""
    result = _fetch_page_text("https://www.argentina.gob.ar/senasa")
    assert result["success"] is True
    assert len(result["text"]) > 100
