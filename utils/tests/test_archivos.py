"""
Tests para criza/utils/archivos.py — Etapa 22 (cont., 2026-09-15).

Excel sintéticos armados en memoria (openpyxl) — sin depender de archivos reales del disco.
"""

import base64
import io
import sys
from pathlib import Path

import pandas as pd
import pytest

_CRIZA = Path(__file__).parent.parent.parent
if str(_CRIZA) not in sys.path:
    sys.path.insert(0, str(_CRIZA))

import utils.archivos as arch


def _excel_simple() -> bytes:
    df = pd.DataFrame({
        "fecha": ["2023-01-01", "2023-02-01", "2023-03-01"],
        "pH": [7.8, 7.9, 7.85],
    })
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Hoja1", index=False)
    return buf.getvalue()


def _excel_header_desplazado() -> bytes:
    """Simula el caso real de Helios (hoja 'BD-MET'): filas de metadata antes del header real."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        pd.DataFrame({0: ["Reporte de laboratorio"]}).to_excel(
            writer, sheet_name="BD-MET", index=False, header=False, startrow=0
        )
        df = pd.DataFrame({"fecha": ["2024-01-01", "2024-02-01"], "Manganeso": [14.3, 15.1]})
        df.to_excel(writer, sheet_name="BD-MET", index=False, startrow=5)
    return buf.getvalue()


def _excel_con_codigos_mezclados() -> bytes:
    """Simula el caso real: una hoja con varios códigos de digestor distintos mezclados."""
    df = pd.DataFrame({
        "fecha": ["2023-01-01", "2023-01-01", "2023-02-01", "2023-02-01"],
        "codigo": ["T401", "T301", "T401", "T301"],
        "pH": [7.9, 6.5, 7.95, 6.4],
    })
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Digestores", index=False)
    return buf.getvalue()


class TestCodificarArchivo:

    def test_codifica_y_es_decodificable(self):
        contenido = b"hola mundo"
        b64 = arch.codificar_archivo(contenido)
        assert base64.b64decode(b64) == contenido

    def test_rechaza_archivo_demasiado_grande(self):
        contenido = b"x" * (9 * 1024 * 1024)
        with pytest.raises(ValueError):
            arch.codificar_archivo(contenido)


class TestPrevisualizarExcel:

    def test_lista_hojas_y_primeras_filas(self):
        preview = arch.previsualizar_excel(_excel_simple())
        assert "Hoja1" in preview
        assert "pH" in preview or "fecha" in preview

    def test_archivo_invalido_no_rompe(self):
        preview = arch.previsualizar_excel(b"esto no es un excel")
        assert "No se pudo abrir" in preview

    def test_reporta_rango_de_fechas_real_calculado(self):
        """El fix de fondo: el rango de fechas viene de un cómputo real (pandas), no de una
        adivinanza del modelo que lee el texto — caso raíz del bug de fabricación del Conductor
        (2026-09-15, "febrero 2022" inventado al no tener este dato)."""
        preview = arch.previsualizar_excel(_excel_simple())
        assert "2023-01-01 a 2023-03-01" in preview
        assert "3 de 3 filas" in preview

    def test_con_varias_columnas_de_fecha_reporta_la_mas_completa(self):
        """Caso real (T401, Helios): 6 columnas con 'fecha' en el nombre, la mayoría
        administrativas y casi vacías. Tomar la primera (en vez de la más completa) da un rango
        técnicamente calculado pero igual de engañoso que uno inventado — encontrado corriendo el
        fix contra el archivo real, antes de dárselo al Conductor."""
        df = pd.DataFrame({
            "fecha solicitud": [None, None, "2024-05-01", None, None],
            "fecha muestreo": ["2023-01-01", "2023-06-01", "2024-01-01", "2024-06-01", "2025-01-01"],
        })
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Datos", index=False)
        preview = arch.previsualizar_excel(buf.getvalue())
        assert "fecha muestreo" in preview
        assert "2023-01-01 a 2025-01-01" in preview
        assert "5 de 5 filas" in preview

    def test_columna_con_espacios_en_el_nombre_no_rompe(self):
        """Bug real: sin re-asignar df.columns con los nombres 'stripeados', df[col] tiraba
        KeyError apenas el header tenía un salto de línea o espacios — rompía la previsualización
        entera (encontrado con 'Base de datos Logística.xlsx' real)."""
        df = pd.DataFrame({"fecha \n": ["2023-01-01", "2023-02-01"], "valor": [1, 2]})
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Datos", index=False)
        preview = arch.previsualizar_excel(buf.getvalue())
        assert "No se pudo" not in preview
        assert "2023-01-01 a 2023-02-01" in preview

    def test_detecta_header_desplazado_y_reporta_filas_correctas(self):
        """Caso real de Helios: metadata de laboratorio antes del header — la previsualización
        debe encontrar el header real (fila 6) y no confundir la fila de metadata con datos."""
        preview = arch.previsualizar_excel(_excel_header_desplazado())
        assert "fila 6" in preview
        assert "Filas de datos: 2" in preview
        assert "2024-01-01 a 2024-02-01" in preview
        assert "2 de 2 filas" in preview

    def test_sin_columna_de_fecha_lo_dice_explicitamente(self):
        df = pd.DataFrame({"codigo": ["A", "B"], "valor": [1, 2]})
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="SinFecha", index=False)
        preview = arch.previsualizar_excel(buf.getvalue())
        assert "sin columna de fecha reconocible" in preview


class TestLeerSerieDeExcel:

    def test_lee_serie_simple(self):
        b64 = arch.codificar_archivo(_excel_simple())
        result = arch.leer_serie_de_excel(b64, hoja="Hoja1", columna_fecha="fecha", columna_valor="pH")
        assert result["n"] == 3
        assert result["serie"][0] == {"fecha": "2023-01-01", "valor": 7.8}

    def test_header_desplazado(self):
        b64 = arch.codificar_archivo(_excel_header_desplazado())
        result = arch.leer_serie_de_excel(
            b64, hoja="BD-MET", columna_fecha="fecha", columna_valor="Manganeso", header_fila=5,
        )
        assert result["n"] == 2
        assert result["serie"][0]["valor"] == 14.3

    def test_header_incorrecto_da_columnas_disponibles_no_error_silencioso(self):
        b64 = arch.codificar_archivo(_excel_header_desplazado())
        result = arch.leer_serie_de_excel(
            b64, hoja="BD-MET", columna_fecha="fecha", columna_valor="Manganeso", header_fila=0,
        )
        assert "error" in result
        assert "columnas_disponibles" in result

    def test_filtro_por_codigo_no_mezcla_puntos_distintos(self):
        b64 = arch.codificar_archivo(_excel_con_codigos_mezclados())
        result = arch.leer_serie_de_excel(
            b64, hoja="Digestores", columna_fecha="fecha", columna_valor="pH",
            filtro_columna="codigo", filtro_valor="T401",
        )
        assert result["n"] == 2
        assert all(7.5 < p["valor"] < 8.5 for p in result["serie"])  # solo los valores de T401, no T301

    def test_hoja_inexistente_devuelve_hojas_disponibles(self):
        b64 = arch.codificar_archivo(_excel_simple())
        result = arch.leer_serie_de_excel(b64, hoja="NoExiste", columna_fecha="fecha", columna_valor="pH")
        assert "error" in result
        assert result["hojas_disponibles"] == ["Hoja1"]

    def test_columna_inexistente_devuelve_columnas_disponibles(self):
        b64 = arch.codificar_archivo(_excel_simple())
        result = arch.leer_serie_de_excel(b64, hoja="Hoja1", columna_fecha="fecha", columna_valor="NoExiste")
        assert "error" in result
        assert "columnas_disponibles" in result

    def test_base64_invalido_da_error_claro(self):
        result = arch.leer_serie_de_excel("no es base64 valido!!!", hoja="x", columna_fecha="a", columna_valor="b")
        assert "error" in result

    def test_filtro_columna_inexistente_da_error_claro(self):
        b64 = arch.codificar_archivo(_excel_simple())
        result = arch.leer_serie_de_excel(
            b64, hoja="Hoja1", columna_fecha="fecha", columna_valor="pH",
            filtro_columna="no_existe", filtro_valor="x",
        )
        assert "error" in result
