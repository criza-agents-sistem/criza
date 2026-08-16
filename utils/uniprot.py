"""
UniProt REST API — utilidad compartida CRIZA.

Base: https://rest.uniprot.org/uniprotkb/search (sin API key). Búsqueda de proteínas/enzimas
por nombre, con función, organismo, EC number (si aplica) y secuencia.

Copia canónica: criza/utils/uniprot.py. scientific_agent/tools/uniprot.py es una copia previa
con foco en ingeniería de proteínas (secuencia para ESMFold) — se mantiene separada a
propósito (ver scientific_agent/docs, agente inactivo hoy) para no arriesgar ese módulo al
tocarlo; esta copia generaliza el resultado (agrega EC number) para el caso de uso de
evaluación microbiológica/enzimática, no de diseño de proteínas.
"""

import requests
from typing import Optional

_BASE_URL = "https://rest.uniprot.org/uniprotkb/search"
_FIELDS = "accession,protein_name,sequence,organism_name,length,ec,cc_function"
_TIMEOUT = 30


def search_uniprot(query: str, organism: Optional[str] = None, max_results: int = 5) -> dict:
    """
    Busca proteínas/enzimas en UniProt por nombre.

    Args:
        query: nombre de la proteína/enzima (ej. 'methane monooxygenase'), en inglés.
        organism: organismo opcional en latín (ej. 'Methylococcus capsulatus').
        max_results: cantidad de resultados (default 5).

    Returns:
        dict con 'resultados': [{accession, nombre, organismo, ec_number, funcion, longitud, url}]
    """
    q = query
    if organism:
        q += f" AND organism_name:{organism}"
    q_reviewed = q + " AND reviewed:true"

    params = {"query": q_reviewed, "format": "json", "size": max_results, "fields": _FIELDS}
    try:
        resp = requests.get(_BASE_URL, params=params, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        return {"error": f"UniProt request failed: {exc}", "query": query}

    if not data.get("results"):
        params["query"] = q
        try:
            resp = requests.get(_BASE_URL, params=params, timeout=_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            return {"error": f"UniProt request failed: {exc}", "query": query}

    resultados = []
    for entry in data.get("results", [])[:max_results]:
        prot_desc = entry.get("proteinDescription", {})
        rec_name = prot_desc.get("recommendedName", {})
        nombre = rec_name.get("fullName", {}).get("value", query)
        ec_numbers = [e.get("value") for e in rec_name.get("ecNumbers", []) if e.get("value")]

        funcion = ""
        for comment in entry.get("comments", []):
            if comment.get("commentType") == "FUNCTION":
                textos = comment.get("texts", [])
                if textos:
                    funcion = textos[0].get("value", "")
                break

        seq_obj = entry.get("sequence", {})
        accession = entry.get("primaryAccession", "")
        resultados.append({
            "accession": accession,
            "nombre": nombre,
            "organismo": entry.get("organism", {}).get("scientificName", ""),
            "ec_number": ec_numbers[0] if ec_numbers else None,
            "funcion": funcion[:500] if funcion else "No anotada",
            "longitud_aa": seq_obj.get("length", 0),
            "url": f"https://www.uniprot.org/uniprotkb/{accession}",
        })

    return {"query": query, "organismo_filtro": organism, "resultados": resultados, "source": "uniprot"}
