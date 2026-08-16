"""
Tests para criza/utils/uniprot.py

Unit tests: mock de requests.get. Integration: pytest -m integration (red real, sin auth).
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

_CRIZA = Path(__file__).parent.parent.parent
if str(_CRIZA) not in sys.path:
    sys.path.insert(0, str(_CRIZA))

import utils.uniprot as uniprot


def _mock_response(json_data: dict, status: int = 200):
    resp = MagicMock()
    resp.status_code = status
    resp.raise_for_status = MagicMock()
    if status >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status}")
    resp.json.return_value = json_data
    return resp


MOCK_RESULT = {
    "results": [{
        "primaryAccession": "G1UBD1",
        "organism": {"scientificName": "Methylococcus capsulatus"},
        "proteinDescription": {
            "recommendedName": {
                "fullName": {"value": "Particulate methane monooxygenase alpha subunit"},
                "ecNumbers": [{"value": "1.14.18.3"}],
            }
        },
        "comments": [{"commentType": "FUNCTION", "texts": [{"value": "Oxidizes methane to methanol"}]}],
        "sequence": {"length": 260},
    }]
}


class TestSearchUniprot:

    def test_parsea_resultado_correctamente(self):
        with patch("utils.uniprot.requests.get", return_value=_mock_response(MOCK_RESULT)):
            result = uniprot.search_uniprot("methane monooxygenase")

        assert len(result["resultados"]) == 1
        entrada = result["resultados"][0]
        assert entrada["accession"] == "G1UBD1"
        assert entrada["ec_number"] == "1.14.18.3"
        assert entrada["organismo"] == "Methylococcus capsulatus"
        assert "Oxidizes methane" in entrada["funcion"]

    def test_sin_resultados_reviewed_reintenta_sin_filtro(self):
        empty = {"results": []}
        with patch("utils.uniprot.requests.get", side_effect=[_mock_response(empty), _mock_response(MOCK_RESULT)]) as mock_get:
            result = uniprot.search_uniprot("query")
        assert mock_get.call_count == 2
        assert len(result["resultados"]) == 1

    def test_request_falla_devuelve_error(self):
        with patch("utils.uniprot.requests.get", side_effect=Exception("timeout")):
            result = uniprot.search_uniprot("query")
        assert "error" in result

    def test_organism_filtro_se_incluye_en_query(self):
        with patch("utils.uniprot.requests.get", return_value=_mock_response(MOCK_RESULT)) as mock_get:
            uniprot.search_uniprot("query", organism="Methylococcus capsulatus")
        called_query = mock_get.call_args[1]["params"]["query"]
        assert "Methylococcus capsulatus" in called_query


@pytest.mark.integration
class TestIntegration:

    def test_search_uniprot_methane_monooxygenase_real(self):
        result = uniprot.search_uniprot("methane monooxygenase", max_results=3)
        assert "error" not in result
        assert len(result["resultados"]) > 0
        assert result["resultados"][0]["accession"]
