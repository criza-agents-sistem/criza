"""
Unit tests for tools/variants.py — design_variants()

Pure logic, no external APIs. Always fast.
"""

import pytest
from tools.variants import design_variants, PRO_TARGETS, CONSENSUS_SUBS


@pytest.mark.unit
class TestDesignVariants:

    def test_returns_required_keys(self, short_sequence, sample_weak_regions):
        result = design_variants(short_sequence, sample_weak_regions, "test")
        assert "variants" in result or "message" in result  # either variants or no-candidates message
        assert "protein_name" in result

    def test_generates_variants_for_targetable_sequence(self, short_sequence, sample_weak_regions):
        """short_sequence has G, A, S in weak region — should produce proline variants."""
        result = design_variants(short_sequence, sample_weak_regions, "test")
        assert result.get("variants_designed", 0) > 0

    def test_variant_structure(self, short_sequence, sample_weak_regions):
        """Each variant must have the fields compare_variants and predict_tm_change expect."""
        result = design_variants(short_sequence, sample_weak_regions, "test")
        required = {"variant_id", "strategy", "mutations", "sequence",
                    "predicted_delta_Tm", "confidence", "rationale", "wet_lab_validation"}
        for variant in result.get("variants", []):
            assert required.issubset(variant.keys()), f"Missing keys: {required - variant.keys()}"

    def test_mutation_structure(self, short_sequence, sample_weak_regions):
        """Each mutation must have position, from, to."""
        result = design_variants(short_sequence, sample_weak_regions, "test")
        for variant in result.get("variants", []):
            for mut in variant["mutations"]:
                assert "position" in mut
                assert "from" in mut
                assert "to" in mut
                assert isinstance(mut["position"], int)
                assert mut["position"] >= 1

    def test_variant_sequence_length_preserved(self, short_sequence, sample_weak_regions):
        """Variants must have same length as original sequence."""
        result = design_variants(short_sequence, sample_weak_regions, "test")
        for variant in result.get("variants", []):
            assert len(variant["sequence"]) == len(short_sequence)

    def test_variant_sequence_differs_from_original(self, short_sequence, sample_weak_regions):
        """Each variant must actually differ from the original."""
        result = design_variants(short_sequence, sample_weak_regions, "test")
        for variant in result.get("variants", []):
            assert variant["sequence"] != short_sequence

    def test_proline_substitution_targets(self, sample_weak_regions):
        """Only PRO_TARGET residues (G, A, S, T, N, Q) should get proline substitutions."""
        # Sequence where first residue of weak region is a PRO_TARGET
        seq = "MAAAAAAAAAGSSSSSSSSS"  # position 11+ are G/S = PRO_TARGETS
        result = design_variants(seq, sample_weak_regions, "test")
        for variant in result.get("variants", []):
            if variant["strategy"] == "Proline substitution":
                for mut in variant["mutations"]:
                    assert mut["from"] in PRO_TARGETS
                    assert mut["to"] == "P"

    def test_no_proline_adjacent_to_proline(self, sample_weak_regions):
        """Proline should not be inserted next to an existing proline."""
        # Sequence with P at position 12 (adjacent to targets)
        seq = "MAAAAAAAAAGPSSSSSSS"
        result = design_variants(seq, sample_weak_regions, "test")
        for variant in result.get("variants", []):
            if variant["strategy"] == "Proline substitution":
                for mut in variant["mutations"]:
                    pos = mut["position"] - 1  # 0-indexed
                    assert seq[pos - 1] != "P" if pos > 0 else True
                    assert seq[pos + 1] != "P" if pos < len(seq) - 1 else True

    def test_consensus_mutations_applied(self, sample_weak_regions):
        """Consensus targets (C, M, N, Q) should be substituted."""
        seq = "MCNQTAGNAGKTGLTQGASM"  # has M, C, N, Q
        result = design_variants(seq, sample_weak_regions, "test")
        consensus_variants = [v for v in result.get("variants", [])
                              if v["strategy"] == "Consensus mutation"]
        assert len(consensus_variants) > 0
        for variant in consensus_variants:
            for mut in variant["mutations"]:
                assert mut["from"] in CONSENSUS_SUBS
                assert mut["to"] == CONSENSUS_SUBS[mut["from"]]

    def test_n_variants_limit_respected(self, short_sequence, sample_weak_regions):
        """Should return at most n_variants variants."""
        for n in [1, 2, 3]:
            result = design_variants(short_sequence, sample_weak_regions, "test", n_variants=n)
            assert len(result.get("variants", [])) <= n

    def test_empty_weak_regions_still_runs(self, short_sequence):
        """With no weak regions, consensus mutations may still apply."""
        result = design_variants(short_sequence, [], "test")
        assert "protein_name" in result  # didn't crash

    def test_no_candidates_message(self):
        """Sequence with no targetable residues returns informative message."""
        # Sequence with only residues that are not PRO_TARGETS and not CONSENSUS_SUBS
        seq = "LLLLLLLLLLLLLLLLLLLL"  # L is not a target for any strategy
        result = design_variants(seq, [], "test")
        # Either 0 variants or message explaining why
        assert result.get("variants_designed", 0) == 0 or "message" in result

    def test_target_application_note(self, short_sequence, sample_weak_regions):
        """Providing target_application should add an application note."""
        result = design_variants(
            short_sequence, sample_weak_regions, "test",
            target_application="cooking"
        )
        assert result.get("application_note", "") != "" or result.get("variants_designed", 0) == 0

    def test_protein_name_in_output(self, short_sequence, sample_weak_regions):
        result = design_variants(short_sequence, sample_weak_regions, "lactoferrina")
        assert result["protein_name"] == "lactoferrina"
