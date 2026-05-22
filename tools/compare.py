"""
Variant comparison tool.

Runs ESMFold on each designed variant and compares pLDDT profiles against
the wildtype to rank which variants are predicted to be better structured
(and thus more thermostable) than the original protein.

This is the validation step in the v1 pipeline:
  analyze_stability → design_variants → compare_variants → Brief
"""

import time
from tools.esmfold import predict_structure


def compare_variants(
    wildtype_sequence: str,
    wildtype_plddt: float,
    variants: list[dict],
    protein_name: str,
    max_variants: int = 5,
) -> dict:
    """
    Validate designed variants by comparing ESMFold pLDDT against wildtype.

    Args:
        wildtype_sequence: Original protein sequence
        wildtype_plddt: Average pLDDT of wildtype from previous ESMFold run
        variants: List of variant dicts from design_variants output
        protein_name: Protein name for reference
        max_variants: Maximum number of variants to run through ESMFold (API rate limit)

    Returns:
        dict with ranked variants, pLDDT comparison, and lab recommendations
    """
    results = []
    variants_to_test = variants[:max_variants]

    for i, variant in enumerate(variants_to_test):
        variant_id = variant.get("variant_id", f"variant_{i+1}")
        variant_seq = variant.get("sequence", "")

        if not variant_seq:
            continue

        # Rate limiting — ESM Atlas public API is sensitive to rapid sequential calls
        if i > 0:
            time.sleep(3)

        # Run ESMFold on variant (truncated to same length as wildtype analysis)
        fold_result = predict_structure(
            sequence=variant_seq,
            protein_name=f"{protein_name} | {variant_id}",
        )

        if not fold_result.get("structure_obtained"):
            results.append({
                "variant_id":     variant_id,
                "strategy":       variant.get("strategy", "unknown"),
                "mutations":      variant.get("mutations", []),
                "plddt_obtained": False,
                "error":          fold_result.get("error", "ESMFold failed"),
                "predicted_delta_Tm": variant.get("predicted_delta_Tm"),
            })
            continue

        variant_plddt = fold_result["avg_plddt"]
        delta_plddt = round(variant_plddt - wildtype_plddt, 2)

        # Interpretation of pLDDT delta
        if delta_plddt >= 5:
            plddt_verdict = "Significantly better than wildtype — strong thermostability candidate"
            priority = 1
        elif delta_plddt >= 2:
            plddt_verdict = "Moderately better than wildtype — good candidate for validation"
            priority = 2
        elif delta_plddt >= -1:
            plddt_verdict = "Similar to wildtype — mutation may be neutral; test experimentally"
            priority = 3
        else:
            plddt_verdict = "Worse than wildtype — mutation likely destabilizing; deprioritize"
            priority = 4

        results.append({
            "variant_id":               variant_id,
            "strategy":                 variant.get("strategy"),
            "mutations":                variant.get("mutations", []),
            "plddt_obtained":           True,
            "wildtype_plddt":           wildtype_plddt,
            "variant_plddt":            variant_plddt,
            "delta_plddt":              delta_plddt,
            "plddt_verdict":            plddt_verdict,
            "priority":                 priority,
            "predicted_delta_Tm":       variant.get("predicted_delta_Tm"),
            "wet_lab_validation":       variant.get("wet_lab_validation"),
            "rationale":                variant.get("rationale"),
        })

    # Sort by priority (best first), then by delta_plddt descending
    results.sort(key=lambda x: (x.get("priority", 5), -x.get("delta_plddt", -99)))

    # Top candidates for wet lab
    lab_candidates = [r for r in results if r.get("priority", 5) <= 2]
    deprioritized = [r for r in results if r.get("priority", 5) >= 4]

    # Summary
    if lab_candidates:
        best = lab_candidates[0]
        summary = (
            f"Best variant: {best['variant_id']} — "
            f"pLDDT {best.get('variant_plddt', '?')} vs wildtype {wildtype_plddt} "
            f"(Δ{best.get('delta_plddt', '?'):+.2f}). "
            f"Predicted thermostability improvement: {best.get('predicted_delta_Tm', 'unknown')}."
        )
    else:
        summary = "No variants showed clear improvement over wildtype in structural prediction. Consider broader sequence space exploration or directed evolution."

    return {
        "protein_name":         protein_name,
        "wildtype_plddt":       wildtype_plddt,
        "variants_tested":      len(results),
        "results":              results,
        "lab_candidates":       [r["variant_id"] for r in lab_candidates],
        "deprioritized":        [r["variant_id"] for r in deprioritized],
        "summary":              summary,
        "lab_recommendation": (
            f"Synthesize and experimentally validate top {min(3, len(lab_candidates))} candidate(s): "
            + ", ".join(r["variant_id"] for r in lab_candidates[:3])
            + ". Measure Tm by DSF (differential scanning fluorimetry) and confirm functional activity "
            "(antimicrobial assay or iron-binding capacity for lactoferrin)."
            if lab_candidates else
            "No clear computational winner. Recommend experimental screening of all variants or pivoting to directed evolution."
        ),
        "note": (
            "pLDDT comparison is a proxy for structural quality, not a direct Tm measurement. "
            "Higher pLDDT in a variant indicates more confident/stable structure prediction, "
            "which correlates with thermostability but must be confirmed experimentally. "
            "ESMFold analyzes only the first 200 aa — variants with mutations beyond position 200 "
            "are not reflected in the pLDDT comparison."
        ),
    }
