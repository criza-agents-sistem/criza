"""
Tests para criza/utils/bacdive.py

Unit tests: mock de requests.get. Integration: pytest -m integration (red real, sin auth —
API pública desde febrero 2026, ver docstring de utils/bacdive.py).
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

_CRIZA = Path(__file__).parent.parent.parent
if str(_CRIZA) not in sys.path:
    sys.path.insert(0, str(_CRIZA))

import utils.bacdive as bacdive


def _mock_response(json_data: dict, status: int = 200):
    resp = MagicMock()
    resp.status_code = status
    resp.raise_for_status = MagicMock()
    if status >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status}")
    resp.json.return_value = json_data
    return resp


class TestSearchBacdive:

    def test_busca_y_trae_detalle(self):
        taxon_resp = _mock_response({"count": 1, "results": [590]})
        fetch_resp = _mock_response({"results": {"590": {
            "General": {"description": "Bacillus test", "keywords": ["Bacteria"]},
            "Name and taxonomic classification": {"LPSN": {"full scientific name": "Bacillus test"}},
        }}})
        with patch("utils.bacdive.requests.get", side_effect=[taxon_resp, fetch_resp]) as mock_get:
            result = bacdive.search_bacdive("Bacillus", max_results=1)

        assert result["resultados"][0]["bacdive_id"] == "590"
        assert result["resultados"][0]["nombre_cientifico"] == "Bacillus test"
        # Usa v2, sin auth
        for call in mock_get.call_args_list:
            assert "/v2/" in call.args[0]
            assert "auth" not in call.kwargs

    def test_taxon_sin_resultados(self):
        with patch("utils.bacdive.requests.get", return_value=_mock_response({"count": 0, "results": []})):
            result = bacdive.search_bacdive("NoExiste")
        assert result["total_encontrados"] == 0
        assert result["resultados"] == []

    def test_taxon_request_falla(self):
        with patch("utils.bacdive.requests.get", side_effect=Exception("timeout")):
            result = bacdive.search_bacdive("Bacillus")
        assert "error" in result

    def test_fetch_individual_falla_no_rompe_los_demas(self):
        taxon_resp = _mock_response({"count": 2, "results": [590, 591]})
        fetch_ok = _mock_response({"results": {"591": {"General": {"description": "OK"}}}})
        with patch("utils.bacdive.requests.get", side_effect=[taxon_resp, Exception("timeout"), fetch_ok]):
            result = bacdive.search_bacdive("Bacillus", max_results=2)
        assert result["resultados"][0]["bacdive_id"] == "590"
        assert "error" in result["resultados"][0]
        assert result["resultados"][1]["bacdive_id"] == "591"


@pytest.mark.integration
class TestIntegration:

    def test_search_bacdive_real(self):
        result = bacdive.search_bacdive("Methanosarcina", max_results=2)
        assert "error" not in result
        assert result["total_encontrados"] > 0
