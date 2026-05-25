"""
Tests for tools/semantic_scholar.py — search_literature()

Integration tests: require Semantic Scholar API access (no key needed).
Skip with: pytest -m "not integration"
"""

import pytest
from tools.semantic_scholar import search_literature


@pytest.mark.integration
class TestSearchLiteratureIntegration:

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

    def test_max_results_capped_at_100(self):
        result = search_literature("fermentation", max_results=200)
        assert result["returned"] <= 100

    def test_empty_query_handled(self):
        """Empty or nonsense query should return without crashing."""
        result = search_literature("xyzxyzxyz_nonexistent_protein_query_12345", max_results=2)
        assert "results" in result  # may be empty, but should not crash

    def test_url_field_is_string(self):
        result = search_literature("lactoferrin", max_results=2)
        for paper in result["results"]:
            if paper.get("url"):
                assert isinstance(paper["url"], str)

    def test_year_field_is_numeric_or_none(self):
        result = search_literature("lactoferrin fermentation yield", max_results=3)
        for paper in result["results"]:
            if paper.get("year") is not None:
                assert isinstance(paper["year"], int)
