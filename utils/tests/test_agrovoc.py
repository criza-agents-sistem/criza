"""
Tests para criza/utils/agrovoc.py

Unit tests: lógica interna sin llamadas de red (mock de _get).
Integration tests: requieren acceso a AGROVOC API. Correr con: pytest -m integration

La API de AGROVOC (Skosmos REST) está en:
  https://agrovoc.fao.org/browse/rest/v1/agrovoc
Rate limit: ~1 req/segundo. Los unit tests no tocan la red.
"""

import sys
from pathlib import Path

import pytest
from unittest.mock import patch, call

_CRIZA = Path(__file__).parent.parent.parent
if str(_CRIZA) not in sys.path:
    sys.path.insert(0, str(_CRIZA))

import utils.agrovoc as agrovoc


# ──────────────────────────────────────────────
# Fixtures de respuestas mock
# ──────────────────────────────────────────────

MOCK_SEARCH_GARRAPATA = {
    "results": [
        {
            "uri": "http://aims.fao.org/aos/agrovoc/c_b9625ac6",
            "prefLabel": "Garrapata",
            "altLabel": "",
            "hiddenLabel": "",
            "lang": "es",
        }
    ]
}

MOCK_SEARCH_EMPTY = {"results": []}

MOCK_SEARCH_EN_TICKS = {
    "results": [
        {
            "uri": "http://aims.fao.org/aos/agrovoc/c_b9625ac6",
            "prefLabel": "ticks",
            "altLabel": "",
            "hiddenLabel": "",
            "lang": "en",
        }
    ]
}

MOCK_LABEL_ES = {"prefLabel": "Garrapata"}
MOCK_LABEL_EN = {"prefLabel": "ticks"}
MOCK_LABEL_PT = {"prefLabel": "Carrapato"}

MOCK_BROADER = {"broader": [{"uri": "http://aims.fao.org/aos/agrovoc/c_555", "prefLabel": "Artrópodo"}]}
MOCK_NARROWER = {"narrower": []}
MOCK_RELATED = {"related": []}


# ──────────────────────────────────────────────
# UNIT TESTS — sin red
# ──────────────────────────────────────────────

class TestSearch:

    def test_devuelve_lista_de_conceptos(self):
        with patch("utils.agrovoc._get", return_value=MOCK_SEARCH_GARRAPATA):
            results = agrovoc.search("garrapata")
        assert len(results) == 1
        assert results[0]["uri"] == "http://aims.fao.org/aos/agrovoc/c_b9625ac6"
        assert results[0]["prefLabel"] == "Garrapata"

    def test_lista_vacia_si_sin_resultados(self):
        with patch("utils.agrovoc._get", return_value=MOCK_SEARCH_EMPTY):
            results = agrovoc.search("terminoquenoexiste")
        assert results == []

    def test_pasa_lang_correcto(self):
        with patch("utils.agrovoc._get", return_value=MOCK_SEARCH_EMPTY) as mock_get:
            agrovoc.search("pest", lang="en")
            mock_get.assert_called_once_with(
                "/search", {"query": "pest", "lang": "en", "searchLang": "en"}
            )


class TestGetLabels:

    def test_retorna_labels_en_tres_idiomas(self):
        def fake_get(path, params={}):
            lang = params.get("lang")
            return {"prefLabel": {"es": "Garrapata", "en": "ticks", "pt": "Carrapato"}[lang]}

        with patch("utils.agrovoc._get", side_effect=fake_get):
            labels = agrovoc.get_labels("http://aims.fao.org/aos/agrovoc/c_b9625ac6")

        assert labels == {"es": "Garrapata", "en": "ticks", "pt": "Carrapato"}

    def test_omite_idioma_si_falla(self):
        def fake_get(path, params={}):
            if params.get("lang") == "pt":
                raise Exception("timeout")
            return {"prefLabel": "Garrapata" if params.get("lang") == "es" else "ticks"}

        with patch("utils.agrovoc._get", side_effect=fake_get):
            labels = agrovoc.get_labels("http://aims.fao.org/aos/agrovoc/c_b9625ac6")

        assert "es" in labels
        assert "en" in labels
        assert "pt" not in labels


