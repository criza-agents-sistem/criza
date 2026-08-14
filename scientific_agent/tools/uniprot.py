"""
UniProt REST API tool.
Retrieves protein sequences, organism info, and functional annotations.
"""

import requests
from typing import Optional


def get_protein_sequence(protein_name: str, organism: Optional[str] = None) -> dict:
    """
    Retrieve protein sequence and metadata from UniProt.

    Args:
        protein_name: Protein name (e.g., 'lactoferrin', 'bovine lactoferrin')
        organism: Optional organism in Latin (e.g., 'Bos taurus')

    Returns:
        dict with top matching proteins, each including sequence and metadata
    """
    base_url = "https://rest.uniprot.org/uniprotkb/search"

    query = protein_name
    if organism:
        query += f" AND organism_name:{organism}"
    # Prefer reviewed (Swiss-Prot) entries
    query += " AND reviewed:true"

    params = {
        "query":  query,
        "format": "json",
        "size":   5,
        "fields": "accession,protein_name,sequence,organism_name,length",
    }

    try:
        resp = requests.get(base_url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return {"error": f"UniProt request failed: {str(e)}"}

    if not data.get("results"):
        # Retry without 'reviewed' filter
        params["query"] = protein_name + (f" AND organism_name:{organism}" if organism else "")
        try:
            resp = requests.get(base_url, params=params, timeout=30)
            data = resp.json()
        except Exception:
            return {"error": f"No protein found for: {protein_name}"}

    results = []
    for entry in data.get("results", [])[:3]:
        seq_obj  = entry.get("sequence", {})
        sequence = seq_obj.get("value", "")
        length   = seq_obj.get("length", 0)

        # Extract recommended name
        prot_desc = entry.get("proteinDescription", {})
        rec_name  = prot_desc.get("recommendedName", {})
        name      = rec_name.get("fullName", {}).get("value", protein_name)

        # Function annotation
        cc_function = ""
        for comment in entry.get("comments", []):
            if comment.get("commentType") == "FUNCTION":
                texts = comment.get("texts", [])
                if texts:
                    cc_function = texts[0].get("value", "")
                break

        # Signal peptide (relevant for secretion in expression systems)
        has_signal_peptide = any(
            f.get("type") == "Signal peptide"
            for f in entry.get("features", [])
        )

        accession = entry.get("primaryAccession", "")
        results.append({
            "accession":         accession,
            "name":              name,
            "organism":          entry.get("organism", {}).get("scientificName", ""),
            "length":            length,
            "sequence":          sequence,
            "function":          cc_function[:500] if cc_function else "Not annotated",
            "has_signal_peptide": has_signal_peptide,
            "url":               f"https://www.uniprot.org/uniprotkb/{accession}",
            "note": (
                f"Sequence length: {length} aa. "
                + ("Has signal peptide — relevant for secretion strategies. " if has_signal_peptide else "")
                + ("Truncate to first 400 aa for ESMFold API." if length > 400 else "Full sequence suitable for ESMFold.")
            ),
        })

    return {
        "protein_queried": protein_name,
        "organism_filter": organism,
        "results":         results,
    }
