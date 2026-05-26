"""
ESMFold structure prediction tool.
Uses the public ESM Atlas API (Meta). Free, no auth required.
Limitation: works best with sequences ≤ 400 aa. Longer sequences are truncated.
"""

import requests
from pathlib import Path


MAX_SEQUENCE_LENGTH = 200  # Public API reliable limit (longer sequences time out)


def predict_structure(sequence: str, protein_name: str) -> dict:
    """
    Predict protein 3D structure confidence using ESMFold.

    Args:
        sequence: Amino acid sequence in single-letter code
        protein_name: Name for reference

    Returns:
        dict with pLDDT score, confidence interpretation, and analysis notes
    """
    # Clean sequence
    sequence = sequence.strip().upper()
    original_length = len(sequence)
    truncated = False

    if original_length > MAX_SEQUENCE_LENGTH:
        sequence = sequence[:MAX_SEQUENCE_LENGTH]
        truncated = True

    url = "https://api.esmatlas.com/foldSequence/v1/pdb/"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    try:
        resp = requests.post(url, data=sequence, headers=headers, timeout=120)

        if resp.status_code != 200:
            return {
                "protein_name":     protein_name,
                "original_length":  original_length,
                "structure_obtained": False,
                "error":            f"API returned status {resp.status_code}: {resp.text[:200]}",
                "fallback_note":    "Use ColabFold (https://colab.research.google.com/github/sokrypton/ColabFold) for longer sequences.",
            }

        pdb_content = resp.text

        # Save PDB to disk for downstream tools (ProteinMPNN, stability analysis)
        pdb_dir = Path(__file__).parent.parent / "structures"
        pdb_dir.mkdir(exist_ok=True)
        safe_name = "".join(c if c.isalnum() else "_" for c in protein_name)
        pdb_path = pdb_dir / f"{safe_name}_{len(sequence)}aa.pdb"
        pdb_path.write_text(pdb_content)

        # Extract per-residue pLDDT from B-factor column — CA atoms only (one per residue)
        plddt_scores = []
        for line in pdb_content.split("\n"):
            if line.startswith("ATOM") and " CA " in line:
                try:
                    val = float(line[60:66].strip())
                    plddt_scores.append(val)
                except ValueError:
                    pass

        # ESMFold public API returns pLDDT in 0-1 scale → normalize to 0-100
        if plddt_scores and max(plddt_scores) <= 1.0:
            plddt_scores = [v * 100 for v in plddt_scores]

        if not plddt_scores:
            return {
                "protein_name":     protein_name,
                "structure_obtained": False,
                "error":            "Could not parse pLDDT scores from PDB output",
            }

        avg_plddt = round(sum(plddt_scores) / len(plddt_scores), 2)

        # pLDDT interpretation (AlphaFold / ESMFold standard)
        if avg_plddt >= 90:
            confidence = "Muy alta (≥90) — estructura bien definida, predicción muy confiable"
            expression_implication = "Alta probabilidad de plegamiento correcto en sistema de expresión microbiano"
        elif avg_plddt >= 70:
            confidence = "Alta (70-90) — estructura confiable con posibles regiones flexibles"
            expression_implication = "Plegamiento correcto probable. Verificar regiones de baja confianza"
        elif avg_plddt >= 50:
            confidence = "Media (50-70) — regiones desordenadas o flexibles presentes"
            expression_implication = "Puede haber problemas de solubilidad o agregación. Considerar variantes más estables"
        else:
            confidence = "Baja (<50) — proteína probablemente intrínsecamente desordenada"
            expression_implication = "Alto riesgo de cuerpos de inclusión. Requiere optimización significativa de expresión"

        # Fraction of residues with high confidence
        high_conf = sum(1 for s in plddt_scores if s >= 70)
        pct_high  = round(100 * high_conf / len(plddt_scores), 1)

        return {
            "protein_name":          protein_name,
            "original_length":       original_length,
            "analyzed_length":       len(sequence),
            "truncated":             truncated,
            "structure_obtained":    True,
            "pdb_path":              str(pdb_path),
            "avg_plddt":             avg_plddt,
            "pct_residues_high_conf": pct_high,
            "confidence_level":      confidence,
            "expression_implication": expression_implication,
            "per_residue_plddt":     [round(v, 2) for v in plddt_scores],
            "note": (
                f"Analyzed {'first ' + str(MAX_SEQUENCE_LENGTH) + ' aa (truncated)' if truncated else 'full sequence'}. "
                f"{pct_high}% of residues have high confidence (pLDDT ≥ 70). "
                f"PDB saved to {pdb_path}."
            ),
        }

    except requests.exceptions.Timeout:
        return {
            "protein_name":     protein_name,
            "structure_obtained": False,
            "error":            "Request timed out (120s). Sequence may be too large for public API.",
            "fallback_note":    "Use first 400 aa or run ESMFold locally.",
        }
    except Exception as e:
        return {
            "protein_name":     protein_name,
            "structure_obtained": False,
            "error":            str(e),
        }
