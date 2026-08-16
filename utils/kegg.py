"""
KEGG REST API — utilidad compartida CRIZA.

Base: https://rest.kegg.jp/ (sin API key, sin auth, texto plano tab-separated).
Cubre pathways/module/compound/ko/genome — útil para mapear qué proceso metabólico
(ej. metanogénesis, degradación de un compuesto) o qué organismo/gen participa.

Verificado en vivo (2026-08-16): find/<db>/<query> y get/<entry> responden 200 sin auth.
"""

import requests

_BASE = "https://rest.kegg.jp"
_TIMEOUT = 15
_DATABASES = {"pathway", "module", "compound", "ko", "genome"}


def _parse_find(raw: str) -> list[dict]:
    entradas = []
    for line in raw.strip().splitlines():
        if not line.strip():
            continue
        entry_id, _, nombre = line.partition("\t")
        entradas.append({"id": entry_id.strip(), "nombre": nombre.strip()})
    return entradas


def get_entry(entry_id: str) -> dict:
    """Detalle completo (texto plano KEGG) de una entrada — pathway, module, compound, etc."""
    try:
        resp = requests.get(f"{_BASE}/get/{entry_id}", timeout=_TIMEOUT)
        resp.raise_for_status()
        return {"id": entry_id, "detalle": resp.text.strip()}
    except Exception as exc:
        return {"id": entry_id, "error": str(exc)}


def search_kegg(query: str, database: str = "pathway", max_results: int = 10, fetch_detail_top_n: int = 3) -> dict:
    """
    Busca en KEGG por palabra clave dentro de una base (pathway/module/compound/ko/genome).

    Trae detalle completo (get_entry) de los primeros `fetch_detail_top_n` resultados —
    el find solo devuelve id+nombre, el detalle es lo que da contenido evaluable.
    """
    if database not in _DATABASES:
        return {"error": f"database debe ser una de {sorted(_DATABASES)}, recibido: {database}"}

    try:
        resp = requests.get(f"{_BASE}/find/{database}/{query}", timeout=_TIMEOUT)
        resp.raise_for_status()
    except Exception as exc:
        return {"error": f"KEGG find falló: {exc}", "query": query, "database": database}

    entradas = _parse_find(resp.text)[:max_results]
    for e in entradas[:fetch_detail_top_n]:
        detalle = get_entry(e["id"])
        e["detalle"] = detalle.get("detalle") or detalle.get("error")

    return {
        "query": query,
        "database": database,
        "total_encontrados": len(entradas),
        "resultados": entradas,
        "source": "kegg",
    }
