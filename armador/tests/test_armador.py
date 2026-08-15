"""
Tests del Armador del Expediente (SEB-145).

Unit: estructura de tools, build_input, manejo de cruce 2 ausente, campos required.
Integration: corrida real contra KM con oportunidad real.
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

_AGENT = Path(__file__).parent.parent
sys.path.insert(0, str(_AGENT))

import armador as arm
from armador import build_input, TOOLS, SYSTEM_PROMPT


# ── Fixtures ──────────────────────────────────────────────────────────────────

OPORTUNIDAD_CON_MERCADO = {
    "nombre": "Fitasa nutrición animal",
    "descripcion": "Producción local de fitasa para porcinos y aves",
    "props": {
        "mercado": {
            "cruce_1": {"dolor": "Baja digestibilidad fósforo", "estado": "establecido"},
            "cruce_3": {"que_existe": "Novozymes importado", "estado": "establecido"},
            "cruce_4": {"encuadre_regulatorio": "SENASA aditivo zootécnico", "estado": "establecido"},
            "bloque_6_anclas": {"inversion_ancla": {"valor": "USD 200K–500K", "estado": "asumido"}},
            "agente": "mercado",
        }
    },
}

OPORTUNIDAD_SIN_MERCADO = {
    "nombre": "Oportunidad sin análisis previo",
    "descripcion": "Descripción de prueba",
    "props": {},
}

OPORTUNIDAD_CON_EVIDENCIA = {
    "nombre": "Oportunidad con ambos agentes",
    "descripcion": "Descripción",
    "props": {
        "mercado": {"cruce_1": {"dolor": "Test", "estado": "establecido"}},
        "evidencia": {"cruce_2": {"solucion": "Enzima recombinante", "estado": "asumido"}},
    },
}


# ── Unit: tool set ────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_una_sola_tool():
    """El Armador tiene exactamente una tool: submit_expediente."""
    assert len(TOOLS) == 1
    assert TOOLS[0]["name"] == "submit_expediente"


@pytest.mark.unit
def test_submit_expediente_campos_requeridos():
    """submit_expediente tiene los 6 bloques + trazabilidad + resumen como required."""
    required = TOOLS[0]["input_schema"].get("required", [])
    esperados = {"bloque_1", "bloque_2", "bloque_3", "bloque_4", "bloque_5", "bloque_6",
                 "trazabilidad", "resumen_markdown"}
    faltantes = esperados - set(required)
    assert not faltantes, f"Campos faltantes en submit_expediente: {faltantes}"


@pytest.mark.unit
def test_submit_expediente_bloque2_tiene_4_cruces():
    """bloque_2 tiene los 4 cruces como required."""
    bloque_2 = TOOLS[0]["input_schema"]["properties"]["bloque_2"]
    required = bloque_2.get("required", [])
    for cruce in ("cruce_1", "cruce_2", "cruce_3", "cruce_4"):
        assert cruce in required, f"bloque_2 no tiene '{cruce}' como required"


@pytest.mark.unit
def test_bloque4_niveles_validos():
    """bloque_4.nivel tiene exactamente los 3 niveles definidos en la spec."""
    nivel_schema = TOOLS[0]["input_schema"]["properties"]["bloque_4"]["properties"]["nivel"]
    assert set(nivel_schema["enum"]) == {
        "hipotesis_de_screening", "parcialmente_validado", "listo_para_decision"
    }


# ── Unit: system prompt ───────────────────────────────────────────────────────

@pytest.mark.unit
def test_system_prompt_no_investiga():
    """El system prompt debe decir explícitamente que el Armador no investiga."""
    sp = SYSTEM_PROMPT.upper()
    assert "NO INVESTIGÁS" in sp or "NO INVESTIGAS" in sp or "NO INVESTIGA" in sp


@pytest.mark.unit
def test_system_prompt_veracidad():
    """El system prompt menciona la regla de veracidad (establecido/asumido/a-confirmar)."""
    assert "establecido" in SYSTEM_PROMPT.lower()
    assert "a-confirmar" in SYSTEM_PROMPT.lower()


@pytest.mark.unit
def test_system_prompt_sin_timelines():
    """El system prompt previene que el modelo genere timelines propios."""
    assert "NUNCA" in SYSTEM_PROMPT and "timeline" in SYSTEM_PROMPT.lower()


# ── Unit: build_input ─────────────────────────────────────────────────────────

@pytest.mark.unit
def test_build_input_con_datos_mercado():
    """Con datos de mercado, el input los incluye en el mensaje."""
    result = build_input("id-123", OPORTUNIDAD_CON_MERCADO)
    assert "cruce_1" in result
    assert "Fitasa" in result
    assert "id-123" in result


@pytest.mark.unit
def test_build_input_sin_mercado():
    """Sin datos de mercado, el input declara la ausencia explícitamente."""
    result = build_input("id-456", OPORTUNIDAD_SIN_MERCADO)
    assert "NO DISPONIBLE" in result
    assert "Market Agent" in result


@pytest.mark.unit
def test_build_input_sin_evidencia():
    """Sin datos de evidencia, el input menciona SEB-149 como pendiente."""
    result = build_input("id-789", OPORTUNIDAD_CON_MERCADO)
    assert "SEB-149" in result or "Evidence Agent" in result


@pytest.mark.unit
def test_build_input_con_evidencia():
    """Con datos de evidencia, el input los incluye."""
    result = build_input("id-abc", OPORTUNIDAD_CON_EVIDENCIA)
    assert "Enzima recombinante" in result


@pytest.mark.unit
def test_build_input_props_adicionales():
    """Props adicionales (ni mercado ni evidencia) se incluyen como contexto."""
    oportunidad = {
        "nombre": "Test",
        "descripcion": "Desc",
        "props": {
            "mercado": {},
            "sector": "biotech",
            "etapa": "screening",
        },
    }
    result = build_input("id-xyz", oportunidad)
    assert "sector" in result or "etapa" in result


@pytest.mark.unit
def test_build_input_informe_completo_como_texto():
    """Si props.mercado tiene informe_completo, se muestra como texto plano (no dentro del JSON)."""
    oportunidad = {
        "nombre": "Test Fitasa",
        "descripcion": "Prueba",
        "props": {
            "mercado": {
                "cruce_1": {"dolor": "Test", "estado": "establecido"},
                "informe_completo": "## Análisis de mercado\n\nEste es el informe completo del agente.",
            }
        },
    }
    result = build_input("id-inf", oportunidad)
    # El informe debe aparecer como texto, no encapsulado en JSON
    assert "## Análisis de mercado" in result
    assert "informe_completo" not in result  # la clave no debe aparecer como JSON key visible


@pytest.mark.unit
def test_build_input_nombre_desde_props():
    """Si nombre/descripcion no están al top level (formato KM real), los lee de props."""
    oportunidad_km_real = {
        "id": "uuid-1234",
        "tipo": "oportunidad",
        "props": {
            "nombre": "Fitasa desde KM",
            "descripcion": "Descripción desde props",
            "mercado": {"cruce_1": {"dolor": "Test", "estado": "establecido"}},
        },
    }
    result = build_input("uuid-1234", oportunidad_km_real)
    assert "Fitasa desde KM" in result
    assert "uuid-1234" in result


# ── Unit: run_agent (mock) ────────────────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_agent_captura_submit_expediente():
    """run_agent debe capturar la llamada a submit_expediente y devolverla."""
    expediente_mock = {
        "bloque_1": {"tesis": "Tesis test", "puerta_de_entrada": "sector", "oportunidad_nombre": "Test"},
        "bloque_2": {"cruce_1": {}, "cruce_2": {}, "cruce_3": {}, "cruce_4": {}},
        "bloque_3": {"establecidos": [], "asumidos": [], "a_confirmar": [], "indice_confianza": "bajo"},
        "bloque_4": {"nivel": "hipotesis_de_screening", "justificacion": "Test"},
        "bloque_5": {"gaps": []},
        "bloque_6": {"inversion": {}, "tiempo_a_mercado": {}, "capacidades": {}, "regulatorio": {}},
        "trazabilidad": {"agentes_que_contribuyeron": ["mercado"], "fecha": "2026-06-16"},
        "resumen_markdown": "# Expediente test\n\nResumen de prueba.",
        "lecciones_caso": ["Lección de prueba"],
    }

    mock_tool_use = type("ToolUseBlock", (), {
        "type": "tool_use",
        "name": "submit_expediente",
        "id": "tool_abc",
        "input": expediente_mock,
    })()

    mock_response = type("Response", (), {
        "stop_reason": "tool_use",
        "content": [mock_tool_use],
        "usage": type("Usage", (), {"input_tokens": 100, "output_tokens": 50})(),
    })()

    # Segunda respuesta: end_turn (no se alcanza porque el loop ya rompió)
    with patch("armador._ai_complete_streaming", new=AsyncMock(return_value=mock_response)), \
         patch("armador.aprendizaje.bloque_lecciones_para_prompt", new=AsyncMock(return_value="")):

        resumen, expediente, lecciones = await arm.run_agent(
            oportunidad_id=None,
            oportunidad_dict=OPORTUNIDAD_CON_MERCADO,
            verbose=False,
        )

    assert resumen == "# Expediente test\n\nResumen de prueba."
    assert expediente["bloque_1"]["tesis"] == "Tesis test"
    assert lecciones == ["Lección de prueba"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_agent_sin_submit_devuelve_texto():
    """Si el agente no llama submit_expediente y da end_turn, devuelve el texto raw."""
    mock_text_block = type("TextBlock", (), {
        "type": "text",
        "text": "Respuesta sin tool",
    })()

    mock_response = type("Response", (), {
        "stop_reason": "end_turn",
        "content": [mock_text_block],
        "usage": type("Usage", (), {"input_tokens": 50, "output_tokens": 20})(),
    })()

    with patch("armador._ai_complete_streaming", new=AsyncMock(return_value=mock_response)), \
         patch("armador.aprendizaje.bloque_lecciones_para_prompt", new=AsyncMock(return_value="")):

        resumen, expediente, lecciones = await arm.run_agent(
            oportunidad_id=None,
            oportunidad_dict=OPORTUNIDAD_CON_MERCADO,
            verbose=False,
        )

    assert "Respuesta sin tool" in resumen
    assert expediente == {}
    assert lecciones == []


# ── Unit: patrón anti-sesgo por estructura (orchestration-layer.md Decisión 6) ──

@pytest.mark.unit
def test_validar_cobertura_bloquea_sin_mercado():
    resultado = arm._validar_cobertura_upstream({})
    assert resultado.ok is False
    assert any("mercado" in b for b in resultado.bloqueantes)


@pytest.mark.unit
def test_validar_cobertura_ok_con_mercado_y_evidencia():
    props = {
        "mercado": {"fuentes_y_cobertura": {"cobertura_declarada": "exhaustiva"}},
        "evidencia": {"fuentes_y_cobertura": {"cobertura_declarada": "exhaustiva"}},
    }
    resultado = arm._validar_cobertura_upstream(props)
    assert resultado.ok is True
    assert resultado.bloqueantes == []
    assert resultado.advertencias == []


@pytest.mark.unit
def test_validar_cobertura_advertencia_sin_evidencia():
    """Sin evidencia (SEB-149 no corrió aún) → advertencia, no bloqueante."""
    props = {"mercado": {"fuentes_y_cobertura": {"cobertura_declarada": "exhaustiva"}}}
    resultado = arm._validar_cobertura_upstream(props)
    assert resultado.ok is True
    assert any("evidencia" in a for a in resultado.advertencias)


@pytest.mark.unit
def test_validar_cobertura_advertencia_cobertura_parcial():
    props = {"mercado": {"fuentes_y_cobertura": {"cobertura_declarada": "parcial-por-falla-de-fuente"}}}
    resultado = arm._validar_cobertura_upstream(props)
    assert resultado.ok is True
    assert any("mercado" in a and "parcial" in a for a in resultado.advertencias)


@pytest.mark.unit
def test_derive_cobertura_global_alto_cuando_ambas_exhaustivas():
    props = {
        "mercado": {"fuentes_y_cobertura": {"cobertura_declarada": "exhaustiva"}},
        "evidencia": {"fuentes_y_cobertura": {"cobertura_declarada": "exhaustiva"}},
    }
    assert arm._derive_cobertura_global(props) == "alto"


@pytest.mark.unit
def test_derive_cobertura_global_bajo_sin_datos():
    assert arm._derive_cobertura_global({}) == "bajo"


@pytest.mark.unit
def test_derive_cobertura_global_medio_mezcla():
    props = {
        "mercado": {"fuentes_y_cobertura": {"cobertura_declarada": "exhaustiva"}},
        "evidencia": {"fuentes_y_cobertura": {"cobertura_declarada": "parcial-por-falla-de-fuente"}},
    }
    assert arm._derive_cobertura_global(props) == "medio"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_agent_frena_sin_mercado():
    """Sin mercado, el armador no debe ni siquiera llamar al modelo (objective-first)."""
    with patch("armador._ai_complete_streaming", new=AsyncMock()) as mock_complete:
        with pytest.raises(RuntimeError, match="Validación de cobertura bloqueante"):
            await arm.run_agent(
                oportunidad_id=None,
                oportunidad_dict=OPORTUNIDAD_SIN_MERCADO,
                verbose=False,
            )
    mock_complete.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_agent_inyecta_cobertura_global_en_bloque_3():
    """El expediente final debe traer bloque_3.cobertura_global calculado, no autoreportado."""
    props_con_cobertura = dict(OPORTUNIDAD_CON_MERCADO["props"])
    props_con_cobertura["mercado"] = {
        **props_con_cobertura["mercado"],
        "fuentes_y_cobertura": {"cobertura_declarada": "exhaustiva"},
    }
    oportunidad = {**OPORTUNIDAD_CON_MERCADO, "props": props_con_cobertura}

    submit_input = {
        "bloque_1": {"tesis": "t", "puerta_de_entrada": "sector", "oportunidad_nombre": "n"},
        "bloque_2": {"cruce_1": {}, "cruce_2": {}, "cruce_3": {}, "cruce_4": {}},
        "bloque_3": {"establecidos": [], "asumidos": [], "a_confirmar": [], "indice_confianza": "medio"},
        "bloque_4": {"nivel": "hipotesis_de_screening", "justificacion": "j"},
        "bloque_5": {"gaps": []},
        "bloque_6": {"inversion": {}, "tiempo_a_mercado": {}, "capacidades": {}, "regulatorio": {}},
        "trazabilidad": {"agentes_que_contribuyeron": ["mercado"], "fecha": "2026-07-02"},
        "resumen_markdown": "# Expediente",
    }
    mock_tool_use = type("ToolUseBlock", (), {
        "type": "tool_use", "name": "submit_expediente", "id": "tool_01", "input": submit_input,
    })()
    mock_response = type("Response", (), {
        "stop_reason": "tool_use", "content": [mock_tool_use],
        "usage": type("Usage", (), {"input_tokens": 10, "output_tokens": 10})(),
    })()

    with patch("armador._ai_complete_streaming", new=AsyncMock(return_value=mock_response)), \
         patch("armador.aprendizaje.bloque_lecciones_para_prompt", new=AsyncMock(return_value="")):

        _, expediente, _ = await arm.run_agent(
            oportunidad_id=None, oportunidad_dict=oportunidad, verbose=False,
        )

    assert expediente["bloque_3"]["cobertura_global"] == "alto"  # solo mercado presente, cobertura exhaustiva


@pytest.mark.integration
@pytest.mark.asyncio
async def test_run_agent_caso_real():
    """Corrida real del Armador con caso fitasa (sin KM, usando oportunidad_dict)."""
    from run import CASO_FITASA
    from knowledge_module.db import reset_engine
    reset_engine()

    resumen, expediente, lecciones = await arm.run_agent(
        oportunidad_id=None,
        oportunidad_dict=CASO_FITASA,
        verbose=True,
    )

    assert isinstance(resumen, str) and len(resumen) > 50
    if expediente:
        assert "bloque_1" in expediente
        assert "bloque_2" in expediente
        assert "bloque_3" in expediente
        assert "bloque_4" in expediente
        assert "bloque_5" in expediente
        assert "bloque_6" in expediente


# ── _derive_nivel_confianza (2026-07-22) ──────────────────────────────────────

@pytest.mark.unit
def test_derive_nivel_confianza_vacio_es_bajo():
    """Sin bloque_3 (o vacío) no hay nada que contar — 'bajo', no 'alto'.

    Es el caso exacto del bug: antes `run()` devolvía "alto if expediente else bajo",
    así que un expediente con bloque_3 vacío igual daba "alto".
    """
    assert arm._derive_nivel_confianza({}) == "bajo"


@pytest.mark.unit
def test_derive_nivel_confianza_mayoria_establecidos_es_alto():
    bloque_3 = {
        "establecidos": [{"dato": "a"}, {"dato": "b"}, {"dato": "c"}],
        "asumidos": [{"dato": "d"}],
        "a_confirmar": [],
    }
    assert arm._derive_nivel_confianza(bloque_3) == "alto"


@pytest.mark.unit
def test_derive_nivel_confianza_mayoria_a_confirmar_es_bajo():
    bloque_3 = {
        "establecidos": [{"dato": "a"}],
        "asumidos": [],
        "a_confirmar": [{"dato": "b"}, {"dato": "c"}],
    }
    assert arm._derive_nivel_confianza(bloque_3) == "bajo"


@pytest.mark.unit
def test_derive_nivel_confianza_mezcla_pareja_es_medio():
    bloque_3 = {
        "establecidos": [{"dato": "a"}],
        "asumidos": [{"dato": "b"}],
        "a_confirmar": [{"dato": "c"}],
    }
    assert arm._derive_nivel_confianza(bloque_3) == "medio"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_nivel_confianza_no_es_solo_si_hubo_expediente():
    """Caso testigo de la corrida real de metano: expediente presente con bloque_3
    mayormente a-confirmar debía dar 'bajo', no 'alto' por el mero hecho de existir."""
    submit_input = {
        "bloque_3": {
            "establecidos": [],
            "asumidos": [{"dato": "x", "peso": "medio"}],
            "a_confirmar": [
                {"dato": "y", "donde_confirmar": "z", "impacto_en_decision": "alto"},
                {"dato": "w", "donde_confirmar": "z", "impacto_en_decision": "alto"},
            ],
            "indice_confianza": "alto",  # autoreporte del modelo — no debe usarse tal cual
        },
        "resumen_markdown": "# Expediente",
    }
    mock_tool_use = type("ToolUseBlock", (), {
        "type": "tool_use", "name": "submit_expediente", "id": "tool_01", "input": submit_input,
    })()
    mock_response = type("Response", (), {
        "stop_reason": "tool_use", "content": [mock_tool_use],
        "usage": type("Usage", (), {"input_tokens": 10, "output_tokens": 10})(),
    })()

    with patch("armador._ai_complete_streaming", new=AsyncMock(return_value=mock_response)), \
         patch("armador.aprendizaje.bloque_lecciones_para_prompt", new=AsyncMock(return_value="")), \
         patch("armador.motor_api.obtener", new=AsyncMock(return_value=OPORTUNIDAD_CON_MERCADO)), \
         patch("armador.motor_api.actualizar_props", new=AsyncMock(return_value={"success": True})):

        resultado = await arm.run(
            contract_input={"conocimiento": {"oportunidad_id": "test-oid"}},
            verbose=False,
        )

    assert resultado["nivel_confianza"] == "bajo"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_run_agent_system_prompt_con_cache_control():
    """Prompt caching (2026-07-22). El SYSTEM_PROMPT del armador es 100% estático
    (sin lecciones inyectadas ahí) — cachea dentro Y entre corridas."""
    submit_input = {
        "bloque_3": {"establecidos": [], "asumidos": [], "a_confirmar": [], "indice_confianza": "bajo"},
        "resumen_markdown": "# Expediente",
    }
    mock_tool_use = type("ToolUseBlock", (), {
        "type": "tool_use", "name": "submit_expediente", "id": "tool_cache", "input": submit_input,
    })()
    mock_response = type("Response", (), {
        "stop_reason": "tool_use", "content": [mock_tool_use],
        "usage": type("Usage", (), {"input_tokens": 10, "output_tokens": 10})(),
    })()

    mock_complete = AsyncMock(return_value=mock_response)
    with patch("armador._ai_complete_streaming", new=mock_complete), \
         patch("armador.aprendizaje.bloque_lecciones_para_prompt", new=AsyncMock(return_value="")):

        await arm.run_agent(
            oportunidad_id=None, oportunidad_dict=OPORTUNIDAD_CON_MERCADO, verbose=False,
        )

    _, kwargs = mock_complete.call_args
    system = kwargs["system"]
    assert isinstance(system, list)
    assert system[0]["cache_control"] == {"type": "ephemeral"}
    assert system[0]["text"] == arm.SYSTEM_PROMPT
