"""
Tests para criza/utils/estadistica.py — Etapa 22 (cont., 2026-09-14).

Series sintéticas de propiedad conocida (no reales) para verificar que cada función detecta
exactamente lo que se espera — mismo criterio de rigor que el caso real de Helios que motivó
este módulo (ver docstring de estadistica.py).
"""

import sys
from pathlib import Path
from datetime import date, timedelta

import numpy as np
import pytest

_CRIZA = Path(__file__).parent.parent.parent
if str(_CRIZA) not in sys.path:
    sys.path.insert(0, str(_CRIZA))

import utils.estadistica as est


def _serie(valores: list[float], desde: date = date(2023, 1, 1), paso_dias: int = 1) -> list[dict]:
    return [
        {"fecha": (desde + timedelta(days=i * paso_dias)).isoformat(), "valor": v}
        for i, v in enumerate(valores)
    ]


class TestAnalizarEstabilidad:

    def test_serie_estable_sin_tendencia(self):
        rng = np.random.default_rng(42)
        valores = 100 + rng.normal(0, 1, 60)  # CV ~1%, sin tendencia
        result = est.analizar_estabilidad(_serie(list(valores)))
        assert result["clasificacion"] == "ESTABLE"
        assert result["cv_pct"] < 15
        assert result["tendencia"]["significativa"] is False

    def test_serie_con_tendencia_real(self):
        # sube de 100 a 200 de forma lineal sostenida a lo largo de 100 puntos
        valores = [100 + i * 1.0 for i in range(100)]
        result = est.analizar_estabilidad(_serie(valores))
        assert result["tendencia"]["significativa"] is True
        assert result["tendencia"]["cambio_pct_total_periodo"] > 50

    def test_serie_no_estable(self):
        rng = np.random.default_rng(7)
        valores = 100 + rng.normal(0, 60, 60)  # CV alto
        result = est.analizar_estabilidad(list(_serie(list(valores))))
        assert result["clasificacion"] == "NO_ESTABLE"

    def test_umbrales_configurables(self):
        rng = np.random.default_rng(1)
        valores = 100 + rng.normal(0, 20, 60)  # CV ~20%
        result_default = est.analizar_estabilidad(_serie(list(valores)))
        result_laxo = est.analizar_estabilidad(_serie(list(valores)), umbral_estable=25, umbral_variable=40)
        assert result_default["clasificacion"] != "ESTABLE"
        assert result_laxo["clasificacion"] == "ESTABLE"

    def test_datos_insuficientes(self):
        result = est.analizar_estabilidad(_serie([1, 2, 3]))
        assert "error" in result

    def test_datos_vacios(self):
        result = est.analizar_estabilidad([])
        assert "error" in result

    def test_falta_clave_valor(self):
        result = est.analizar_estabilidad([{"fecha": "2023-01-01"}] * 10)
        assert "error" in result


class TestDetectarCambiosDeRegimen:

    def test_detecta_quiebre_real_sostenido(self):
        rng = np.random.default_rng(3)
        # nivel 100 en enero-febrero, nivel 200 en marzo-abril (quiebre alineado a mes, sostenido)
        antes = list(100 + rng.normal(0, 3, 59))  # 2023-01-01 .. 2023-02-28
        despues = list(200 + rng.normal(0, 3, 61))  # 2023-03-01 .. 2023-04-30
        datos = _serie(antes + despues, desde=date(2023, 1, 1))
        result = est.detectar_cambios_de_regimen(datos, periodo="M", min_periodos_sostenido=2)
        assert len(result["quiebres_detectados"]) >= 1
        cambios = [q["cambio_pct"] for q in result["quiebres_detectados"]]
        assert any(c > 50 for c in cambios)

    def test_no_detecta_blip_de_un_solo_periodo(self):
        rng = np.random.default_rng(5)
        # nivel 100 constante, con un solo mes anómalo que vuelve al nivel original después
        base = list(100 + rng.normal(0, 2, 30))
        blip = list(300 + rng.normal(0, 2, 30))
        vuelta = list(100 + rng.normal(0, 2, 60))
        datos = _serie(base + blip + vuelta, desde=date(2023, 1, 1))
        result = est.detectar_cambios_de_regimen(datos, periodo="M", min_periodos_sostenido=2)
        # el blip no debe contar como quiebre sostenido porque vuelve al nivel anterior
        cambios_grandes = [q for q in result["quiebres_detectados"] if abs(q["cambio_pct"]) > 100]
        assert len(cambios_grandes) == 0

    def test_datos_insuficientes(self):
        result = est.detectar_cambios_de_regimen(_serie([1, 2, 3, 4, 5]))
        assert "error" in result


