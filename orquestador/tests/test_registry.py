"""
Tests de orquestador/registry.py — CRIZA.

Correr unit: pytest tests/ -m "not integration"
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from orquestador.registry import AgentSpec, _cargar_agente


@pytest.mark.unit
def test_cargar_agente_guarda_el_modulo_completo():
    """Etapa 19 (cont., 2026-08-19) — modulo_obj es lo que le permite al Conductor leer TOOLS
    de un especialista (ver_herramientas_especialista) sin duplicar la lógica de carga."""
    modulo_fake = SimpleNamespace(run=lambda: None, TOOLS=[{"name": "algo"}])
    spec = AgentSpec(nombre="x", modulo="paquete.x", descripcion="", prop_key="x", activo=True)

    with patch("orquestador.registry.importlib.import_module", return_value=modulo_fake):
        resultado = _cargar_agente(spec)

    assert resultado.modulo_obj is modulo_fake
    assert resultado.modulo_obj.TOOLS == [{"name": "algo"}]
    assert resultado.run_fn is modulo_fake.run


@pytest.mark.unit
def test_cargar_agente_inactivo_no_carga_nada():
    spec = AgentSpec(nombre="x", modulo="paquete.x", descripcion="", prop_key="x", activo=False)
    resultado = _cargar_agente(spec)
    assert resultado.modulo_obj is None
    assert resultado.run_fn is None


@pytest.mark.unit
def test_cargar_agente_import_roto_deja_modulo_obj_none():
    """Mismo criterio que run_fn — un import roto no debe tumbar el registro completo."""
    spec = AgentSpec(nombre="x", modulo="paquete.no_existe", descripcion="", prop_key="x", activo=True)

    with patch("orquestador.registry.importlib.import_module", side_effect=ImportError("boom")):
        resultado = _cargar_agente(spec)

    assert resultado.modulo_obj is None
    assert resultado.run_fn is None
