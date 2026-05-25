"""
ESMFold local structure prediction — SEB-79

Runs ESMFold (Meta) locally via fair-esm package.
No length limit, no API dependency, no timeouts.

Requirements:
    pip install fair-esm torch
    GPU recommended (Lambda Labs A10 24GB): ~30s per protein
    CPU fallback: ~20-30 min per protein for long sequences

Install ESMFold model weights (auto-downloaded on first run, ~2.5 GB):
    import esm; esm.pretrained.esmfold_v1()

Output interface is identical to predict_structure() for pipeline compatibility.
The only differences: no truncation, and 'method': 'local' in the output.
"""

from pathlib import Path


def _check_dependencies() -> tuple[bool, str]:
    """
    Check if fair-esm and torch are installed and importable.

    Returns:
        (available: bool, error_message: str)
    """
    try:
        import torch  # noqa: F401
    except ImportError:
        return False, "torch not installed — run: pip install torch"
    try:
        import esm  # noqa: F401
    except ImportError:
        return False, "fair-esm not installed — run: pip install fair-esm"
    return True, ""


def _is_gpu_available() -> bool:
    """Return True if CUDA GPU is available."""
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


def predict_structure_local(sequence: str, protein_name: str) -> dict:
    """
    Predict protein 3D structure using ESMFold running locally.

    Same interface as predict_structure() in esmfold.py, but:
    - No length limit — analyzes the full sequence
    - No external API dependency
    - GPU recommended; CPU fallback is very slow for long sequences

    Args:
        sequence:     Amino acid sequence in single-letter code (full length)
        protein_name: Name for reference

    Returns:
        dict compatible with predict_structure() output.
        If fair-esm/torch not installed: returns structure_obtained=False
        with setup_instructions instead of raising an exception.
    """
    available, error_msg = _check_dependencies()
    if not available:
        return {
            "protein_name":       protein_name,
            "structure_obtained": False,
            "error":              error_msg,
            "setup_instructions": (
                "Install dependencies for ESMFold local:\n"
                "  pip install fair-esm torch\n\n"
                "GPU recommended (A10 24GB on Lambda Labs):\n"
                "  - Cost: ~$0.60/hr on-demand\n"
                "  - Speed: ~30s per protein\n"
                "  - Setup: see docs/ONBOARDING.md — Lambda Labs section\n\n"
                "CPU fallback (no GPU):\n"
                "  - Speed: ~20-30 min per protein for sequences > 400 aa\n"
                "  - No additional setup required beyond pip install\n\n"
                "Model weights (~2.5 GB) are downloaded automatically on first run."
            ),
            "fallback": (
                "predict_structure() using ESM Atlas public API — "
                "limited to first 200 aa but no local setup required"
            ),
        }

    import esm
    import torch

    sequence = sequence.strip().upper()
    original_length = len(sequence)

    use_gpu = _is_gpu_available()
    device_label = "GPU (CUDA)" if use_gpu else "CPU (slow — GPU recommended for sequences > 200 aa)"

    try:
        # Load model — cached in memory after first call within the same process.
        # Weights are downloaded to ~/.cache/torch/hub/ on first run (~2.5 GB).
        model = esm.pretrained.esmfold_v1()
        model = model.eval()
        if use_gpu:
            model = model.cuda()

        # Run prediction — returns PDB string
        with torch.no_grad():
            pdb_content = model.infer_pdb(sequence)

        # Persist PDB to structures/ (downstream tools: ProteinMPNN, FoldX)
        pdb_dir = Path(__file__).parent.parent / "structures"
        pdb_dir.mkdir(exist_ok=True)
        safe_name = "".join(c if c.isalnum() else "_" for c in protein_name)
        pdb_path = pdb_dir / f"{safe_name}_{original_length}aa_local.pdb"
        pdb_path.write_text(pdb_content)

        # Extract pLDDT from B-factor column (columns 60-66 of ATOM lines)
        plddt_scores: list[float] = []
        for line in pdb_content.split("\n"):
            if line.startswith("ATOM"):
                try:
                    val = float(line[60:66].strip())
                    plddt_scores.append(val)
                except ValueError:
                    pass

        # Normalize if returned in 0-1 scale (unlikely for local, but safe)
        if plddt_scores and max(plddt_scores) <= 1.0:
            plddt_scores = [v * 100.0 for v in plddt_scores]

        if not plddt_scores:
            return {
                "protein_name":       protein_name,
                "structure_obtained": False,
                "error":              "Could not parse pLDDT scores from PDB output",
            }

        avg_plddt = round(sum(plddt_scores) / len(plddt_scores), 2)

        # Standard AlphaFold/ESMFold pLDDT interpretation
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

        high_conf = sum(1 for s in plddt_scores if s >= 70)
        pct_high  = round(100 * high_conf / len(plddt_scores), 1)

        return {
            "protein_name":           protein_name,
            "original_length":        original_length,
            "analyzed_length":        original_length,   # full sequence — no truncation
            "truncated":              False,
            "structure_obtained":     True,
            "method":                 "local",
            "device":                 device_label,
            "pdb_path":               str(pdb_path),
            "avg_plddt":              avg_plddt,
            "pct_residues_high_conf": pct_high,
            "confidence_level":       confidence,
            "expression_implication": expression_implication,
            "per_residue_plddt":      [round(v, 2) for v in plddt_scores],
            "note": (
                f"Full sequence analyzed locally ({original_length} aa) — no truncation. "
                f"{pct_high}% of residues have high confidence (pLDDT ≥ 70). "
                f"Computed on {device_label}. PDB saved to {pdb_path}."
            ),
        }

    except Exception as e:
        return {
            "protein_name":       protein_name,
            "structure_obtained": False,
            "error":              f"ESMFold local error: {e}",
        }
