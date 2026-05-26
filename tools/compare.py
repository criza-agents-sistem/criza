"""
Variant comparison tool.

Corre ESMFold en cada variante diseñada y compara pLDDT vs wildtype
para rankear cuáles variantes son estructuralmente mejores.

v2: usa predict_structure_local (pod RunPod o local) cuando está disponible,
fallback a predict_structure (API pública, 200aa) si no.
"""

import time
from tools.esmfold import predict_structure
from tools.esmfold_local import predict_structure_local, ESMFOLD_POD_URL, _check_dependencies


def _fold(sequence: str, label: str) -> dict:
    """
    Corre ESMFold en la secuencia dada.
    Prioridad: pod HTTP → local → API pública.
    """
    # Intentar local/pod primero (sin límite de longitud)
    local_available = bool(ESMFOLD_POD_URL) or _check_dependencies()[0]
    if local_available:
        result = predict_structure_local(sequence, label)
        if result.get("structure_obtained"):
            return result

    # Fallback a API pública (trunca a 200aa)
    return predict_structure(sequence, label)


def compare_variants(
    wildtype_sequence: str,
    wildtype_plddt: float,
    variants: list[dict],
    protein_name: str,
    max_variants: int = 5,
) -> dict:
    """
    Valida variantes diseñadas comparando pLDDT de ESMFold vs wildtype.

    Args:
        wildtype_sequence: Secuencia original de la proteína
        wildtype_plddt:    pLDDT promedio del wildtype (de predict_structure/_local)
        variants:          Lista de variantes de design_variants
        protein_name:      Nombre de la proteína
        max_variants:      Máximo de variantes a correr (default 5)

    Returns:
        dict con variantes rankeadas y recomendaciones para wet lab
    """
    # Determinar si usamos análisis completo o truncado a 200aa
    using_local = bool(ESMFOLD_POD_URL) or _check_dependencies()[0]
    analysis_note = (
        "Variantes evaluadas con ESMFold completo (sin truncación) via pod/local."
        if using_local else
        "Variantes evaluadas con ESMFold API pública — truncadas a 200aa. "
        "Mutaciones en posiciones > 200 no reflejadas en la comparación."
    )

    results = []
    variants_to_test = variants[:max_variants]

    for i, variant in enumerate(variants_to_test):
        variant_id = variant.get("variant_id", f"variant_{i+1}")
        variant_seq = variant.get("sequence", "")

        if not variant_seq:
            continue

        # Rate limiting entre llamadas secuenciales al pod
        if i > 0:
            time.sleep(2)

        fold_result = _fold(
            sequence=variant_seq,
            label=f"{protein_name} | {variant_id}",
        )

        if not fold_result.get("structure_obtained"):
            results.append({
                "variant_id":        variant_id,
                "strategy":          variant.get("strategy", "unknown"),
                "mutations":         variant.get("mutations", []),
                "plddt_obtained":    False,
                "error":             fold_result.get("error", "ESMFold falló"),
                "predicted_delta_Tm": variant.get("predicted_delta_Tm"),
            })
            continue

        variant_plddt = fold_result["avg_plddt"]
        delta_plddt = round(variant_plddt - wildtype_plddt, 2)

        if delta_plddt >= 5:
            plddt_verdict = "Significativamente mejor que wildtype — candidata fuerte a termoestabilidad"
            priority = 1
        elif delta_plddt >= 2:
            plddt_verdict = "Moderadamente mejor que wildtype — buena candidata para validación"
            priority = 2
        elif delta_plddt >= -1:
            plddt_verdict = "Similar a wildtype — mutación posiblemente neutra; validar experimentalmente"
            priority = 3
        else:
            plddt_verdict = "Peor que wildtype — mutación probablemente desestabilizante; descartar"
            priority = 4

        results.append({
            "variant_id":          variant_id,
            "strategy":            variant.get("strategy"),
            "mutations":           variant.get("mutations", []),
            "plddt_obtained":      True,
            "wildtype_plddt":      wildtype_plddt,
            "variant_plddt":       variant_plddt,
            "delta_plddt":         delta_plddt,
            "plddt_verdict":       plddt_verdict,
            "priority":            priority,
            "predicted_delta_Tm":  variant.get("predicted_delta_Tm"),
            "wet_lab_validation":  variant.get("wet_lab_validation"),
            "rationale":           variant.get("rationale"),
        })

    # Ordenar por prioridad, luego por delta_plddt descendente
    results.sort(key=lambda x: (x.get("priority", 5), -x.get("delta_plddt", -99)))

    lab_candidates = [r for r in results if r.get("priority", 5) <= 2]
    deprioritized  = [r for r in results if r.get("priority", 5) >= 4]

    if lab_candidates:
        best = lab_candidates[0]
        summary = (
            f"Mejor variante: {best['variant_id']} — "
            f"pLDDT {best.get('variant_plddt', '?')} vs wildtype {wildtype_plddt} "
            f"(Δ{best.get('delta_plddt', '?'):+.2f}). "
            f"Mejora de termoestabilidad predicha: {best.get('predicted_delta_Tm', 'desconocido')}."
        )
    else:
        summary = (
            "Ninguna variante mostró mejora clara sobre el wildtype. "
            "Considerar exploración más amplia del espacio de secuencias o evolución dirigida."
        )

    return {
        "protein_name":      protein_name,
        "wildtype_plddt":    wildtype_plddt,
        "variants_tested":   len(results),
        "results":           results,
        "lab_candidates":    [r["variant_id"] for r in lab_candidates],
        "deprioritized":     [r["variant_id"] for r in deprioritized],
        "summary":           summary,
        "lab_recommendation": (
            f"Sintetizar y validar experimentalmente top {min(3, len(lab_candidates))} candidata(s): "
            + ", ".join(r["variant_id"] for r in lab_candidates[:3])
            + ". Medir Tm por DSF (fluorimetría de barrido diferencial) y confirmar "
            "actividad funcional (ensayo antimicrobiano o capacidad de unión a hierro para lactoferrina)."
            if lab_candidates else
            "Sin ganador computacional claro. Recomendado: screening experimental de todas las variantes."
        ),
        "analysis_mode":  "local/pod (secuencia completa)" if using_local else "API pública (200aa)",
        "note":           analysis_note,
    }
