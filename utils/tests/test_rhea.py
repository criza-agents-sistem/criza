"""
Tests para criza/utils/rhea.py

Unit tests: mock de requests.get. Integration: pytest -m integration (red real, sin auth).
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

_CRIZA = Path(__file__).parent.parent.parent
if str(_CRIZA) not in sys.path:
    sys.path.insert(0, str(_CRIZA))

import utils.rhea as rhea


def _mock_response(text: str = "", status: int = 200):
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    resp.raise_for_status = MagicMock()
    if status >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status}")
    return resp


class TestSearchRhea:

    def test_parsea_tsv_correctamente(self):
        tsv = (
            "Reaction identifier\tEquation\tEC number\tChEBI name\n"
            "RHEA:13637\tmethane + NADH + O2 = methanol + NAD+ + H2O\tEC:1.14.13.25\tmethane;NADH\n"
        )
        with patch("utils.rhea.requests.get", return_value=_mock_response(text=tsv)):
            result = rhea.search_rhea("methane")

        assert result["total_encontrados"] == 1
        assert result["resultados"][0]["rhea_id"] == "RHEA:13637"
        assert result["resultados"][0]["ec_number"] == "EC:1.14.13.25"

    def test_sin_resultados_devuelve_lista_vacia(self):
        tsv = "Reaction identifier\tEquation\tEC number\tChEBI name\n"
        with patch("utils.rhea.requests.get", return_value=_mock_response(text=tsv)):
            result = rhea.search_rhea("terminoquenoexiste")
        assert result["total_encontrados"] == 0
        assert result["resultados"] == []

    def test_request_falla_devuelve_error(self):
        with patch("utils.rhea.requests.get", side_effect=Exception("timeout")):
            result = rhea.search_rhea("query")
        assert "error" in result


@pytest.mark.integration
class TestIntegration:

    def test_search_rhea_methane_real(self):
        result = rhea.search_rhea("methane", max_results=5)
        assert "error" not in result
        assert result["total_encontrados"] > 0
        assert result["resultados"][0]["rhea_id"].startswith("RHEA:")
