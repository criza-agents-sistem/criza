"""
Tests para tools/datosgobar.py
"""

import pytest
from unittest.mock import patch, MagicMock


# ── Unit tests ────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_search_official_stats_parses_response(sample_datosgobar_response):
    """Con respuesta válida debe retornar datasets bien estructurados."""
    from market_agent.tools.datosgobar import search_official_stats
    mock_resp = MagicMock()
    mock_resp.json.return_value = sample_datosgobar_response
    mock_resp.raise_for_status.return_value = None

    with patch("tools.datosgobar.requests.get", return_value=mock_resp):
        result = search_official_stats("enzimas exportaciones")

    assert result["success"] is True
    assert len(result["datasets"]) == 2
    assert result["datasets"][0]["title"] == "Exportaciones agropecuarias por producto"
    assert result["datasets"][0]["organization"] == "MAGYP"
    assert "[VERIFICADO]" in result["source"]
    assert len(result["resources"]) > 0


@pytest.mark.unit
def test_search_official_stats_http_error():
    """Error HTTP debe retornar success=False."""
    import requests as req
    from market_agent.tools.datosgobar import search_official_stats

    with patch("tools.datosgobar.requests.get", side_effect=req.RequestException("connection error")):
        result = search_official_stats("fitasa")

    assert result["success"] is False
    assert result["datasets"] == []


@pytest.mark.unit
def test_search_official_stats_api_returns_false():
    """Si la API retorna success=false, debe manejarlo gracefully."""
    from market_agent.tools.datosgobar import search_official_stats
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"success": False}
    mock_resp.raise_for_status.return_value = None

    with patch("tools.datosgobar.requests.get", return_value=mock_resp):
        result = search_official_stats("test")

    assert result["success"] is False
    assert result["datasets"] == []


@pytest.mark.unit
def test_search_official_stats_with_organization():
    """El filtro de organismo resuelve el alias: 'indec' → slug 'sspm'."""
    from market_agent.tools.datosgobar import search_official_stats
    mock_resp = MagicMock()
    # count > 0 para evitar el retry sin filtro
    mock_resp.json.return_value = {"success": True, "result": {"count": 1, "results": []}}
    mock_resp.raise_for_status.return_value = None

    with patch("tools.datosgobar.requests.get", return_value=mock_resp) as mock_get:
        search_official_stats("enzimas", organization="indec")

    call_params = mock_get.call_args[1]["params"]
    # 'indec' se resuelve a slug 'sspm' por _resolve_org
    assert "sspm" in call_params.get("fq", "")


@pytest.mark.unit
def test_search_official_stats_description_truncated():
    """Descripciones largas deben truncarse a 300 caracteres."""
    from market_agent.tools.datosgobar import search_official_stats
    long_description = "x" * 1000
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "success": True,
        "result": {
            "count": 1,
            "results": [{
                "title": "Test",
                "notes": long_description,
                "name": "test",
                "organization": {"title": "INDEC"},
                "metadata_modified": "",
                "resources": [],
            }],
        },
    }
    mock_resp.raise_for_status.return_value = None

    with patch("tools.datosgobar.requests.get", return_value=mock_resp):
        result = search_official_stats("test")

    assert len(result["datasets"][0]["description"]) <= 300


# ── Unit: search_series ───────────────────────────────────────────────────────

_SERIES_RESPONSE = {
    "data": [
        {
            "field": {
                "id": "MAGyP_FAENA_PORCINA",
                "description": "Faena porcina mensual (cabezas)",
                "units": "Cabezas",
                "frequency": "month",
                "time_index_start": "2000-01",
                "time_index_end": "2024-12",
            },
            "dataset": {
                "title": "Estadísticas porcinas MAGyP",
                "publisher": {"name": "Ministerio de Agricultura"},
            },
        }
    ]
}


@pytest.mark.unit
def test_search_series_parses_response():
    """search_series parsea la respuesta de la API de Series."""
    from market_agent.tools.datosgobar import search_series
    mock_resp = MagicMock()
    mock_resp.json.return_value = _SERIES_RESPONSE
    mock_resp.raise_for_status.return_value = None

    with patch("tools.datosgobar.requests.get", return_value=mock_resp):
        result = search_series("faena porcina")

    assert result["success"] is True
    assert len(result["series"]) == 1
    s = result["series"][0]
    assert s["id"] == "MAGyP_FAENA_PORCINA"
    assert s["descripcion"] == "Faena porcina mensual (cabezas)"
    assert s["unidad"] == "Cabezas"
    assert s["frecuencia"] == "month"
    assert "[VERIFICADO]" in result["source"]


