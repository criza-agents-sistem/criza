"""
Tests for tools/openalex.py — search_literature()

Unit tests: prueban lógica interna sin llamadas de red.
Integration tests: requieren acceso a OpenAlex API. Correr con: pytest -m integration
"""

import pytest
from unittest.mock import patch, MagicMock
from tools.openalex import search_literature, _reconstruct_abstract


# ──────────────────────────────────────────────
# UNIT TESTS — sin red
# ──────────────────────────────────────────────

class TestReconstructAbstract:

    def test_simple_inverted_index(self):
        inverted = {"Hello": [0], "world": [1]}
        assert _reconstruct_abstract(inverted) == "Hello world"

    def test_multi_position_word(self):
        inverted = {"the": [0, 3], "cat": [1], "and": [2], "dog": [4]}
        result = _reconstruct_abstract(inverted)
        assert result == "the cat and the dog"

    def test_none_returns_fallback(self):
        assert _reconstruct_abstract(None) == "No abstract available"

    def test_empty_dict_returns_fallback(self):
        assert _reconstruct_abstract({}) == "No abstract available"

    def test_preserves_word_order(self):
        inverted = {"C": [2], "A": [0], "B": [1]}
        assert _reconstruct_abstract(inverted) == "A B C"


class TestSearchLiteratureUnit:

    def _make_mock_work(self, title="Test Paper", year=2023, doi="10.1234/test"):
        return {
            "id": "https://openalex.org/W123",
            "title": title,
            "abstract_inverted_index": {"Background": [0], "study": [1]},
            "publication_year": year,
            "authorships": [
                {"author": {"display_name": "Author One"}},
                {"author": {"display_name": "Author Two"}},
            ],
            "primary_location": {
                "source": {"display_name": "Nature Biotechnology"}
            },
            "doi": f"https://doi.org/{doi}",
            "ids": {"pmid": "https://pubmed.ncbi.nlm.nih.gov/12345/"},
            "cited_by_count": 42,
            "open_access": {"oa_url": "https://example.com/paper.pdf"},
        }

    def test_output_has_required_keys(self):
        mock_response = {
            "meta": {"count": 1},
            "results": [self._make_mock_work()],
        }
        with patch("tools.openalex.requests.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response,
                raise_for_status=lambda: None,
            )
            result = search_literature("test query")

        assert "query" in result
        assert "total_found" in result
        assert "returned" in result
        assert "results" in result
        assert "source" in result
        assert result["source"] == "openalex"

    def test_paper_has_required_keys(self):
        mock_response = {
            "meta": {"count": 1},
            "results": [self._make_mock_work()],
        }
        with patch("tools.openalex.requests.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response,
                raise_for_status=lambda: None,
            )
            result = search_literature("test query")

        required = {"title", "abstract", "year", "journal", "authors", "url", "doi", "pmid", "citation_count"}
        for paper in result["results"]:
            assert required.issubset(paper.keys()), \
                f"Missing keys: {required - paper.keys()}"

    def test_doi_strip_prefix(self):
        """DOI debe venir sin prefijo https://doi.org/"""
        mock_response = {
            "meta": {"count": 1},
            "results": [self._make_mock_work(doi="10.1234/test")],
        }
        with patch("tools.openalex.requests.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response,
                raise_for_status=lambda: None,
            )
            result = search_literature("test")

        assert result["results"][0]["doi"] == "10.1234/test"

    def test_pmid_strip_prefix(self):
        """PMID debe venir como número, sin URL prefix."""
        mock_response = {
            "meta": {"count": 1},
            "results": [self._make_mock_work()],
        }
        with patch("tools.openalex.requests.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response,
                raise_for_status=lambda: None,
            )
            result = search_literature("test")

        assert result["results"][0]["pmid"] == "12345"

    def test_abstract_reconstructed(self):
        mock_response = {
            "meta": {"count": 1},
            "results": [self._make_mock_work()],
        }
        with patch("tools.openalex.requests.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response,
                raise_for_status=lambda: None,
            )
            result = search_literature("test")

        assert result["results"][0]["abstract"] == "Background study"

    def test_max_results_capped_at_200(self):
        with patch("tools.openalex.requests.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: {"meta": {"count": 0}, "results": []},
                raise_for_status=lambda: None,
            )
            search_literature("test", max_results=500)

        call_params = mock_get.call_args[1]["params"]
        assert call_params["per_page"] == 200

    def test_http_error_returns_error_dict(self):
        import requests as req
        with patch("tools.openalex.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 500
            mock_resp.raise_for_status.side_effect = req.exceptions.HTTPError("500 Server Error")
            mock_get.return_value = mock_resp
            result = search_literature("test")

        assert "error" in result
        assert result["results"] == []

    def test_network_exception_triggers_fallback(self):
        """Si OpenAlex falla por timeout, intenta Semantic Scholar."""
        with patch("tools.openalex.requests.get", side_effect=Exception("timeout")):
            with patch("tools.openalex._fallback_semantic_scholar") as mock_fallback:
                mock_fallback.return_value = {"results": [], "total_found": 0, "source": "semantic_scholar_fallback"}
                result = search_literature("test")

        mock_fallback.assert_called_once()

    def test_authors_et_al_over_3(self):
        work = self._make_mock_work()
        work["authorships"] = [
            {"author": {"display_name": f"Author {i}"}} for i in range(5)
        ]
        mock_response = {"meta": {"count": 1}, "results": [work]}
        with patch("tools.openalex.requests.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response,
                raise_for_status=lambda: None,
            )
            result = search_literature("test")

        assert "et al." in result["results"][0]["authors"]

    def test_year_is_string(self):
        mock_response = {
            "meta": {"count": 1},
            "results": [self._make_mock_work(year=2021)],
        }
        with patch("tools.openalex.requests.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_response,
                raise_for_status=lambda: None,
            )
            result = search_literature("test")

        assert result["results"][0]["year"] == "2021"
        assert isinstance(result["results"][0]["year"], str)


# ──────────────────────────────────────────────
# INTEGRATION TESTS — requieren red
# ──────────────────────────────────────────────

@pytest.mark.integration
class TestOpenAlexIntegration:

    def test_returns_results_for_known_query(self):
        result = search_literature("lactoferrin recombinant expression", max_results=3)
        assert result["returned"] > 0
        assert len(result["results"]) > 0

    def test_required_keys_in_response(self):
        result = search_literature("protein fermentation", max_results=2)
        required = {"query", "total_found", "returned", "results"}
        assert required.issubset(result.keys())

    def test_required_keys_in_each_paper(self):
        result = search_literature("lactoferrin thermostability", max_results=2)
        required_paper_keys = {"title", "abstract", "year", "url"}
        for paper in result["results"]:
            assert required_paper_keys.issubset(paper.keys()), \
                f"Missing keys in paper: {required_paper_keys - paper.keys()}"

    def test_max_results_respected(self):
        result = search_literature("protein engineering", max_results=5)
        assert result["returned"] <= 5
        assert len(result["results"]) <= 5

    def test_empty_query_handled(self):
        result = search_literature("xyzxyzxyz_nonexistent_protein_query_12345", max_results=2)
        assert "results" in result

    def test_source_is_openalex(self):
        result = search_literature("phytase feed enzyme", max_results=2)
        assert result.get("source") == "openalex"

    def test_abstract_is_reconstructed(self):
        """Abstracts deben ser texto legible, no índices invertidos."""
        result = search_literature("phytase animal feed phosphorus", max_results=3)
        for paper in result["results"]:
            abstract = paper.get("abstract", "")
            if abstract and abstract != "No abstract available":
                # Debe ser texto, no un dict
                assert isinstance(abstract, str)
                assert len(abstract) > 10

    def test_agro_query_returns_relevant_results(self):
        """Búsqueda agro debe devolver papers del dominio."""
        result = search_literature("xylanase broiler feed performance", max_results=5)
        assert result["total_found"] > 0
