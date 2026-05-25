"""
Tests for tools/compare.py — compare_variants()

Unit tests mock ESMFold to avoid API calls.
Integration tests run real ESMFold (slow, require API access).
"""

import pytest
from unittest.mock import patch
from tools.compare import compare_variants


# ── Shared mock response ──────────────────────────────────────────────────────

def make_esmfold_response(avg_plddt: float, success: bool = True):
    if not success:
        return {"structure_obtained": False, "error": "API error"}
    return {
        "structure_obtained": True,
        "avg_plddt": avg_plddt,
        "per_residue_plddt": [avg_plddt] * 20,
        "pdb_path": "structures/mock.pdb",
    }


@pytest.mark.unit
class TestCompareVariantsUnit:

    def test_better_variant_ranked_first(self, sample_variants):
        """Variant with higher pLDDT than wildtype should rank first."""
        wildtype_plddt = 70.0
        side_effects = [
            make_esmfold_response(80.0),  # variant 1: +10 pLDDT (better)
            make_esmfold_response(65.0),  # variant 2: -5 pLDDT (worse)
        ]
        with patch("tools.compare.predict_structure", side_effect=side_effects):
            result = compare_variants(
                wildtype_sequence="MGSNTAGNAGKTGLTQGASM",
                wildtype_plddt=wildtype_plddt,
                variants=sample_variants,
                protein_name="test",
            )

        assert result["variants_tested"] == 2
        best = result["results"][0]
        assert best["delta_plddt"] > 0

    def test_delta_plddt_computed_correctly(self, sample_variants):
        wildtype_plddt = 70.0
        variant_plddt = 78.0
        with patch("tools.compare.predict_structure",
                   return_value=make_esmfold_response(variant_plddt)):
            result = compare_variants(
                wildtype_sequence="MGSNTAGNAGKTGLTQGASM",
                wildtype_plddt=wildtype_plddt,
                variants=[sample_variants[0]],
                protein_name="test",
            )

        assert abs(result["results"][0]["delta_plddt"] - (variant_plddt - wildtype_plddt)) < 0.01

    def test_failed_esmfold_handled_gracefully(self, sample_variants):
        with patch("tools.compare.predict_structure",
                   return_value=make_esmfold_response(0, success=False)):
            result = compare_variants(
                wildtype_sequence="MGSNTAGNAGKTGLTQGASM",
                wildtype_plddt=70.0,
                variants=[sample_variants[0]],
                protein_name="test",
            )

        assert result["variants_tested"] == 1
        assert result["results"][0]["plddt_obtained"] is False

    def test_returns_required_keys(self, sample_variants):
        with patch("tools.compare.predict_structure",
                   return_value=make_esmfold_response(75.0)):
            result = compare_variants(
                wildtype_sequence="MGSNTAGNAGKTGLTQGASM",
                wildtype_plddt=70.0,
                variants=sample_variants,
                protein_name="test",
            )

        required = {"protein_name", "wildtype_plddt", "variants_tested",
                    "results", "lab_candidates", "summary"}
        assert required.issubset(result.keys())

    def test_max_variants_limit(self, sample_variants):
        with patch("tools.compare.predict_structure",
                   return_value=make_esmfold_response(75.0)):
            result = compare_variants(
                wildtype_sequence="MGSNTAGNAGKTGLTQGASM",
                wildtype_plddt=70.0,
                variants=sample_variants,
                protein_name="test",
                max_variants=1,
            )

        assert result["variants_tested"] == 1

    def test_verdict_significantly_better(self, sample_variants):
        """delta_pLDDT >= 5 should get the top verdict."""
        with patch("tools.compare.predict_structure",
                   return_value=make_esmfold_response(80.0)):  # +10 over 70 WT
            result = compare_variants(
                wildtype_sequence="MGSNTAGNAGKTGLTQGASM",
                wildtype_plddt=70.0,
                variants=[sample_variants[0]],
                protein_name="test",
            )

        assert result["results"][0]["priority"] == 1
        assert "significantly better" in result["results"][0]["plddt_verdict"].lower()

    def test_verdict_worse_than_wildtype(self, sample_variants):
        """delta_pLDDT < -1 should be deprioritized."""
        with patch("tools.compare.predict_structure",
                   return_value=make_esmfold_response(65.0)):  # -5 under 70 WT
            result = compare_variants(
                wildtype_sequence="MGSNTAGNAGKTGLTQGASM",
                wildtype_plddt=70.0,
                variants=[sample_variants[0]],
                protein_name="test",
            )

        assert result["results"][0]["priority"] == 4

    def test_lab_candidates_contain_only_good_variants(self, sample_variants):
        """lab_candidates should only include priority 1 or 2 variants."""
        side_effects = [
            make_esmfold_response(80.0),  # +10: priority 1 → lab candidate
            make_esmfold_response(65.0),  # -5: priority 4 → NOT lab candidate
        ]
        with patch("tools.compare.predict_structure", side_effect=side_effects):
            result = compare_variants(
                wildtype_sequence="MGSNTAGNAGKTGLTQGASM",
                wildtype_plddt=70.0,
                variants=sample_variants,
                protein_name="test",
            )

        assert len(result["lab_candidates"]) == 1
        assert result["lab_candidates"][0] == sample_variants[0]["variant_id"]

    def test_empty_variants_list(self):
        result = compare_variants(
            wildtype_sequence="MGSNTAGNAGKTGLTQGASM",
            wildtype_plddt=70.0,
            variants=[],
            protein_name="test",
        )
        assert result["variants_tested"] == 0


@pytest.mark.integration
class TestCompareVariantsIntegration:

    def test_real_esmfold_call(self, sample_variants):
        """
        Real ESMFold API call. Slow (~30-60s per variant).
        Requires internet access.
        """
        result = compare_variants(
            wildtype_sequence="MGSNTAGNAGKTGLTQGASM",
            wildtype_plddt=70.0,
            variants=[sample_variants[0]],
            protein_name="test_integration",
            max_variants=1,
        )
        assert result["variants_tested"] == 1
        if result["results"][0]["plddt_obtained"]:
            assert 0 <= result["results"][0]["variant_plddt"] <= 100