@pytest.mark.unit
def test_search_series_http_error():
    """Error HTTP → success=False."""
    import requests as req
    from market_agent.tools.datosgobar import search_series

    with patch("tools.datosgobar.requests.get", side_effect=req.RequestException("timeout")):
        result = search_series("producción soja")

    assert result["success"] is False
    assert result["series"] == []


@pytest.mark.unit
def test_search_series_empty_data():
    """Sin series → lista vacía, total_found=0."""
    from market_agent.tools.datosgobar import search_series
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": []}
    mock_resp.raise_for_status.return_value = None

    with patch("tools.datosgobar.requests.get", return_value=mock_resp):
        result = search_series("término sin resultados")

    assert result["success"] is True
    assert result["series"] == []
    assert result["total_found"] == 0


# ── Unit: get_series_values ───────────────────────────────────────────────────

_VALUES_RESPONSE = {
    "data": [
        ["2024-12", 1234567.0],
        ["2024-11", 1189234.0],
        ["2024-10", 1201876.0],
    ]
}


@pytest.mark.unit
def test_get_series_values_parses_response():
    """get_series_values parsea {fecha, valor} desde la API."""
    from market_agent.tools.datosgobar import get_series_values
    mock_resp = MagicMock()
    mock_resp.json.return_value = _VALUES_RESPONSE
    mock_resp.raise_for_status.return_value = None

    with patch("tools.datosgobar.requests.get", return_value=mock_resp):
        result = get_series_values("MAGyP_FAENA_PORCINA", last=3)

    assert result["success"] is True
    assert len(result["valores"]) == 3
    assert result["valores"][0] == {"fecha": "2024-12", "valor": 1234567.0}
    assert result["series_id"] == "MAGyP_FAENA_PORCINA"


@pytest.mark.unit
def test_get_series_values_http_error():
    """Error HTTP → success=False."""
    import requests as req
    from market_agent.tools.datosgobar import get_series_values

    with patch("tools.datosgobar.requests.get", side_effect=req.RequestException("timeout")):
        result = get_series_values("INVALID_ID")

    assert result["success"] is False
    assert result["valores"] == []


@pytest.mark.unit
def test_get_series_values_malformed_row_skipped():
    """Rows con menos de 2 elementos no crashean — se omiten."""
    from market_agent.tools.datosgobar import get_series_values
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": [["2024-12", 100], ["2024-11"], [None, 200]]}
    mock_resp.raise_for_status.return_value = None

    with patch("tools.datosgobar.requests.get", return_value=mock_resp):
        result = get_series_values("TEST_ID")

    assert result["success"] is True
    # Solo la row completa + la que tiene None como fecha pasa
    assert len(result["valores"]) >= 1


# ── Integration tests ─────────────────────────────────────────────────────────

@pytest.mark.integration
def test_search_official_stats_real_api():
    """Consulta real a datos.gob.ar — sin API key requerida."""
    from market_agent.tools.datosgobar import search_official_stats

    result = search_official_stats("exportaciones agropecuarias", max_results=5)
    assert result["success"] is True
    assert isinstance(result["datasets"], list)
    assert result["total_found"] >= 0
    assert "[VERIFICADO]" in result["source"]


@pytest.mark.integration
def test_search_series_real_api():
    """Consulta real a la API de Series de datos.gob.ar."""
    from market_agent.tools.datosgobar import search_series

    result = search_series("faena porcina", max_results=5)
    assert result["success"] is True
    assert isinstance(result["series"], list)
    assert "[VERIFICADO]" in result["source"]


@pytest.mark.integration
def test_get_series_values_real_api():
    """Si search_series encuentra una serie, get_series_values trae valores reales."""
    from market_agent.tools.datosgobar import search_series, get_series_values

    series_result = search_series("producción porcina", max_results=3)
    if not series_result["series"]:
        pytest.skip("No se encontraron series para el término — API fluctúa")

    series_id = series_result["series"][0]["id"]
    values_result = get_series_values(series_id, last=4)

    assert values_result["success"] is True
    assert isinstance(values_result["valores"], list)
