"""
Tests para criza/utils/kegg.py

Unit tests: mock de requests.get. Integration: pytest -m integration (red real, sin auth).
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

_CRIZA = Path(__file__).parent.parent.parent
if str(_CRIZA) not in sys.path:
    sys.path.insert(0, str(_CRIZA))

import utils.kegg as kegg


def _mock_response(text: str = "", json_data=None, status: int = 200):
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    resp.raise_for_status = MagicMock()
    if status >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status}")
    if json_data is not None:
        resp.json.return_value = json_data
    return resp


class TestSearchKegg:

    def test_database_invalida_devuelve_error(self):
        result = kegg.search_kegg("query", database="no_existe")
        assert "error" in result

    def test_parsea_find_y_trae_detalle_top_n(self):
        find_resp = _mock_response(text="map00680\tMethane metabolism\nmap00010\tGlycolysis\n")
        get_resp = _mock_response(text="ENTRY map00680 Pathway\nNAME Methane metabolism\n")
        with patch("utils.kegg.requests.get", side_effect=[find_resp, get_resp, get_resp]):
            result = kegg.search_kegg("methane", database="pathway", fetch_detail_top_n=2)

        assert result["total_encontrados"] == 2
        assert result["resultados"][0]["id"] == "map00680"
        assert result["resultados"][0]["nombre"] == "Methane metabolism"
        assert "detalle" in result["resultados"][0]

    def test_find_falla_devuelve_error(self):
        with patch("utils.kegg.requests.get", side_effect=Exception("timeout")):
            result = kegg.search_kegg("query")
        assert "error" in result

    def test_max_results_limita_resultados(self):
        find_resp = _mock_response(text="\n".join(f"map{i}\tPathway {i}" for i in range(20)))
        get_resp = _mock_response(text="detalle")
        with patch("utils.kegg.requests.get", side_effect=[find_resp] + [get_resp] * 3):
            result = kegg.search_kegg("query", max_results=5, fetch_detail_top_n=3)
        assert result["total_encontrados"] == 5


@pytest.mark.integration
class TestIntegration:

    def test_search_kegg_methane_pathway_real(self):
        result = kegg.search_kegg("methane", database="pathway", max_results=5)
        assert "error" not in result
        assert result["total_encontrados"] > 0
        assert any("methane" in r["nombre"].lower() for r in result["resultados"])
