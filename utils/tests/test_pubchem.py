"""
Tests para criza/utils/pubchem.py

Unit tests: mock de requests.get. Integration: pytest -m integration (red real, sin auth).
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

_CRIZA = Path(__file__).parent.parent.parent
if str(_CRIZA) not in sys.path:
    sys.path.insert(0, str(_CRIZA))

import utils.pubchem as pubchem


def _mock_response(json_data: dict, status: int = 200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    if status >= 400 and status != 404:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status}")
    return resp


class TestSearchPubchem:

    def test_parsea_propiedades_correctamente(self):
        data = {"PropertyTable": {"Properties": [{
            "CID": 10220511, "MolecularFormula": "H16MgNO10P", "MolecularWeight": "245.41",
            "IUPACName": "azanium;magnesium;phosphate;hexahydrate", "CanonicalSMILES": "N.[Mg].O=P(O)(O)O",
        }]}}
        with patch("utils.pubchem.requests.get", return_value=_mock_response(data)):
            result = pubchem.search_pubchem("struvite")

        assert result["encontrado"] is True
        assert result["cid"] == 10220511
        assert result["formula"] == "H16MgNO10P"

    def test_no_encontrado_es_404(self):
        with patch("utils.pubchem.requests.get", return_value=_mock_response({}, status=404)):
            result = pubchem.search_pubchem("terminoquenoexiste")
        assert result["encontrado"] is False
        assert "error" not in result

    def test_request_falla_devuelve_error(self):
        with patch("utils.pubchem.requests.get", side_effect=Exception("timeout")):
            result = pubchem.search_pubchem("query")
        assert "error" in result


@pytest.mark.integration
class TestIntegration:

    def test_search_pubchem_struvite_real(self):
        result = pubchem.search_pubchem("struvite")
        assert "error" not in result
        assert result["encontrado"] is True
        assert result["formula"]
