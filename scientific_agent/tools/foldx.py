"""
Thermostability prediction via FoldX.

FoldX calculates the change in free energy of folding (ΔΔG) when mutations
are introduced into a protein structure. From ΔΔG we estimate ΔTm using
the standard approximation: ΔTm ≈ -ΔΔG × 1.7°C·mol/kcal.

FoldX workflow per variant:
  1. RepairPDB  — fixes missing atoms/bonds in the input PDB (run once on WT)
  2. BuildModel — introduces mutations and computes ΔΔG vs. wildtype
  3. Parse      — extract ΔΔG from Average_BuildModel_*.fxout output file

Why FoldX over pLDDT delta:
  ESMFold pLDDT delta (compare_variants) is a structural quality proxy.
  FoldX ΔΔG is a thermodynamic quantity — directly related to protein stability.
  Combined, they give orthogonal evidence for thermostability.

Sign convention (FoldX):
  ΔΔG < 0  →  mutant more stable than wildtype  →  positive ΔTm (good)
  ΔΔG > 0  →  mutant less stable than wildtype  →  negative ΔTm (bad)

Setup required (one-time):
  1. Download FoldX from https://foldxsuite.biocomputing.eu (free academic registration)
  2. Extract the binary to a known path
  3. Add to .env: FOLDX_PATH=/path/to/foldx  (the binary itself, not the directory)

Reference:
  Schymkowitz et al. (2005). The FoldX web server: an online force field.
  Nucleic Acids Research, 33(suppl_2), W382-W388.
  https://doi.org/10.1093/nar/gki387
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional


# Approximation factor: ΔTm (°C) ≈ -ΔΔG (kcal/mol) × TM_FACTOR
# Literature range: 1.0–2.0°C·mol/kcal depending on protein size and Tm.
# We use 1.7 (midpoint) and document the uncertainty explicitly.
TM_FACTOR = 1.7

# FoldX confidence thresholds
STABILIZING_THRESHOLD = -0.5    # kcal/mol — clearly stabilizing
NEUTRAL_LOWER = -0.5
NEUTRAL_UPPER = 0.5             # kcal/mol — neutral range
DESTABILIZING_THRESHOLD = 0.5  # kcal/mol — clearly destabilizing


def predict_tm_change(
    wildtype_pdb: str,
    variants: list[dict],
    protein_name: str,
    wildtype_tm: Optional[float] = None,
) -> dict:
    """
    Predict ΔΔG and estimate ΔTm for designed variants using FoldX.

    Args:
        wildtype_pdb: Path to wildtype PDB file from predict_structure output
        variants: List of variant dicts from design_variants or design_variants_mpnn
                  Each must contain 'mutations': [{'position': int, 'from': str, 'to': str}]
        protein_name: Protein name for reference
        wildtype_tm: Known wildtype Tm from literature (°C), optional.
                     If provided, estimates absolute Tm for each variant.

    Returns:
        dict with ΔΔG and ΔTm estimates per variant, ranked best to worst.
        Returns error dict with setup instructions if FoldX is not installed.
    """
    # ── Validate inputs ───────────────────────────────────────────────────────
    wildtype_pdb = Path(wildtype_pdb)
    if not wildtype_pdb.exists():
        return {
            "protein_name": protein_name,
            "success":      False,
            "error":        f"PDB file not found: {wildtype_pdb}",
            "hint":         "Run predict_structure first to generate the PDB file.",
        }

    if not variants:
        return {
            "protein_name": protein_name,
            "success":      False,
            "error":        "No variants provided. Run design_variants first.",
        }

    # Filter variants that have mutations defined
    testable = [v for v in variants if v.get("mutations")]
    if not testable:
        return {
            "protein_name": protein_name,
            "success":      False,
            "error":        "None of the provided variants have defined mutations (empty 'mutations' list).",
            "hint":         "Use variants from design_variants (rule-based) which always include mutation dicts.",
        }

    # ── Locate FoldX ─────────────────────────────────────────────────────────
    foldx_bin = _find_foldx()
    if foldx_bin is None:
        return {
            "protein_name": protein_name,
            "success":      False,
            "error":        "FoldX binary not found. FOLDX_PATH not set or binary not in standard locations.",
            "setup_instructions": (
                "FoldX requires a one-time registration and download:\n"
                "\n"
                "Step 1 — Register (free for academic use):\n"
                "  https://foldxsuite.biocomputing.eu\n"
                "\n"
                "Step 2 — Download the binary for your OS (Linux/macOS/Windows).\n"
                "  Extract and note the full path to the 'foldx' executable.\n"
                "\n"
                "Step 3 — Add to .env:\n"
                "  FOLDX_PATH=/path/to/foldx\n"
                "  (Point to the binary itself, not the directory)\n"
                "\n"
                "Step 4 — Rebuild Docker container:\n"
                "  docker compose build\n"
                "\n"
                "Note: FoldX does NOT require GPU. CPU-only, runs in seconds per variant.\n"
            ),
            "fallback": (
                "Use compare_variants (ESMFold pLDDT delta) as a proxy for thermostability. "
                "Less precise than ΔΔG but works without additional setup."
            ),
        }

    # ── Run analysis ──────────────────────────────────────────────────────────
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Copy PDB to working dir (FoldX writes output alongside input)
        pdb_copy = tmp_path / wildtype_pdb.name
        shutil.copy2(wildtype_pdb, pdb_copy)

        # Step 1: RepairPDB (run once on wildtype)
        repaired_pdb = _run_repair(foldx_bin, pdb_copy, tmp_path)
        if repaired_pdb is None:
            return {
                "protein_name": protein_name,
                "success":      False,
                "error":        "FoldX RepairPDB failed. The PDB file may be malformed.",
                "hint":         "Try re-running predict_structure to regenerate the PDB.",
            }

        # Step 2: BuildModel for each variant
        results = []
        for variant in testable:
            variant_id = variant.get("variant_id", "unknown")
            mutations = variant.get("mutations", [])

            ddg_result = _run_build_model(
                foldx_bin, repaired_pdb, mutations, tmp_path, variant_id
            )

            if ddg_result is None:
                results.append({
                    "variant_id":       variant_id,
                    "strategy":         variant.get("strategy", "unknown"),
                    "mutations":        mutations,
                    "success":          False,
                    "error":            "FoldX BuildModel failed for this variant.",
                    "hint":             f"Mutation format issue. Check chain assignment for: {mutations}",
                })
                continue

            ddg = ddg_result
            delta_tm_estimate = round(-ddg * TM_FACTOR, 1)

            # Absolute Tm estimate if wildtype Tm is known
            absolute_tm = None
            if wildtype_tm is not None:
                absolute_tm = round(wildtype_tm + delta_tm_estimate, 1)

            verdict, priority = _ddg_verdict(ddg)

            results.append({
                "variant_id":       variant_id,
                "strategy":         variant.get("strategy", "unknown"),
                "mutations":        mutations,
                "success":          True,
                "ddg_kcal_mol":     round(ddg, 3),
                "delta_tm_estimate": delta_tm_estimate,
                "absolute_tm":      absolute_tm,
                "verdict":          verdict,
                "priority":         priority,
                "wet_lab_validation": variant.get("wet_lab_validation", ""),
                "foldx_note": (
                    f"ΔΔG = {ddg:+.3f} kcal/mol. "
                    f"ΔTm ≈ {delta_tm_estimate:+.1f}°C (approximation: ΔTm ≈ -ΔΔG × {TM_FACTOR}). "
                    f"Uncertainty: ±1–2°C. Experimental DSF required for confirmation."
                ),
            })

    # ── Rank and summarize ────────────────────────────────────────────────────
    results.sort(key=lambda x: (x.get("priority", 5), x.get("ddg_kcal_mol", 999)))

    stabilizing = [r for r in results if r.get("success") and r.get("ddg_kcal_mol", 999) < STABILIZING_THRESHOLD]
    destabilizing = [r for r in results if r.get("success") and r.get("ddg_kcal_mol", -999) > DESTABILIZING_THRESHOLD]

    if stabilizing:
        best = stabilizing[0]
        summary = (
            f"Best variant: {best['variant_id']} — "
            f"ΔΔG = {best['ddg_kcal_mol']:+.3f} kcal/mol, "
            f"ΔTm ≈ {best['delta_tm_estimate']:+.1f}°C"
            + (f", estimated Tm ≈ {best['absolute_tm']}°C" if best.get("absolute_tm") else "")
            + "."
        )
    else:
        summary = (
            "No clearly stabilizing variants found (ΔΔG ≥ -0.5 kcal/mol for all). "
            "Consider broader sequence space exploration via ProteinMPNN or directed evolution."
        )

    return {
        "protein_name":        protein_name,
        "success":             True,
        "pdb_used":            str(wildtype_pdb),
        "wildtype_tm":         wildtype_tm,
        "variants_tested":     len(results),
        "results":             results,
        "stabilizing_variants": [r["variant_id"] for r in stabilizing],
        "destabilizing_variants": [r["variant_id"] for r in destabilizing],
        "summary":             summary,
        "lab_recommendation": (
            f"Prioritize {min(3, len(stabilizing))} variant(s) with ΔΔG < -0.5 kcal/mol: "
            + ", ".join(r["variant_id"] for r in stabilizing[:3])
            + ". Validate Tm by DSF. Confirm functional activity after thermostabilization."
            if stabilizing else
            "No clear winner from FoldX. Use pLDDT comparison (compare_variants) as secondary signal."
        ),
        "note": (
            f"ΔTm estimates use approximation ΔTm ≈ -ΔΔG × {TM_FACTOR}°C·mol/kcal "
            "(literature range: 1.0–2.0). Accuracy: ±1–2°C. "
            "FoldX is most reliable for single point mutations; "
            "multi-mutation estimates assume additive effects (epistasis not modeled). "
            "Combine with ESMFold pLDDT delta (compare_variants) for orthogonal evidence."
        ),
    }


# ──────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────

def _find_foldx() -> Optional[Path]:
    """
    Locate FoldX binary.
    Checks FOLDX_PATH env var first, then common locations.
    """
    # 1. Explicit env var (can be path to binary or directory)
    env_path = os.getenv("FOLDX_PATH", "").strip()
    if env_path:
        p = Path(env_path)
        if p.is_file() and os.access(p, os.X_OK):
            return p
        if p.is_dir():
            # Look for foldx binary inside the directory
            for name in ("foldx", "foldx.exe", "foldx5", "foldx5.exe"):
                candidate = p / name
                if candidate.exists():
                    return candidate
        # Path explicitly set but invalid — report as not found (don't silently fall through)
        return None

    # 2. System PATH
    foldx_in_path = shutil.which("foldx") or shutil.which("foldx5")
    if foldx_in_path:
        return Path(foldx_in_path)

    # 3. Common installation locations
    common = [
        Path.home() / "foldx" / "foldx",
        Path.home() / "FoldX" / "foldx",
        Path("/opt/foldx/foldx"),
        Path("/opt/FoldX/foldx"),
        Path("/app/foldx/foldx"),
        Path(__file__).parent.parent / "foldx" / "foldx",
    ]
    for p in common:
        if p.exists():
            return p

    return None


def _mutations_to_foldx(mutations: list[dict], chain: str = "A") -> str:
    """
    Convert mutation list to FoldX individual_list.txt format.

    Input:  [{"position": 1, "from": "G", "to": "P"}, {"position": 10, "from": "M", "to": "L"}]
    Output: "GA1P,MA10L;"

    FoldX format per mutation: {from_aa}{chain}{position}{to_aa}
    Multiple mutations separated by commas, line ends with semicolon.
    """
    parts = []
    for mut in mutations:
        from_aa = mut.get("from", "").strip().upper()
        to_aa = mut.get("to", "").strip().upper()
        position = mut.get("position", 0)
        chain_id = mut.get("chain", chain)

        if not from_aa or not to_aa or not position:
            continue

        parts.append(f"{from_aa}{chain_id}{position}{to_aa}")

    if not parts:
        return ""

    return ",".join(parts) + ";"


def _run_repair(foldx_bin: Path, pdb_path: Path, work_dir: Path) -> Optional[Path]:
    """
    Run FoldX RepairPDB command.

    Returns path to repaired PDB (_Repair.pdb suffix) or None on failure.
    """
    cmd = [
        str(foldx_bin),
        "--command=RepairPDB",
        f"--pdb={pdb_path.name}",
        f"--output-dir={work_dir}",
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(work_dir),
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None

    # Look for repaired PDB
    stem = pdb_path.stem
    repaired = work_dir / f"{stem}_Repair.pdb"

    if repaired.exists():
        return repaired

    # Some FoldX versions use different naming
    alternatives = list(work_dir.glob(f"{stem}*Repair*.pdb"))
    if alternatives:
        return alternatives[0]

    return None


def _run_build_model(
    foldx_bin: Path,
    repaired_pdb: Path,
    mutations: list[dict],
    work_dir: Path,
    variant_id: str,
) -> Optional[float]:
    """
    Run FoldX BuildModel for a single variant.

    Returns ΔΔG in kcal/mol (negative = stabilizing) or None on failure.
    """
    # Write mutation file
    mutation_str = _mutations_to_foldx(mutations)
    if not mutation_str:
        return None

    mutation_file = work_dir / f"individual_list_{variant_id}.txt"
    mutation_file.write_text(mutation_str + "\n", encoding="utf-8")

    cmd = [
        str(foldx_bin),
        "--command=BuildModel",
        f"--pdb={repaired_pdb.name}",
        f"--mutant-file={mutation_file.name}",
        f"--output-dir={work_dir}",
        "--numberOfRuns=1",
        "--out-pdb=false",    # Don't write mutant PDB (saves disk/time)
        "--pdb-dir=.",
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(work_dir),
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None

    # Parse ΔΔG from output file
    stem = repaired_pdb.stem
    fxout_files = list(work_dir.glob(f"Average_BuildModel_{stem}*.fxout"))

    if not fxout_files:
        # Try alternate naming pattern
        fxout_files = list(work_dir.glob("Average_BuildModel_*.fxout"))

    if not fxout_files:
        return None

    ddg = _parse_build_model_output(fxout_files[0])

    # Clean up this variant's mutation file and fxout to avoid conflicts on next run
    mutation_file.unlink(missing_ok=True)
    for f in fxout_files:
        f.unlink(missing_ok=True)

    return ddg


def _parse_build_model_output(fxout_path: Path) -> Optional[float]:
    """
    Parse ΔΔG from FoldX Average_BuildModel output file.

    File format (tab-separated):
      Line 1: header row (Pdb, total energy, ...)
      Line 2: WT energies (Pdb name contains "WT_" prefix)
      Line 3: mutant energies

    ΔΔG = total_energy(mutant) - total_energy(wildtype)
    """
    try:
        lines = fxout_path.read_text(encoding="utf-8").strip().split("\n")

        # Find header line and data lines
        header_idx = None
        for i, line in enumerate(lines):
            if line.startswith("Pdb") or "total energy" in line.lower():
                header_idx = i
                break

        if header_idx is None:
            return None

        data_lines = [l for l in lines[header_idx + 1:] if l.strip() and not l.startswith("#")]

        if len(data_lines) < 2:
            # May have only one data line (some FoldX versions report ΔΔG directly)
            if len(data_lines) == 1:
                cols = data_lines[0].split("\t")
                if len(cols) > 1:
                    try:
                        return float(cols[1])
                    except ValueError:
                        return None
            return None

        # Two data lines: first is WT, second is mutant
        wt_cols = data_lines[0].split("\t")
        mut_cols = data_lines[1].split("\t")

        if len(wt_cols) < 2 or len(mut_cols) < 2:
            return None

        wt_energy = float(wt_cols[1])
        mut_energy = float(mut_cols[1])

        return round(mut_energy - wt_energy, 4)

    except Exception:
        return None


def _ddg_verdict(ddg: float) -> tuple[str, int]:
    """
    Convert ΔΔG value to human-readable verdict and priority rank.

    Returns (verdict_string, priority) where lower priority = better candidate.
    """
    if ddg < -2.0:
        return "Strongly stabilizing (ΔΔG < -2.0 kcal/mol) — top priority", 1
    elif ddg < -0.5:
        return "Stabilizing (ΔΔG -2.0 to -0.5 kcal/mol) — good candidate", 2
    elif ddg <= 0.5:
        return "Neutral (ΔΔG -0.5 to +0.5 kcal/mol) — marginal effect, test experimentally", 3
    elif ddg <= 2.0:
        return "Mildly destabilizing (ΔΔG +0.5 to +2.0 kcal/mol) — deprioritize", 4
    else:
        return "Strongly destabilizing (ΔΔG > +2.0 kcal/mol) — discard", 5
