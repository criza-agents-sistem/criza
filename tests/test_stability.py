"""
Unit tests for tools/stability.py — analyze_stability()

Pure logic, no external APIs. Always fast.
"""

import pytest
from tools.stability import analyze_stability, LOW_CONFIDENCE_THRESHOLD, MIN_REGION_LENGTH


@pytest.mark.unit
class TestAnalyzeStability:

    def test_returns_required_keys(self, short_sequence, synthetic_plddt_with_weak_region):
        result = analyze_stability(short_sequence, synthetic_plddt_with_weak_region, "test_protein")
        required = {"protein_name", "avg_plddt", "weak_regions",
                    "n_weak_regions", "stability_assessment"}
        assert required.issubset(result.keys()), f"Missing keys: {required - result.keys()}"

    def test_detects_weak_region(self, short_sequence, synthetic_plddt_with_weak_region):
        """10 consecutive residues below threshold (55.0) should be flagged."""
        result = analyze_stability(short_sequence, synthetic_plddt_with_weak_region, "test")
        assert result["n_weak_regions"] >= 1
        assert len(result["weak_regions"]) >= 1

    def test_no_weak_regions_when_all_stable(self, short_sequence, synthetic_plddt_all_stable):
        """All residues at 82.0 (above threshold 70) — no weak regions."""
        result = analyze_stability(short_sequence, synthetic_plddt_all_stable, "test")
        assert result["n_weak_regions"] == 0
        assert result["weak_regions"] == []

    def test_avg_plddt_computed_correctly(self, short_sequence, synthetic_plddt_with_weak_region):
        result = analyze_stability(short_sequence, synthetic_plddt_with_weak_region, "test")
        expected_avg = sum(synthetic_plddt_with_weak_region) / len(synthetic_plddt_with_weak_region)
        assert abs(result["avg_plddt"] - expected_avg) < 0.01

    def test_avg_plddt_accepted_as_input(self, short_sequence, synthetic_plddt_with_weak_region):
        """avg_plddt passed explicitly should be used without recomputing."""
        result = analyze_stability(
            short_sequence, synthetic_plddt_with_weak_region, "test", avg_plddt=99.0
        )
        assert result["avg_plddt"] == 99.0

    def test_weak_region_fields(self, short_sequence, synthetic_plddt_with_weak_region):
        """Each weak region must have all required fields."""
        result = analyze_stability(short_sequence, synthetic_plddt_with_weak_region, "test")
        for region in result["weak_regions"]:
            assert "start" in region
            assert "end" in region
            assert "avg_plddt" in region
            assert "sequence" in region
            assert region["avg_plddt"] < LOW_CONFIDENCE_THRESHOLD

    def test_weak_region_minimum_length(self, short_sequence):
        """Regions shorter than MIN_REGION_LENGTH should not be flagged."""
        # Only 2 consecutive low-pLDDT residues (below MIN_REGION_LENGTH of 4)
        plddt = [85.0] * 10 + [50.0] * 2 + [85.0] * 8
        result = analyze_stability(short_sequence, plddt, "test")
        assert result["n_weak_regions"] == 0

    def test_sequence_length_mismatch_handled(self, short_sequence):
        """If sequence and pLDDT lengths differ, should handle gracefully."""
        short_plddt = [80.0] * 10  # shorter than sequence
        result = analyze_stability(short_sequence, short_plddt, "test")
        assert "protein_name" in result  # didn't crash

    def test_protein_name_in_output(self, short_sequence, synthetic_plddt_all_stable):
        result = analyze_stability(short_sequence, synthetic_plddt_all_stable, "lactoferrina")
        assert result["protein_name"] == "lactoferrina"

    def test_thermostability_assessment_present(self, short_sequence, synthetic_plddt_with_weak_region):
        result = analyze_stability(short_sequence, synthetic_plddt_with_weak_region, "test")
        assert isinstance(result["stability_assessment"], str)
        assert len(result["stability_assessment"]) > 0
