"""
Tests para criza/utils/bcra.py

Unit tests: mock de requests.get. Integration: pytest -m integration (red real, sin auth,
API pública del BCRA).
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

_CRIZA = Path(__file__).parent.parent.parent
if str(_CRIZA) not in sys.path:
    sys.path.insert(0, str(_CRIZA))

import utils.bcra as bcra


def _mock_response(json_data: dict, status: int = 200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    if status >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status}")
    return resp


class TestSearchBcraVariables:

    def test_filtra_por_texto_en_descripcion(self):
        data = {"results": [
            {"idVariable": 4, "descripcion": "Tipo de cambio minorista (promedio vendedor)",
             "categoria": "Principales Variables", "unidadExpresion": "Pesos argentinos por dólar",
             "moneda": "ML", "ultFechaInformada": "2026-09-04", "ultValorInformado": 1528.6},
            {"idVariable": 7, "descripcion": "Tasa de interés BADLAR de bancos privados",
             "categoria": "Principales Variables", "unidadExpresion": "En porcentaje nominal anual",
             "moneda": "ML", "ultFechaInformada": "2026-09-03", "ultValorInformado": 23.25},
        ]}
        with patch("utils.bcra.requests.get", return_value=_mock_response(data)):
            result = bcra.search_bcra_variables("tipo de cambio")

        assert result["success"] is True
        assert result["total_found"] == 1
        assert result["variables"][0]["id_variable"] == 4

    def test_matchea_por_palabras_no_por_substring_literal(self):
        """Bug real (2026-09-07): 'BADLAR bancos privados' no matcheaba 'Tasa de interés BADLAR
        DE bancos privados' con substring literal — ahora matchea por AND de palabras sueltas."""
        data = {"results": [
            {"idVariable": 7, "descripcion": "Tasa de interés BADLAR de bancos privados",
             "categoria": "Principales Variables", "unidadExpresion": "En porcentaje nominal anual",
             "moneda": "ML", "ultFechaInformada": "2026-09-03", "ultValorInformado": 23.25},
        ]}
        with patch("utils.bcra.requests.get", return_value=_mock_response(data)):
            result = bcra.search_bcra_variables("BADLAR bancos privados")

        assert result["total_found"] == 1
        assert result["variables"][0]["id_variable"] == 7

    def test_sin_resultados_no_es_error(self):
        with patch("utils.bcra.requests.get", return_value=_mock_response({"results": []})):
            result = bcra.search_bcra_variables("término inexistente")
        assert result["success"] is True
        assert result["total_found"] == 0
        assert result["variables"] == []

    def test_request_falla_devuelve_error(self):
        import requests
        with patch("utils.bcra.requests.get", side_effect=requests.RequestException("timeout")):
            result = bcra.search_bcra_variables("badlar")
        assert result["success"] is False
        assert "error" in result


class TestGetBcraValues:

    def test_parsea_detalle_correctamente(self):
        data = {"results": [{"idVariable": 4, "detalle": [
            {"fecha": "2026-09-04", "valor": 1528.6},
            {"fecha": "2026-09-03", "valor": 1529.42},
        ]}]}
        with patch("utils.bcra.requests.get", return_value=_mock_response(data)):
            result = bcra.get_bcra_values(4)

        assert result["success"] is True
        assert result["valores"][0] == {"fecha": "2026-09-04", "valor": 1528.6}

    def test_id_variable_sin_datos_es_error_no_excepcion(self):
        with patch("utils.bcra.requests.get", return_value=_mock_response({"results": []})):
            result = bcra.get_bcra_values(999999)
        assert result["success"] is False
        assert "error" in result

    def test_request_falla_devuelve_error(self):
        import requests
        with patch("utils.bcra.requests.get", side_effect=requests.RequestException("timeout")):
            result = bcra.get_bcra_values(4)
        assert result["success"] is False
        assert "error" in result

    def test_pasa_desde_hasta_como_params(self):
        data = {"results": [{"idVariable": 4, "detalle": [{"fecha": "2026-09-04", "valor": 1528.6}]}]}
        with patch("utils.bcra.requests.get", return_value=_mock_response(data)) as mock_get:
            bcra.get_bcra_values(4, desde="2026-01-01", hasta="2026-09-04", limit=3)

        _, kwargs = mock_get.call_args
        assert kwargs["params"]["desde"] == "2026-01-01"
        assert kwargs["params"]["hasta"] == "2026-09-04"
        assert kwargs["params"]["limit"] == 3


@pytest.mark.integration
class TestIntegration:

    def test_search_bcra_variables_tipo_de_cambio_real(self):
        result = bcra.search_bcra_variables("tipo de cambio minorista")
        assert result["success"] is True
        assert result["total_found"] >= 1
        assert any(v["id_variable"] == 4 for v in result["variables"])

    def test_get_bcra_values_tipo_de_cambio_real(self):
        result = bcra.get_bcra_values(4, limit=3)
        assert result["success"] is True
        assert len(result["valores"]) >= 1
        assert result["valores"][0]["valor"] > 0