class TestExpandTerm:

    def _setup_mock_get(self, mock_get, search_es=None, search_en=None):
        """Configura _get para retornar respuestas según el path/params."""
        search_es = search_es or MOCK_SEARCH_GARRAPATA
        search_en = search_en or MOCK_SEARCH_EN_TICKS

        def side_effect(path, params={}):
            if path == "/search":
                if params.get("searchLang") == "es":
                    return search_es
                if params.get("searchLang") == "en":
                    return search_en
                return MOCK_SEARCH_EMPTY
            if path == "/label":
                return {"prefLabel": {"es": "Garrapata", "en": "ticks", "pt": "Carrapato"}.get(params.get("lang"), "")}
            if path == "/broader":
                return MOCK_BROADER
            if path == "/narrower":
                return MOCK_NARROWER
            if path == "/related":
                return MOCK_RELATED
            return {}

        mock_get.side_effect = side_effect

    def test_expand_term_encontrado_en_es(self):
        with patch("utils.agrovoc._get") as mock_get:
            self._setup_mock_get(mock_get)
            result = agrovoc.expand_term("garrapata")

        assert result is not None
        assert result["prefLabel_es"] == "Garrapata"
        assert result["prefLabel_en"] == "ticks"
        assert result["uri"] == "http://aims.fao.org/aos/agrovoc/c_b9625ac6"
        assert len(result["broader"]) == 1
        assert result["broader"][0]["prefLabel"] == "Artrópodo"

    def test_expand_term_fallback_a_en_si_es_vacio(self):
        with patch("utils.agrovoc._get") as mock_get:
            self._setup_mock_get(mock_get, search_es=MOCK_SEARCH_EMPTY)
            result = agrovoc.expand_term("biological control")

        assert result is not None
        # Cuando viene del fallback EN, prefLabel_es viene de get_labels
        assert result["prefLabel_es"] == "Garrapata"

    def test_expand_term_retorna_none_si_no_hay_resultados(self):
        with patch("utils.agrovoc._get") as mock_get:
            mock_get.return_value = MOCK_SEARCH_EMPTY
            result = agrovoc.expand_term("xyzzy123nonexistent")

        assert result is None

    def test_expand_term_search_terms_es_sin_duplicados(self):
        mock_search = {
            "results": [{
                "uri": "http://aims.fao.org/aos/agrovoc/c_b9625ac6",
                "prefLabel": "Garrapata",
                "altLabel": "Garrapata",  # duplicado intencional
                "hiddenLabel": "Acaro",
                "lang": "es",
            }]
        }

        def fake_get(path, params={}):
            if path == "/search":
                return mock_search
            if path == "/label":
                return {"prefLabel": {"es": "Garrapata", "en": "ticks"}.get(params.get("lang"), "")}
            return {"broader": [], "narrower": [], "related": []}

        with patch("utils.agrovoc._get", side_effect=fake_get):
            result = agrovoc.expand_term("garrapata")

        # "Garrapata" no debe aparecer dos veces
        assert result["search_terms_es"].count("Garrapata") == 1
        assert "Acaro" in result["search_terms_es"]

    def test_top_n_mayor_a_1_retorna_lista(self):
        mock_search = {
            "results": [
                {"uri": "http://aims.fao.org/aos/agrovoc/c_aaa", "prefLabel": "A", "altLabel": "", "hiddenLabel": "", "lang": "es"},
                {"uri": "http://aims.fao.org/aos/agrovoc/c_bbb", "prefLabel": "B", "altLabel": "", "hiddenLabel": "", "lang": "es"},
            ]
        }

        def fake_get(path, params={}):
            if path == "/search":
                return mock_search
            if path == "/label":
                return {"prefLabel": "label"}
            return {"broader": [], "narrower": [], "related": []}

        with patch("utils.agrovoc._get", side_effect=fake_get):
            result = agrovoc.expand_term("multiple", top_n=2)

        assert isinstance(result, list)
        assert len(result) == 2


# ──────────────────────────────────────────────
# INTEGRATION TESTS — requieren red
# ──────────────────────────────────────────────

@pytest.mark.integration
class TestIntegration:
    """
    Smoke tests contra la API real. Correr con: pytest -m integration
    Estos tests son lentos por los delays de rate limiting.
    """

    def test_search_garrapata_devuelve_resultado(self):
        results = agrovoc.search("garrapata", lang="es")
        assert len(results) > 0
        uris = [r["uri"] for r in results]
        assert any("agrovoc" in u for u in uris)

    def test_expand_term_garrapata_completo(self):
        result = agrovoc.expand_term("garrapata")
        assert result is not None
        assert result["prefLabel_es"] is not None
        assert result["prefLabel_en"] is not None
        assert isinstance(result["broader"], list)
        assert isinstance(result["narrower"], list)
        assert isinstance(result["related"], list)

    def test_expand_term_fallback_en_para_termino_sin_tilde(self):
        # "control biologico" sin tilde — espera resultado via fallback EN
        result = agrovoc.expand_term("control biologico")
        # No garantizamos resultado (puede fallar si AGROVOC no lo encuentra),
        # pero si hay resultado, debe tener estructura válida
        if result is not None:
            assert "uri" in result
            assert "prefLabel_es" in result

    def test_expand_term_none_para_termino_inexistente(self):
        result = agrovoc.expand_term("xyzzy123termino_que_no_existe_en_agrovoc")
        assert result is None
