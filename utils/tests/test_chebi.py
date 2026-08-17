"""
Tests para criza/utils/chebi.py

Unit tests: mock de requests.get. Integration: pytest -m integration (red real, sin auth).
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

_CRIZA = Path(__file__).parent.parent.parent
if str(_CRIZA) not in sys.path:
    sys.path.insert(0, str(_CRIZA))

import utils.chebi as chebi


def _mock_response(json_data: dict, status: int = 200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    if status >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status}")
    return resp


class TestSearchChebi:

    def test_parsea_resultados_correctamente(self):
        data = {"response": {"docs": [{
            "obo_id": "CHEBI:17234", "label": "glucose",
            "description": ["An aldohexose used as a source of energy."],
            "exact_synonyms": ["Glucose", "gluco-hexose"],
        }]}}
        with patch("utils.chebi.requests.get", return_value=_mock_response(data)):
            result = chebi.search_chebi("glucose")

        assert result["total_encontrados"] == 1
        assert result["resultados"][0]["chebi_id"] == "CHEBI:17234"
        assert result["resultados"][0]["nombre"] == "glucose"

    def test_sin_resultados_devuelve_lista_vacia(self):
        with patch("utils.chebi.requests.get", return_value=_mock_response({"response": {"docs": []}})):
            result = chebi.search_chebi("terminoquenoexiste")
        assert result["total_encontrados"] == 0
        assert result["resultados"] == []

    def test_request_falla_devuelve_error(self):
        with patch("utils.chebi.requests.get", side_effect=Exception("timeout")):
            result = chebi.search_chebi("query")
        assert "error" in result


@pytest.mark.integration
class TestIntegration:

    def test_search_chebi_glucose_real(self):
        result = chebi.search_chebi("glucose", max_results=3)
        assert "error" not in result
        assert result["total_encontrados"] > 0
        assert result["resultados"][0]["chebi_id"].startswith("CHEBI:")
