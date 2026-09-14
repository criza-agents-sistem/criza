"""
Tests para criza/utils/brightdata_serp.py — Etapa 22 (cont., 2026-09-14).

Unit tests: mock de requests.post. Integration: pytest -m integration (red real, BRIGHTDATA_API_KEY
tiene que estar seteada en el entorno).
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

_CRIZA = Path(__file__).parent.parent.parent
if str(_CRIZA) not in sys.path:
    sys.path.insert(0, str(_CRIZA))

import utils.brightdata_serp as bd


def _mock_response(json_data: dict, status: int = 200):
    resp = MagicMock()
    resp.status_code = status
    resp.raise_for_status = MagicMock()
    if status >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status}")
    resp.json.return_value = json_data
    return resp


def _organic(n: int) -> list[dict]:
    return [{"title": f"Título {i}", "link": f"https://example.com/{i}", "description": f"Descripción {i}"} for i in range(n)]


class TestSinApiKey:

    def test_devuelve_error_claro_sin_api_key(self, monkeypatch):
        monkeypatch.delenv("BRIGHTDATA_API_KEY", raising=False)
        result = bd.buscar_web_tecnico("query")
        assert "error" in result
        assert "BRIGHTDATA_API_KEY" in result["error"]


class TestBuscarWebTecnico:

    def test_pagina_hasta_agotar_resultados_reales(self, monkeypatch):
        monkeypatch.setenv("BRIGHTDATA_API_KEY", "fake-key")
        pagina_1 = _mock_response({"general": {"results_cnt": 12}, "organic": _organic(10)})
        pagina_2 = _mock_response({"general": {"results_cnt": 12}, "organic": _organic(2)})
        pagina_3 = _mock_response({"general": {"results_cnt": 12}, "organic": []})
        with patch("utils.brightdata_serp.requests.post", side_effect=[pagina_1, pagina_2, pagina_3]) as mock_post:
            result = bd.buscar_web_tecnico("ectoine production", max_total=30)

        assert mock_post.call_count == 3
        assert result["total_traido"] == 12
        assert result["total_found"] == 12
        assert result["agotado"] is True

    def test_se_corta_en_el_techo_de_seguridad(self, monkeypatch):
        monkeypatch.setenv("BRIGHTDATA_API_KEY", "fake-key")
        pagina = _mock_response({"general": {"results_cnt": 500}, "organic": _organic(10)})
        with patch("utils.brightdata_serp.requests.post", return_value=pagina):
            result = bd.buscar_web_tecnico("query muy común", max_total=15)
        assert result["total_traido"] == 15
        assert result["agotado"] is False

    def test_manda_zone_y_authorization_correctos(self, monkeypatch):
        monkeypatch.setenv("BRIGHTDATA_API_KEY", "mi-key-real")
        pagina = _mock_response({"general": {"results_cnt": 0}, "organic": []})
        with patch("utils.brightdata_serp.requests.post", return_value=pagina) as mock_post:
            bd.buscar_web_tecnico("query")
        _, kwargs = mock_post.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer mi-key-real"
        assert kwargs["json"]["zone"] == "serp_api1"

    def test_idioma_y_pais_se_incluyen_en_la_url(self, monkeypatch):
        monkeypatch.setenv("BRIGHTDATA_API_KEY", "fake-key")
        pagina = _mock_response({"general": {"results_cnt": 0}, "organic": []})
        with patch("utils.brightdata_serp.requests.post", return_value=pagina) as mock_post:
            bd.buscar_web_tecnico("query", idioma="pt", pais="br")
        _, kwargs = mock_post.call_args
        url = kwargs["json"]["url"]
        assert "hl=pt" in url
        assert "gl=br" in url

    def test_trunca_descripciones_largas(self, monkeypatch):
        monkeypatch.setenv("BRIGHTDATA_API_KEY", "fake-key")
        largo = [{"title": "t", "link": "u", "description": "x" * 1000}]
        pagina = _mock_response({"general": {"results_cnt": 1}, "organic": largo})
        pagina_vacia = _mock_response({"general": {"results_cnt": 1}, "organic": []})
        with patch("utils.brightdata_serp.requests.post", side_effect=[pagina, pagina_vacia]):
            result = bd.buscar_web_tecnico("query", descripcion_max_chars=50)
        assert len(result["results"][0]["descripcion"]) <= 51

    def test_error_en_pagina_devuelve_lo_traido_hasta_ahi(self, monkeypatch):
        monkeypatch.setenv("BRIGHTDATA_API_KEY", "fake-key")
        pagina_1 = _mock_response({"general": {"results_cnt": 100}, "organic": _organic(10)})
        with patch("utils.brightdata_serp.requests.post", side_effect=[pagina_1, Exception("timeout")]):
            result = bd.buscar_web_tecnico("query", max_total=100)
        assert result["total_traido"] == 10
        assert "error_en_pagina" in result
        assert result["agotado"] is False


@pytest.mark.integration
class TestIntegration:

    def test_buscar_web_tecnico_query_real(self):
        result = bd.buscar_web_tecnico("ectoine industrial production Halomonas", max_total=10)
        assert "error" not in result
        assert result["total_traido"] >= 0
