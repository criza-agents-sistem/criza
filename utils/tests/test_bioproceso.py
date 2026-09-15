"""
Tests para criza/utils/bioproceso.py — Etapa 22 (cont., 2026-09-15).

Caso real de química conocida para verificar el número a mano: fermentación alcohólica de
glucosa (C6H12O6 -> 2 CH3CH2OH + 2 CO2) — 1 mol glucosa da 2 moles de etanol. PM glucosa =
180.16 g/mol, PM etanol = 46.07 g/mol. Rendimiento teórico clásico de la literatura: ~0.511 g
etanol / g glucosa — usado acá como referencia externa para confirmar que el cálculo es correcto,
no inventado.
"""

import sys
from pathlib import Path

import pytest

_CRIZA = Path(__file__).parent.parent.parent
if str(_CRIZA) not in sys.path:
    sys.path.insert(0, str(_CRIZA))

import utils.bioproceso as bp

PM_GLUCOSA = 180.16
PM_ETANOL = 46.07
RELACION_ETANOL_GLUCOSA = 2.0  # 2 mol etanol por mol glucosa


class TestCalcularRendimientoTeorico:

    def test_caso_real_fermentacion_alcoholica(self):
        """Verificado contra el rendimiento teórico clásico de la literatura (~0.511 g/g)."""
        result = bp.calcular_rendimiento_teorico(
            masa_sustrato_disponible_g=100.0,
            peso_molecular_sustrato=PM_GLUCOSA,
            peso_molecular_producto=PM_ETANOL,
            relacion_estequiometrica_producto_sustrato=RELACION_ETANOL_GLUCOSA,
            fuente_relacion_estequiometrica="Fermentación alcohólica, Gay-Lussac: C6H12O6 -> 2 C2H5OH + 2 CO2",
        )
        assert "error" not in result
        assert result["rendimiento_masico_pct"] == pytest.approx(51.14, rel=0.01)
        assert result["estado"].startswith("teórico")

    def test_eficiencia_de_conversion_reduce_proporcionalmente(self):
        completo = bp.calcular_rendimiento_teorico(
            masa_sustrato_disponible_g=100.0, peso_molecular_sustrato=PM_GLUCOSA,
            peso_molecular_producto=PM_ETANOL, relacion_estequiometrica_producto_sustrato=RELACION_ETANOL_GLUCOSA,
            fuente_relacion_estequiometrica="test",
        )
        con_90pct = bp.calcular_rendimiento_teorico(
            masa_sustrato_disponible_g=100.0, peso_molecular_sustrato=PM_GLUCOSA,
            peso_molecular_producto=PM_ETANOL, relacion_estequiometrica_producto_sustrato=RELACION_ETANOL_GLUCOSA,
            fuente_relacion_estequiometrica="test", eficiencia_conversion_pct=90.0,
        )
        assert con_90pct["masa_producto_con_eficiencia_g"] == pytest.approx(completo["masa_producto_con_eficiencia_g"] * 0.9)

    def test_masa_sustrato_no_positiva(self):
        result = bp.calcular_rendimiento_teorico(
            masa_sustrato_disponible_g=0, peso_molecular_sustrato=180, peso_molecular_producto=46,
            relacion_estequiometrica_producto_sustrato=2, fuente_relacion_estequiometrica="x",
        )
        assert "error" in result

    def test_peso_molecular_invalido(self):
        result = bp.calcular_rendimiento_teorico(
            masa_sustrato_disponible_g=100, peso_molecular_sustrato=-1, peso_molecular_producto=46,
            relacion_estequiometrica_producto_sustrato=2, fuente_relacion_estequiometrica="x",
        )
        assert "error" in result

    def test_relacion_estequiometrica_no_positiva(self):
        result = bp.calcular_rendimiento_teorico(
            masa_sustrato_disponible_g=100, peso_molecular_sustrato=180, peso_molecular_producto=46,
            relacion_estequiometrica_producto_sustrato=0, fuente_relacion_estequiometrica="x",
        )
        assert "error" in result

    def test_eficiencia_fuera_de_rango(self):
        result = bp.calcular_rendimiento_teorico(
            masa_sustrato_disponible_g=100, peso_molecular_sustrato=180, peso_molecular_producto=46,
            relacion_estequiometrica_producto_sustrato=2, fuente_relacion_estequiometrica="x",
            eficiencia_conversion_pct=150,
        )
        assert "error" in result

    def test_fuente_obligatoria(self):
        result = bp.calcular_rendimiento_teorico(
            masa_sustrato_disponible_g=100, peso_molecular_sustrato=180, peso_molecular_producto=46,
            relacion_estequiometrica_producto_sustrato=2, fuente_relacion_estequiometrica="   ",
        )
        assert "error" in result

    def test_fuente_se_propaga_al_resultado(self):
        result = bp.calcular_rendimiento_teorico(
            masa_sustrato_disponible_g=100, peso_molecular_sustrato=180, peso_molecular_producto=46,
            relacion_estequiometrica_producto_sustrato=2, fuente_relacion_estequiometrica="KEGG R00014",
        )
        assert result["fuente_relacion_estequiometrica"] == "KEGG R00014"
