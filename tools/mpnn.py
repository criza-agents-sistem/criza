"""
ML-based protein sequence design via ProteinMPNN.

ProteinMPNN (Dauparas et al., Science 2022) designs protein sequences given
a 3D backbone structure. Unlike rule-based approaches, it explores the full
sequence space compatible with the backbone — producing diverse candidates
that may have improved thermostability properties.

How it works:
  1. Takes a PDB file (backbone from ESMFold predict_structure)
  2. Runs ProteinMPNN: message-passing neural network trained on 128k+ PDB structures
  3. Returns N designed sequences ranked by structural compatibility score
     (score = negative log-likelihood; lower = better fit to the backbone)

Setup required (one-time, outside Docker base image):
  git clone https://github.com/dauparas/ProteinMPNN.git ~/ProteinMPNN
  pip install torch --index-url https://download.pytorch.org/whl/cpu
  echo "PROTEINMPNN_PATH=/root/ProteinMPNN" >> .env  (or full path)
  docker compose build

The tool fails gracefully with setup instructions if ProteinMPNN is not found.
Fallback: use design_variants (rule-based) which works without additional setup.

Reference:
  Dauparas et al. (2022). Robust deep learning–based protein sequence design
  using ProteinMPNN. Science, 378(6615), 49-56.
  https://doi.org/10.1126/science.add2187
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional


def design_variants_mpnn(
    pdb_path: str,
    protein_name: str,
    n_sequences: int = 10,
    temperature: float = 0.1,
) -> dict:
    """
    Design protein sequence variants from structure using ProteinMPNN.

    Takes a PDB file (from predict_structure) and generates diverse sequences
    optimized by a neural network for compatibility with that backbone.

    Args:
        pdb_path: Path to PDB file from predict_structure output
        protein_name: Protein name for reference
        n_sequences: Number of sequences to generate (default 10, max 50)
        temperature: Sampling temperature.
            0.1 → conservative (close to native-like, higher accuracy)
            0.3 → balanced
            1.0 → maximum diversity (explore more of sequence space)

    Returns:
        dict with designed sequences ranked by score, compatible with compare_variants.
        Returns error dict with setup_instructions if ProteinMPNN is not installed.
    """
    # ── Validate inputs ───────────────────────────────────────────────────────
    pdb_path = Path(pdb_path)
    if not pdb_path.exists():
        return {
            "protein_name": protein_name,
            "success":      False,
            "error":        f"PDB file not found: {pdb_path}",
            "hint":         "Run predict_structure first to generate the PDB file.",
        }

    n_sequences = max(1, min(n_sequences, 50))
    temperature = max(0.01, min(temperature, 1.0))

    # ── Locate ProteinMPNN ────────────────────────────────────────────────────
    mpnn_path = _find_proteinmpnn()
    if mpnn_path is None:
        return {
            "protein_name": protein_name,
            "success":      False,
            "error":        "ProteinMPNN not installed or PROTEINMPNN_PATH not set.",
            "setup_instructions": (
                "ProteinMPNN requires a one-time setup (outside Docker base image):\n"
                "\n"
                "Step 1 — Clone the repo:\n"
                "  git clone https://github.com/dauparas/ProteinMPNN.git ~/ProteinMPNN\n"
                "\n"
                "Step 2 — Install PyTorch (CPU-only, ~500MB):\n"
                "  pip install torch --index-url https://download.pytorch.org/whl/cpu\n"
                "\n"
                "Step 3 — Add path to .env:\n"
                "  PROTEINMPNN_PATH=/root/ProteinMPNN\n"
                "\n"
                "Step 4 — Rebuild Docker container:\n"
                "  docker compose build\n"
                "\n"
                "In Docker (alternative):\n"
                "  Mount the cloned repo as a volume in docker-compose.yml\n"
                "  and set PROTEINMPNN_PATH in the service environment.\n"
            ),
            "fallback": (
                "Use design_variants tool for rule-based thermostabilization "
                "(proline substitutions, consensus mutations) — no extra setup needed."
            ),
        }

    run_script = mpnn_path / "protein_mpnn_run.py"
    if not run_script.exists():
        return {
            "protein_name": protein_name,
            "success":      False,
            "error":        f"protein_mpnn_run.py not found in {mpnn_path}. Verify PROTEINMPNN_PATH.",
        }

    # ── Run ProteinMPNN ───────────────────────────────────────────────────────
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        cmd = [
            sys.executable, str(run_script),
            "--pdb_path",           str(pdb_path),
            "--out_folder",         str(tmp_path),
            "--num_seq_per_target", str(n_sequences),
            "--sampling_temp",      str(temperature),
            "--seed",               "37",       # Reproducible results
            "--batch_size",         "1",        # Safe for CPU inference
        ]

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,        # 10 min max (CPU inference is slow for many sequences)
                cwd=str(mpnn_path), # Run from ProteinMPNN dir (relative imports)
            )
        except subprocess.TimeoutExpired:
            return {
                "protein_name": protein_name,
                "success":      False,
                "error":        "ProteinMPNN timed out (>10 min). Try reducing n_sequences.",
                "hint":         "CPU inference is slow. Start with n_sequences=5.",
            }
        except FileNotFoundError:
            return {
                "protein_name": protein_name,
                "success":      False,
                "error":        "Python executable not found. Check environment in container.",
            }

        if proc.returncode != 0:
            return {
                "protein_name": protein_name,
                "success":      False,
                "error":        f"ProteinMPNN exited with code {proc.returncode}",
                "stderr":       proc.stderr[-1000:] if proc.stderr else "(no stderr)",
                "hint": (
                    "Common causes:\n"
                    "  - PyTorch not installed: pip install torch --index-url https://download.pytorch.org/whl/cpu\n"
                    "  - Corrupted PDB file: re-run predict_structure\n"
                    "  - Wrong PROTEINMPNN_PATH: should point to the cloned repo root"
                ),
            }

        # ── Parse FASTA output ────────────────────────────────────────────────
        seqs_dir = tmp_path / "seqs"
        fasta_files = sorted(seqs_dir.glob("*.fa")) if seqs_dir.exists() else []

        if not fasta_files:
            return {
                "protein_name": protein_name,
                "success":      False,
                "error":        "ProteinMPNN ran but produced no FASTA output in seqs/ folder.",
                "stdout":       proc.stdout[-500:] if proc.stdout else "",
            }

        sequences = _parse_mpnn_fasta(fasta_files[0])

    if not sequences:
        return {
            "protein_name": protein_name,
            "success":      False,
            "error":        "Could not parse sequences from ProteinMPNN FASTA output.",
        }

    # ── Separate wildtype (first entry) from designed sequences ──────────────
    # ProteinMPNN always writes the original sequence first with its score
    wildtype_entry = None
    designed = sequences

    if sequences and "sample" not in sequences[0]["header"].lower():
        # First entry is likely the original; remaining are designed
        wildtype_entry = sequences[0]
        designed = sequences[1:] if len(sequences) > 1 else sequences

    # Sort designed sequences by score (lower = better)
    designed.sort(key=lambda x: x["score"])

    # ── Format as variant objects ─────────────────────────────────────────────
    wt_seq = wildtype_entry["sequence"] if wildtype_entry else ""

    variants = []
    for i, seq_data in enumerate(designed):
        mutations = _diff_sequences(wt_seq, seq_data["sequence"]) if wt_seq else []
        n_mutations = len(mutations)

        variants.append({
            "variant_id":         f"MPNN_{i + 1:02d}_T{temperature}",
            "strategy":           "ProteinMPNN (ML-based sequence design)",
            "sequence":           seq_data["sequence"],
            "mpnn_score":         round(seq_data["score"], 4),
            "global_score":       round(seq_data.get("global_score", seq_data["score"]), 4),
            "temperature":        temperature,
            "rank":               i + 1,
            "mutations":          mutations,
            "n_mutations":        n_mutations,
            "predicted_delta_Tm": "Unknown — validate via ESMFold + DSF",
            "confidence":         _score_to_confidence(seq_data["score"]),
            "rationale": (
                f"ProteinMPNN-designed sequence from backbone {pdb_path.name}. "
                f"MPNN score: {seq_data['score']:.3f} (lower = better fit to structure). "
                f"{'%d mutation%s vs. wildtype.' % (n_mutations, 's' if n_mutations != 1 else '') if wt_seq else 'Sequence differences not computed (no wildtype reference).'} "
                f"Sampling temperature {temperature}: "
                f"{'conservative, favors native-like sequences' if temperature <= 0.1 else 'moderate diversity' if temperature <= 0.3 else 'high diversity, broader sequence space exploration'}."
            ),
            "wet_lab_validation": (
                "1. Codon-optimize for expression host (E. coli/Pichia) and synthesize gene. "
                "2. Express under same conditions as wildtype. "
                "3. Circular dichroism (CD) to confirm correct secondary structure. "
                "4. DSF (differential scanning fluorimetry) to measure Tm vs. wildtype. "
                "5. Functional assay specific to the protein (bioactivity, binding, enzyme activity)."
            ),
        })

    # ── Build result ──────────────────────────────────────────────────────────
    best = variants[0]
    n_top = min(3, len(variants))

    return {
        "protein_name":      protein_name,
        "success":           True,
        "pdb_used":          str(pdb_path),
        "temperature":       temperature,
        "n_sequences":       len(variants),
        "variants_designed": len(variants),
        "variants":          variants,
        "wildtype_mpnn_score": round(wildtype_entry["score"], 4) if wildtype_entry else None,
        "best_variant": {
            "variant_id": best["variant_id"],
            "mpnn_score": best["mpnn_score"],
            "n_mutations": best["n_mutations"],
        },
        "next_step": (
            f"Run compare_variants with the top {n_top} MPNN sequences "
            "to validate via ESMFold. Select variants with BOTH lower MPNN score "
            "AND higher pLDDT than wildtype as primary wet lab candidates."
        ),
        "note": (
            "ProteinMPNN score reflects structural compatibility, not directly Tm. "
            "Lower score = sequence more compatible with the given backbone. "
            "Combine with ESMFold pLDDT comparison (compare_variants) for best candidates. "
            "Final thermostability improvement requires experimental validation (DSF, CD)."
        ),
    }


# ──────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────

def _find_proteinmpnn() -> Optional[Path]:
    """
    Locate ProteinMPNN installation.
    Checks env var first, then common installation paths.
    """
    # 1. Explicit env var
    env_path = os.getenv("PROTEINMPNN_PATH", "").strip()
    if env_path:
        p = Path(env_path)
        if p.exists() and (p / "protein_mpnn_run.py").exists():
            return p
        # Path set but not valid — report it instead of silently falling through
        return None

    # 2. Common installation locations (auto-detect)
    candidates = [
        Path.home() / "ProteinMPNN",
        Path("/opt/ProteinMPNN"),
        Path("/app/ProteinMPNN"),
        Path(__file__).parent.parent / "ProteinMPNN",
    ]
    for p in candidates:
        if p.exists() and (p / "protein_mpnn_run.py").exists():
            return p

    return None


def _parse_mpnn_fasta(fasta_path: Path) -> list[dict]:
    """
    Parse ProteinMPNN FASTA output file.

    ProteinMPNN FASTA header format:
    >protein, score=0.1234, global_score=0.4567, fixed_chains=, designed_chains=A, ...
    SEQUENCEHERE
    """
    sequences = []

    try:
        content = fasta_path.read_text(encoding="utf-8")
        blocks = content.strip().split("\n>")

        for i, block in enumerate(blocks):
            if i == 0 and block.startswith(">"):
                block = block[1:]  # Remove leading >

            lines = block.strip().split("\n")
            if len(lines) < 2:
                continue

            header = lines[0].strip()
            sequence = "".join(lines[1:]).strip().upper()

            if not sequence or not all(c.isalpha() for c in sequence):
                continue  # Skip empty or malformed sequences

            # Parse score and global_score from header
            score = 9999.0
            global_score = 9999.0

            for part in header.split(","):
                part = part.strip()
                if part.startswith("score="):
                    try:
                        score = float(part[6:])
                    except ValueError:
                        pass
                elif part.startswith("global_score="):
                    try:
                        global_score = float(part[13:])
                    except ValueError:
                        pass

            sequences.append({
                "header":       header,
                "sequence":     sequence,
                "score":        score,
                "global_score": global_score,
            })

    except Exception:
        pass

    return sequences


def _score_to_confidence(score: float) -> str:
    """Map ProteinMPNN score to human-readable confidence label."""
    if score < 0.5:
        return "High — strong structural compatibility (score < 0.5)"
    elif score < 1.0:
        return "Medium-High — good structural compatibility (score 0.5–1.0)"
    elif score < 1.5:
        return "Medium — moderate structural compatibility (score 1.0–1.5)"
    else:
        return "Low — weak structural compatibility (score > 1.5); consider higher temperature"


def _diff_sequences(wildtype: str, designed: str) -> list[dict]:
    """
    Compute amino acid differences between wildtype and designed sequence.

    Returns list of {position (1-indexed), from, to} for each substitution.
    Returns empty list if sequences have different lengths (indels not handled).
    """
    if not wildtype or len(wildtype) != len(designed):
        return []

    return [
        {"position": i + 1, "from": wt, "to": des}
        for i, (wt, des) in enumerate(zip(wildtype, designed))
        if wt != des
    ]
