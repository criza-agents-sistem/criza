"""
PubChem PUG REST — utilidad compartida CRIZA.

Base: https://pubchem.ncbi.nlm.nih.gov/rest/pug (sin API key). Base de datos de compuestos
químicos del NCBI — identidad, fórmula, peso molecular, nombre IUPAC, SMILES. Útil para
identificar la química de un producto candidato (ej. "¿qué es exactamente la estruvita?").

Verificado en vivo (2026-08-17): el endpoint de propiedades por nombre responde 200 sin auth,
pero solo con el nombre en inglés — "estruvita" no matchea, "struvite" sí (mismo criterio de
idioma que ya rige search_literature/search_kegg/etc. en el resto del proyecto).
"""

import requests

_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
_TIMEOUT = 15
_PROPERTIES = "MolecularFormula,MolecularWeight,IUPACName,CanonicalSMILES,XLogP"


def search_pubchem(query: str) -> dict:
    """
    Busca un compuesto en PubChem por nombre (en inglés) y trae su identidad química.

    Returns:
        dict con 'cid', 'formula', 'peso_molecular', 'nombre_iupac', 'smiles', 'logp'.
        {"encontrado": False} si no hay match — no es un error, es una respuesta válida
        (el compuesto puede no estar en PubChem con ese nombre).
    """
    url = f"{_BASE}/compound/name/{query}/property/{_PROPERTIES}/JSON"
    try:
        resp = requests.get(url, timeout=_TIMEOUT)
    except Exception as exc:
        return {"error": f"PubChem search falló: {exc}", "query": query}

    if resp.status_code == 404:
        return {"query": query, "encontrado": False, "source": "pubchem"}
    try:
        resp.raise_for_status()
    except Exception as exc:
        return {"error": f"PubChem search falló: {exc}", "query": query}

    data = resp.json()
    props = (data.get("PropertyTable") or {}).get("Properties") or []
    if not props:
        return {"query": query, "encontrado": False, "source": "pubchem"}

    p = props[0]
    return {
        "query": query,
        "encontrado": True,
        "cid": p.get("CID"),
        "formula": p.get("MolecularFormula"),
        "peso_molecular": p.get("MolecularWeight"),
        "nombre_iupac": p.get("IUPACName"),
        "smiles": p.get("CanonicalSMILES"),
        "logp": p.get("XLogP"),
        "source": "pubchem",
    }
