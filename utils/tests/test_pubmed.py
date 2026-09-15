"""
Tests para criza/utils/pubmed.py — Etapa 22 (cont., 2026-09-14).

Unit tests: mock de requests.get (esearch + efetch). Integration: pytest -m integration (red
real, NCBI E-utilities no requiere API key para volumen bajo).
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

_CRIZA = Path(__file__).parent.parent.parent
if str(_CRIZA) not in sys.path:
    sys.path.insert(0, str(_CRIZA))

import utils.pubmed as pm


def _mock_esearch(pmids: list[str], count: int | None = None) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "esearchresult": {"idlist": pmids, "count": str(count if count is not None else len(pmids))}
    }
    return resp


def _mock_efetch_xml(articles: list[dict]) -> MagicMock:
    """Cada dict: {pmid, title, abstract, year, journal}."""
    partes = []
    for a in articles:
        abstract_xml = f"<AbstractText>{a['abstract']}</AbstractText>" if a.get("abstract") else ""
        partes.append(f"""
        <PubmedArticle>
          <MedlineCitation>
            <PMID>{a['pmid']}</PMID>
            <Article>
              <ArticleTitle>{a['title']}</ArticleTitle>
              <Journal>
                <Title>{a.get('journal', 'Journal X')}</Title>
                <JournalIssue><PubDate><Year>{a.get('year', '2025')}</Year></PubDate></JournalIssue>
              </Journal>
              <Abstract>{abstract_xml}</Abstract>
            </Article>
          </MedlineCitation>
        </PubmedArticle>
        """)
    xml = f"<PubmedArticleSet>{''.join(partes)}</PubmedArticleSet>"
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.content = xml.encode("utf-8")
    return resp


class TestSearchPubmed:

    def test_busqueda_real_devuelve_resultados_parseados(self):
        esearch = _mock_esearch(["111", "222"], count=2)
        efetch = _mock_efetch_xml([
            {"pmid": "111", "title": "Digestate valorization review", "abstract": "Full abstract text here.", "year": "2024", "journal": "Bioresource Technology"},
            {"pmid": "222", "title": "Struvite recovery from swine manure", "abstract": "Another abstract.", "year": "2023", "journal": "Water Research"},
        ])
        with patch("utils.pubmed.requests.get", side_effect=[esearch, efetch]) as mock_get:
            result = pm.search_pubmed("digestate valorization")

        assert mock_get.call_count == 2
        assert result["total_found"] == 2
        assert len(result["results"]) == 2
        assert result["results"][0]["pmid"] == "111"
        assert result["results"][0]["titulo"] == "Digestate valorization review"
        assert result["results"][0]["url"] == "https://pubmed.ncbi.nlm.nih.gov/111/"
        assert result["source"] == "pubmed"

    def test_sin_resultados_no_llama_efetch(self):
        esearch = _mock_esearch([], count=0)
        with patch("utils.pubmed.requests.get", return_value=esearch) as mock_get:
            result = pm.search_pubmed("query sin resultados reales")
        assert mock_get.call_count == 1
        assert result["results"] == []
        assert result["total_found"] == 0

    def test_trunca_abstracts_largos(self):
        esearch = _mock_esearch(["1"], count=1)
        efetch = _mock_efetch_xml([{"pmid": "1", "title": "t", "abstract": "x" * 1000}])
        with patch("utils.pubmed.requests.get", side_effect=[esearch, efetch]):
            result = pm.search_pubmed("query", abstract_max_chars=50)
        assert len(result["results"][0]["resumen"]) <= 51

    def test_error_en_esearch_devuelve_error_claro(self):
        with patch("utils.pubmed.requests.get", side_effect=Exception("timeout")):
            result = pm.search_pubmed("query")
        assert "error" in result
        assert "esearch" in result["error"]
        assert result["results"] == []

    def test_error_en_efetch_devuelve_total_pero_sin_resultados_parseados(self):
        esearch = _mock_esearch(["1"], count=1)
        with patch("utils.pubmed.requests.get", side_effect=[esearch, Exception("boom")]):
            result = pm.search_pubmed("query")
        assert "error" in result
        assert "efetch" in result["error"]
        assert result["total_found"] == 1

    def test_manda_api_key_cuando_esta_configurada(self, monkeypatch):
        monkeypatch.setenv("NCBI_API_KEY", "mi-key-real")
        esearch = _mock_esearch([], count=0)
        with patch("utils.pubmed.requests.get", return_value=esearch) as mock_get:
            pm.search_pubmed("query")
        _, kwargs = mock_get.call_args
        assert kwargs["params"]["api_key"] == "mi-key-real"

    def test_sin_api_key_no_manda_el_parametro(self, monkeypatch):
        monkeypatch.delenv("NCBI_API_KEY", raising=False)
        esearch = _mock_esearch([], count=0)
        with patch("utils.pubmed.requests.get", return_value=esearch) as mock_get:
            pm.search_pubmed("query")
        _, kwargs = mock_get.call_args
        assert "api_key" not in kwargs["params"]


@pytest.mark.integration
class TestIntegration:

    def test_search_pubmed_query_real(self):
        result = pm.search_pubmed("digestate valorization value-added products", max_results=5)
        assert "error" not in result
        assert result["total_found"] > 0
        assert len(result["results"]) > 0
