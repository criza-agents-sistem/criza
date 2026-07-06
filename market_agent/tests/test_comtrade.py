"""
Tests para tools/comtrade.py
"""

import pytest
from unittest.mock import patch, MagicMock


# ── Unit tests ────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_get_import_data_no_api_key():
    """Sin API key debe retornar error claro con instrucciones."""
    from tools.comtrade import get_import_data
    with patch.dict("os.environ", {"COMTRADE_API_KEY": ""}):
        result = get_import_data("3507")
    assert result["success"] is False
    assert "COMTRADE_API_KEY" in result["error"]
    assert result["data"] == []


@pytest.mark.unit
def test_get_import_data_parses_response(sample_comtrade_response):
    """Con respuesta válida, debe parsear correctamente y calcular summary."""
    from tools.comtrade import get_import_data
    mock_resp = MagicMock()
    mock_resp.json.return_value = sample_comtrade_response
    mock_resp.raise_for_status.return_value = None

    with patch.dict("os.environ", {"COMTRADE_API_KEY": "fake-key"}):
        with patch("tools.comtrade.requests.get", return_value=mock_resp):
            result = get_import_data("3507", year=2023)

    assert result["success"] is True
    assert len(result["data"]) == 2
    summary = result["summary"]
    assert summary["total_records"] == 2
    assert summary["total_import_usd"] == pytest.approx(4_700_000.0)
    assert summary["total_import_kg"] == pytest.approx(130_000.0)
    # precio CIF: 4_700_000 / 130_000 ≈ 36.15 USD/kg
    assert summary["price_cif_usd_per_kg"] == pytest.approx(36.15, rel=0.01)
    assert summary["top_origin_countries"][0]["country"] == "Denmark"
    assert "[VERIFICADO]" in result["source"]


@pytest.mark.unit
def test_get_import_data_empty_response():
    """Respuesta vacía de COMTRADE debe retornar success=True con nota útil."""
    from tools.comtrade import get_import_data
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": []}
    mock_resp.raise_for_status.return_value = None

    with patch.dict("os.environ", {"COMTRADE_API_KEY": "fake-key"}):
        with patch("tools.comtrade.requests.get", return_value=mock_resp):
            result = get_import_data("9999")

    assert result["success"] is True
    assert result["data"] == []
    assert "Sin datos" in result["summary"]["note"]


@pytest.mark.unit
def test_get_import_data_http_error():
    """Error HTTP debe retornar success=False con mensaje claro."""
    import requests as req
    from tools.comtrade import get_import_data

    with patch.dict("os.environ", {"COMTRADE_API_KEY": "fake-key"}):
        with patch("tools.comtrade.requests.get", side_effect=req.RequestException("timeout")):
            result = get_import_data("3507")

    assert result["success"] is False
    assert "timeout" in result["error"].lower() or "Error" in result["error"]


@pytest.mark.unit
def test_get_import_data_partner_country_passed():
    """El parámetro partner_country debe pasarse correctamente al request."""
    from tools.comtrade import get_import_data
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": []}
    mock_resp.raise_for_status.return_value = None

    with patch.dict("os.environ", {"COMTRADE_API_KEY": "fake-key"}):
        with patch("tools.comtrade.requests.get", return_value=mock_resp) as mock_get:
            get_import_data("3507", partner_country="076")

    call_params = mock_get.call_args[1]["params"]
    assert call_params["partnerCode"] == "076"


# ── Integration tests ─────────────────────────────────────────────────────────

@pytest.mark.integration
def test_get_import_data_real_api():
    """Consulta real a COMTRADE — requiere COMTRADE_API_KEY en .env."""
    import os
    from tools.comtrade import get_import_data

    if not os.getenv("COMTRADE_API_KEY"):
        pytest.skip("COMTRADE_API_KEY no configurada — skip integration test")

    result = get_import_data("3507", year=2022)
    assert result["success"] is True
    assert isinstance(result["data"], list)
    if result["data"]:
        assert "trade_value_usd" in result["data"][0]
        assert result["summary"]["price_cif_usd_per_kg"] is not None
