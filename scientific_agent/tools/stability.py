"""
Protein thermal stability analysis tool.

Takes per-residue pLDDT scores from ESMFold and the protein sequence to:
1. Identify "weak regions" — stretches of low-confidence residues that are
   the first to unfold under thermal stress.
2. Recommend specific engineering strategies to increase thermostability
   at those positions (proline substitutions, disulfide bonds, salt bridges,
   hydrophobic core packing).

No external API required — pure analysis of ESMFold output.
"""

from typing import Optional


# pLDDT threshold below which a residue is considered flexible/unstable
LOW_CONFIDENCE_THRESHOLD = 70
# Minimum consecutive low-pLDDT residues to flag as a "weak region"
MIN_REGION_LENGTH = 4


def analyze_stability(
    sequence: str,
    per_residue_plddt: list[float],
    protein_name: str,
    avg_plddt: Optional[float] = None,
) -> dict:
    """
    Analyze protein thermal stability from ESMFold per-residue pLDDT scores.

    Args:
        sequence: Amino acid sequence (single-letter code, must match pLDDT length)
        per_residue_plddt: Per-residue pLDDT scores from ESMFold (0-100 scale)
        protein_name: Protein name for reference
        avg_plddt: Average pLDDT (optional, computed if not provided)

    Returns:
        dict with weak regions, engineering strategies, and thermostability assessment
    """
    sequence = sequence.strip().upper()
    scores = per_residue_plddt

    if len(sequence) != len(scores):
        # Truncate to shortest (sequence may have been truncated for ESMFold)
        min_len = min(len(sequence), len(scores))
        sequence = sequence[:min_len]
        scores = scores[:min_len]

    if avg_plddt is None:
        avg_plddt = round(sum(scores) / len(scores), 2) if scores else 0.0

    # ── 1. Identify weak regions ──────────────────────────────────────────────
    weak_regions = []
    in_region = False
    region_start = 0

    for i, (aa, score) in enumerate(zip(sequence, scores)):
        if score < LOW_CONFIDENCE_THRESHOLD:
            if not in_region:
                in_region = True
                region_start = i
        else:
            if in_region:
                region_len = i - region_start
                if region_len >= MIN_REGION_LENGTH:
                    weak_regions.append({
                        "start": region_start + 1,  # 1-indexed for biologists
                        "end": i,
                        "length": region_len,
                        "sequence": sequence[region_start:i],
                        "avg_plddt": round(
                            sum(scores[region_start:i]) / region_len, 2
                        ),
                        "residues": [
                            {"pos": region_start + j + 1, "aa": sequence[region_start + j], "plddt": round(scores[region_start + j], 2)}
                            for j in range(region_len)
                        ],
                    })
                in_region = False

    # Close last region if still open at end of sequence
    if in_region:
        region_len = len(sequence) - region_start
        if region_len >= MIN_REGION_LENGTH:
            weak_regions.append({
                "start": region_start + 1,
                "end": len(sequence),
                "length": region_len,
                "sequence": sequence[region_start:],
                "avg_plddt": round(
                    sum(scores[region_start:]) / region_len, 2
                ),
                "residues": [
                    {"pos": region_start + j + 1, "aa": sequence[region_start + j], "plddt": round(scores[region_start + j], 2)}
                    for j in range(region_len)
                ],
            })

    # ── 2. Engineering strategies per region ─────────────────────────────────
    strategies = []

    for region in weak_regions:
        region_strategies = []
        seq = region["sequence"]
        start = region["start"]

        # Strategy A: Proline substitution
        # Prolines reduce backbone entropy → increase Tm by 1-3°C per substitution
        # Best at: loop positions, NOT alpha-helix (breaks helix), NOT beta-sheet (distorts)
        # Target: non-Pro residues in flexible loops (Gly is especially good target)
        pro_targets = [
            {"pos": start + i, "aa": aa}
            for i, aa in enumerate(seq)
            if aa in ("G", "A", "S", "T") and aa != "P"
        ]
        if pro_targets:
            region_strategies.append({
                "strategy": "Proline substitution",
                "mechanism": "Reduces backbone conformational entropy, stabilizes loop regions",
                "expected_delta_Tm": "+1 to +3°C per substitution",
                "target_positions": pro_targets[:3],  # Top 3 candidates
                "note": "Validate that positions are in loops, not helices or sheets (check PDB structure)",
            })

        # Strategy B: Disulfide bond engineering
        # Pairs of Cys residues form S-S bonds → significant stabilization (+5-15°C)
        # Requires: oxidizing environment in the expression system
        # Best when: two flexible regions are spatially close in the folded structure
        if len(weak_regions) >= 2 and region == weak_regions[0]:
            region_strategies.append({
                "strategy": "Disulfide bond engineering",
                "mechanism": "Covalent crosslink between flexible regions locks structure",
                "expected_delta_Tm": "+5 to +15°C per disulfide bond",
                "candidate_pairs": "Introduce Cys at spatially proximal positions in weak regions (verify distance < 6Å in PDB)",
                "note": "Requires oxidizing fermentation conditions or in vitro refolding. Verify with Disulfide by Design 2.0 tool.",
            })

        # Strategy C: Salt bridge optimization
        # Oppositely charged residues at close spatial distance stabilize structure
        # Effective especially at high temperatures (electrostatic interactions strengthen)
        charge_pos = [
            {"pos": start + i, "aa": aa, "charge": "+" if aa in ("K", "R", "H") else "-"}
            for i, aa in enumerate(seq)
            if aa in ("K", "R", "H", "D", "E")
        ]
        if len(charge_pos) >= 2:
            region_strategies.append({
                "strategy": "Salt bridge optimization",
                "mechanism": "Engineered electrostatic interactions between charged residues",
                "expected_delta_Tm": "+1 to +5°C",
                "candidate_residues": charge_pos[:4],
                "note": "Verify spatial proximity in PDB structure (< 4Å between charged groups)",
            })

        strategies.append({
            "region": f"{region['start']}–{region['end']}",
            "region_sequence": seq,
            "avg_plddt": region["avg_plddt"],
            "engineering_strategies": region_strategies,
        })

    # ── 3. Overall thermostability assessment ─────────────────────────────────
    if avg_plddt >= 80 and len(weak_regions) == 0:
        stability_assessment = "High baseline stability — protein likely tolerates moderate thermal stress. Engineering may push Tm significantly higher."
        engineering_priority = "Medium — protein is already relatively stable; targeted improvements have high success probability"
    elif avg_plddt >= 70 and len(weak_regions) <= 2:
        stability_assessment = "Moderate baseline stability with identifiable weak regions. Good candidate for targeted thermostabilization."
        engineering_priority = "High — clear targets identified; each improvement has meaningful impact"
    else:
        stability_assessment = "Low baseline stability with multiple flexible regions. Significant engineering required."
        engineering_priority = "High — multiple interventions needed; consider consensus sequence approach or directed evolution as alternative"

    # ── 4. Recommended next step ──────────────────────────────────────────────
    if weak_regions:
        next_step = (
            f"Run design_variants tool with the PDB structure to generate thermostable candidates. "
            f"Focus ProteinMPNN on redesigning {len(weak_regions)} weak region(s): "
            + ", ".join(f"positions {r['start']}–{r['end']}" for r in weak_regions)
        )
    else:
        next_step = (
            "Protein shows good baseline stability. Run design_variants to explore sequence space "
            "around flexible positions for marginal stability improvements."
        )

    return {
        "protein_name":          protein_name,
        "analyzed_length":       len(sequence),
        "avg_plddt":             avg_plddt,
        "n_weak_regions":        len(weak_regions),
        "weak_regions":          weak_regions,
        "engineering_strategies": strategies,
        "stability_assessment":  stability_assessment,
        "engineering_priority":  engineering_priority,
        "recommended_next_step": next_step,
        "note": (
            f"Analysis based on ESMFold pLDDT scores (threshold: <{LOW_CONFIDENCE_THRESHOLD} = flexible/unstable). "
            f"Found {len(weak_regions)} weak region(s) of ≥{MIN_REGION_LENGTH} consecutive low-confidence residues. "
            "Spatial validation of all strategies requires inspection of the PDB structure."
        ),
    }