class TestCorrelacionConDesfase:

    def test_correlacion_real_con_desfase_detectada(self):
        rng = np.random.default_rng(11)
        n = 150
        x = list(50 + rng.normal(0, 5, n))
        # y depende de x con 10 dias de desfase, mas ruido
        lag_real = 10
        y_vals = []
        fechas_y = []
        for i in range(30, n):
            y_vals.append(x[i - lag_real] * 2 + rng.normal(0, 3))
            fechas_y.append(date(2023, 1, 1) + timedelta(days=i))
        serie_x = _serie(x, desde=date(2023, 1, 1))
        serie_y = [{"fecha": f.isoformat(), "valor": v} for f, v in zip(fechas_y, y_vals)]

        result = est.correlacion_con_desfase(serie_x, serie_y, ventana_dias=1, lag_min_dias=0, lag_max_dias=30)
        assert "mejor_desfase" in result
        assert abs(result["mejor_desfase"]["lag_dias"] - lag_real) <= 3
        assert result["mejor_desfase"]["r_niveles"] > 0.5

    def test_correlacion_espuria_por_tendencia_compartida_no_es_robusta(self):
        # dos series que solo comparten una tendencia de fondo (sin relacion causal real) --
        # mismo patron que el hallazgo real de Helios (ingreso vs conductividad)
        n = 200
        fechas = [date(2023, 1, 1) + timedelta(days=i) for i in range(n)]
        rng = np.random.default_rng(99)
        x = [100 - i * 0.3 + rng.normal(0, 2) for i in range(n)]  # tendencia bajando
        y = [50 + i * 0.15 + rng.normal(0, 2) for i in range(n)]  # tendencia subiendo, sin relacion real
        serie_x = [{"fecha": f.isoformat(), "valor": v} for f, v in zip(fechas, x)]
        serie_y = [{"fecha": f.isoformat(), "valor": v} for f, v in zip(fechas, y)]

        result = est.correlacion_con_desfase(serie_x, serie_y, ventana_dias=7, lag_min_dias=0, lag_max_dias=30)
        assert result["mejor_desfase"]["robusta"] is False
        assert "advertencia" in result

    def test_datos_insuficientes(self):
        result = est.correlacion_con_desfase(_serie([1, 2]), _serie([1, 2, 3]))
        assert "error" in result


class TestCompararFuentes:

    def test_fuentes_comparables_solo_ruido(self):
        rng = np.random.default_rng(21)
        fechas = [date(2023, 1, 1) + timedelta(days=i * 10) for i in range(15)]
        base = 100 + rng.normal(0, 10, 15)
        a = [{"fecha": f.isoformat(), "valor": float(v)} for f, v in zip(fechas, base)]
        b = [{"fecha": f.isoformat(), "valor": float(v * 1.02 + rng.normal(0, 1))} for f, v in zip(fechas, base)]
        result = est.comparar_fuentes(a, b, nombre_a="LabX", nombre_b="LabY")
        assert result["comparables"] is True

    def test_fuentes_no_comparables_sesgo_sistematico(self):
        # laboratorio B mide sistematicamente 50x mas alto -- mismo patron que el hallazgo real
        fechas = [date(2023, 1, 1) + timedelta(days=i * 10) for i in range(10)]
        a = [{"fecha": f.isoformat(), "valor": 1.0 + i * 0.1} for i, f in enumerate(fechas)]
        b = [{"fecha": f.isoformat(), "valor": (1.0 + i * 0.1) * 50} for i, f in enumerate(fechas)]
        result = est.comparar_fuentes(a, b, nombre_a="JLA", nombre_b="CIQA")
        assert result["comparables"] is False
        assert result["razon_media_JLA_sobre_CIQA"] == pytest.approx(1 / 50, rel=0.01)

    def test_pares_insuficientes(self):
        result = est.comparar_fuentes(_serie([1]), _serie([1]))
        assert "error" in result
