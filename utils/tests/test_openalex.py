"""
Tests para criza/utils/openalex.py — search_literature (muestra dirigida) y
search_literature_exhaustivo (Etapa 22, 2026-09-14 — pagina de verdad, no solo top-N).

Unit tests: mock de requests.get. Integration: pytest -m integration (red real, sin auth).
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

_CRIZA = Path(__file__).parent.parent.parent
if str(_CRIZA) not in sys.path:
    sys.path.insert(0, str(_CRIZA))

import utils.openalex as openalex


def _work(paper_id: str, title: str = "Título") -> dict:
    return {
        "id": paper_id,
        "title": title,
        "abstract_inverted_index": None,
        "publication_year": 2025,
        "authorships": [],
        "primary_location": {},
        "doi": None,
        "ids": {},
        "cited_by_count": 0,
        "open_access": {},
    }


def _mock_response(json_data: dict, status: int = 200):
    resp = MagicMock()
    resp.status_code = status
    resp.raise_for_status = MagicMock()
    if status >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status}")
    resp.json.return_value = json_data
    return resp


class TestSearchLiteratura:

    def test_devuelve_top_n_sin_paginar(self):
        pagina = _mock_response({"meta": {"count": 500}, "results": [_work("w1"), _work("w2")]})
        with patch("utils.openalex.requests.get", return_value=pagina) as mock_get:
            result = openalex.search_literature("digestate", max_results=2)
        assert mock_get.call_count == 1  # no pagina — sigue siendo muestra dirigida
        assert result["returned"] == 2
        assert result["total_found"] == 500


class TestSearchLiteraturaExhaustivo:

    def test_pagina_hasta_agotar_resultados_reales(self):
        """Con menos resultados reales que el techo de seguridad, se corta cuando la API deja
        de devolver — no sigue pidiendo páginas vacías."""
        pagina_1 = _mock_response({"meta": {"count": 3}, "results": [_work("w1"), _work("w2")]})
        pagina_2 = _mock_response({"meta": {"count": 3}, "results": [_work("w3")]})
        pagina_3 = _mock_response({"meta": {"count": 3}, "results": []})
        with patch("utils.openalex.requests.get", side_effect=[pagina_1, pagina_2, pagina_3]) as mock_get:
            result = openalex.search_literature_exhaustivo("compuesto raro", max_total=500)

        assert mock_get.call_count == 3
        assert result["total_traido"] == 3
        assert result["total_found"] == 3
        assert result["agotado"] is True

    def test_se_corta_en_el_techo_de_seguridad_sin_agotar(self):
        """Con muchos más resultados reales que el techo, para en el techo y lo declara
        explícitamente (agotado=False) — no promete cobertura que no dio."""
        pagina_grande = _mock_response({
            "meta": {"count": 100_000},
            "results": [_work(f"w{i}") for i in range(200)],
        })
        with patch("utils.openalex.requests.get", return_value=pagina_grande):
            result = openalex.search_literature_exhaustivo("término muy común", max_total=250)

        assert result["total_traido"] == 250
        assert result["agotado"] is False
        assert result["total_found"] == 100_000

    def test_un_solo_paper_agota_en_una_pagina(self):
        pagina = _mock_response({"meta": {"count": 1}, "results": [_work("w1")]})
        pagina_vacia = _mock_response({"meta": {"count": 1}, "results": []})
        with patch("utils.openalex.requests.get", side_effect=[pagina, pagina_vacia]):
            result = openalex.search_literature_exhaustivo("query muy específica", max_total=500)
        assert result["total_traido"] == 1
        assert result["agotado"] is True

    def test_error_en_pagina_devuelve_lo_traido_hasta_ahi(self):
        pagina_1 = _mock_response({"meta": {"count": 500}, "results": [_work("w1")]})
        with patch("utils.openalex.requests.get", side_effect=[pagina_1, Exception("timeout")]):
            result = openalex.search_literature_exhaustivo("query", max_total=500)
        assert result["total_traido"] == 1
        assert "error_en_pagina" in result
        assert result["agotado"] is False

    def test_trunca_abstracts_largos(self):
        """Encontrado real (2026-09-14): sin truncar, una corrida real con varias consultas
        acumuló 1.5M+ tokens de historial y reventó el límite de contexto de Claude (1M) en el
        turno 5. abstract_max_chars evita que esto se repita."""
        work_con_abstract_largo = _work("w1")
        # abstract_inverted_index con muchas palabras -> reconstruye un abstract largo
        work_con_abstract_largo["abstract_inverted_index"] = {f"palabra{i}": [i] for i in range(500)}
        pagina = _mock_response({"meta": {"count": 1}, "results": [work_con_abstract_largo]})
        pagina_vacia = _mock_response({"meta": {"count": 1}, "results": []})
        with patch("utils.openalex.requests.get", side_effect=[pagina, pagina_vacia]):
            result = openalex.search_literature_exhaustivo("query", max_total=500, abstract_max_chars=100)
        abstract = result["results"][0]["abstract"]
        assert len(abstract) <= 101  # 100 + el "…" de corte
        assert abstract.endswith("…")

    def test_no_trunca_abstracts_cortos(self):
        work = _work("w1", "Título")
        pagina = _mock_response({"meta": {"count": 1}, "results": [work]})
        pagina_vacia = _mock_response({"meta": {"count": 1}, "results": []})
        with patch("utils.openalex.requests.get", side_effect=[pagina, pagina_vacia]):
            result = openalex.search_literature_exhaustivo("query", max_total=500, abstract_max_chars=300)
        assert result["results"][0]["abstract"] == "No abstract available"

    def test_resultados_traen_los_mismos_campos_que_search_literature(self):
        pagina = _mock_response({"meta": {"count": 1}, "results": [_work("w1", "Un paper real")]})
        pagina_vacia = _mock_response({"meta": {"count": 1}, "results": []})
        with patch("utils.openalex.requests.get", side_effect=[pagina, pagina_vacia]):
            result = openalex.search_literature_exhaustivo("query", max_total=500)
        paper = result["results"][0]
        assert paper["title"] == "Un paper real"
        assert set(paper.keys()) == {
            "title", "abstract", "year", "journal", "authors", "url",
            "doi", "pmid", "pdf_url", "citation_count", "paper_id",
        }


@pytest.mark.integration
class TestIntegration:

    def test_search_literature_exhaustivo_query_real_acotada(self):
        """Query real, deliberadamente específica para no traer miles de páginas en el test."""
        result = openalex.search_literature_exhaustivo(
            "ectoine production Halomonas biogas digestate", max_total=100
        )
        assert "error_en_pagina" not in result
        assert result["total_traido"] >= 0
        assert isinstance(result["agotado"], bool)
