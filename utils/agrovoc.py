"""
AGROVOC — utilidad canónica para resolución de términos del tesauro FAO.

Usa la API REST de Skosmos en agrovoc.fao.org.
Endpoint base: https://agrovoc.fao.org/browse/rest/v1/agrovoc

Funciones principales:
  search(term, lang)    → lista de conceptos que coinciden con el término
  get_labels(uri)       → labels en ES + EN para un concepto
  expand_term(term)     → todos los términos de búsqueda útiles para un concepto
                          (prefLabel ES/EN + broader + narrower + related)
"""

import time
import urllib.error
import urllib.request
import urllib.parse
import json
from typing import Optional

_BASE = "https://agrovoc.fao.org/browse/rest/v1/agrovoc"
_HEADERS = {"Accept": "application/json", "User-Agent": "CRIZA-agent/1.0"}
_TIMEOUT = 12
_RETRY_DELAY = 2.0  # segundos entre requests para no superar rate limit


def _get(path: str, params: dict = {}, _retry: int = 3) -> dict:
    url = _BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=_HEADERS)
    for attempt in range(_retry):
        try:
            time.sleep(_RETRY_DELAY if attempt > 0 else 0.3)
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < _retry - 1:
                time.sleep(3.0 * (attempt + 1))
                continue
            raise
    raise RuntimeError(f"AGROVOC: max retries exceeded for {url}")


def search(term: str, lang: str = "es") -> list[dict]:
    """
    Busca conceptos AGROVOC por término.
    Retorna lista de dicts con: uri, prefLabel, lang, altLabels.
    """
    data = _get("/search", {"query": term, "lang": lang, "searchLang": lang})
    results = []
    for item in data.get("results", []):
        results.append({
            "uri": item.get("uri", ""),
            "prefLabel": item.get("prefLabel", ""),
            "altLabel": item.get("altLabel", ""),
            "hiddenLabel": item.get("hiddenLabel", ""),
            "lang": item.get("lang", lang),
        })
    return results


def get_labels(uri: str) -> dict:
    """
    Retorna los labels en ES y EN para un URI de concepto.
    """
    labels = {}
    for lang in ("es", "en", "pt"):
        try:
            data = _get("/label", {"uri": uri, "lang": lang})
            label = data.get("prefLabel")
            if label:
                labels[lang] = label
        except Exception:
            pass
    return labels


def _get_related(endpoint: str, uri: str, lang: str = "es") -> list[dict]:
    """Helper para broader / narrower / related."""
    key = endpoint.lstrip("/")
    data = _get(f"/{key}", {"uri": uri, "lang": lang})
    return [
        {"uri": item.get("uri", ""), "prefLabel": item.get("prefLabel", "")}
        for item in data.get(key, [])
    ]


def expand_term(term: str, lang: str = "es", top_n: int = 1) -> Optional[dict]:
    """
    Dado un término en español, retorna un dict con todos los términos
    de búsqueda útiles: labels ES/EN, broader, narrower, related.

    top_n: cuántos conceptos de la búsqueda expandir (default: 1 — el más relevante).

    Retorna None si no hay resultados.

    Ejemplo de output:
    {
      "uri": "http://aims.fao.org/aos/agrovoc/c_b9625ac6",
      "prefLabel_es": "Garrapata",
      "prefLabel_en": "ticks",
      "search_terms_es": ["Garrapata"],
      "search_terms_en": ["ticks"],
      "broader": [{"uri": "...", "prefLabel": "Artrópodo"}],
      "narrower": [],
      "related": [],
    }
    """
    candidates = search(term, lang=lang)
    search_lang_used = lang

    # Fallback a inglés: AGROVOC requiere tildes exactas en español;
    # si la búsqueda en ES falla, buscamos en EN y usamos get_labels para el ES después.
    if not candidates and lang == "es":
        candidates = search(term, lang="en")
        search_lang_used = "en"

    if not candidates:
        return None

    results = []
    for concept in candidates[:top_n]:
        uri = concept["uri"]
        labels = get_labels(uri)

        # Términos de búsqueda en español desde labels autoritativos
        es_label = labels.get("es") or concept.get("prefLabel") if search_lang_used == "en" else concept.get("prefLabel")
        en_label = labels.get("en") or (concept.get("prefLabel") if search_lang_used == "en" else None)

        es_terms = list(filter(None, [
            es_label,
            concept.get("altLabel") if isinstance(concept.get("altLabel"), str) else None,
            concept.get("hiddenLabel") if isinstance(concept.get("hiddenLabel"), str) else None,
        ]))

        results.append({
            "uri": uri,
            "prefLabel_es": es_label,
            "prefLabel_en": en_label,
            "search_terms_es": list(dict.fromkeys(es_terms)),
            "search_terms_en": [en_label] if en_label else [],
            "broader": _get_related("broader", uri, "es"),
            "narrower": _get_related("narrower", uri, "es"),
            "related": _get_related("related", uri, "es"),
        })

    return results[0] if top_n == 1 else results
