"""
Tests para criza/utils/bacdive.py

Unit tests: mock de requests.get + BACDIVE_EMAIL/PASSWORD. Integration: pytest -m integration
(requiere BACDIVE_EMAIL/BACDIVE_PASSWORD reales en el entorno — se skippea si no están).
"""

import os
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

    def test_sin_credenciales_devuelve_error_explicito(self):
        with patch.dict(os.environ, {}, clear=True):
            result = bacdive.search_bacdive("Methanosarcina")
        assert "error" in result
        assert "BACDIVE_EMAIL" in result["error"]

    def test_con_credenciales_busca_y_trae_detalle(self):
        taxon_resp = _mock_response({"count": 1, "results": [590]})
        fetch_resp = _mock_response({"results": {"590": {
            "General": {"description": "Bacillus test", "keywords": ["Bacteria"]},
            "Name and taxonomic classification": {"LPSN": {"full scientific name": "Bacillus test"}},
        }}})
        with patch.dict(os.environ, {"BACDIVE_EMAIL": "a@b.com", "BACDIVE_PASSWORD": "pw"}), \
             patch("utils.bacdive.requests.get", side_effect=[taxon_resp, fetch_resp]):
            result = bacdive.search_bacdive("Bacillus", max_results=1)

        assert result["resultados"][0]["bacdive_id"] == "590"
        assert result["resultados"][0]["nombre_cientifico"] == "Bacillus test"

    def test_taxon_sin_resultados(self):
        with patch.dict(os.environ, {"BACDIVE_EMAIL": "a@b.com", "BACDIVE_PASSWORD": "pw"}), \
             patch("utils.bacdive.requests.get", return_value=_mock_response({"count": 0, "results": []})):
            result = bacdive.search_bacdive("NoExiste")
        assert result["total_encontrados"] == 0
        assert result["resultados"] == []

    def test_taxon_request_falla(self):
        with patch.dict(os.environ, {"BACDIVE_EMAIL": "a@b.com", "BACDIVE_PASSWORD": "pw"}), \
             patch("utils.bacdive.requests.get", side_effect=Exception("timeout")):
            result = bacdive.search_bacdive("Bacillus")
        assert "error" in result


@pytest.mark.integration
class TestIntegration:

    def test_search_bacdive_real(self):
        if not os.getenv("BACDIVE_EMAIL") or not os.getenv("BACDIVE_PASSWORD"):
            pytest.skip("BACDIVE_EMAIL/BACDIVE_PASSWORD no configurados — registrarse en https://api.bacdive.dsmz.de/")
        result = bacdive.search_bacdive("Methanosarcina", max_results=2)
        assert "error" not in result
        assert result["total_encontrados"] > 0
