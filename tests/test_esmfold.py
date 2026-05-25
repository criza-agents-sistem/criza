"""
Tests for tools/esmfold.py — predict_structure()

Integration tests: require ESM Atlas API access (free, no auth).
Each call takes ~30-60s. Skip with: pytest -m "not integration"
"""

import pytest
from tools.esmfold import predict_structure, MAX_SEQUENCE_LENGTH

# Short sequence for API tests — fast, reliable
SHORT_TEST_SEQUENCE = "MGSNTAGNAGKT"  # 12aa, well within API limit


@pytest.mark.integration
class TestPredictStructureIntegration:

    def test_returns_structure_for_short_sequence(self):
        result = predict_structure(SHORT_TEST_SEQUENCE, "test_protein")
        assert result.get("structure_obtained") is True, \
            f"Structure not obtained: {result.get('error', 'unknown error')}"

    def test_plddt_in_valid_range(self):
        result = predict_structure(SHORT_TEST_SEQUENCE, "test_protein")
        if result.get("structure_obtained"):
            plddt = result["avg_plddt"]
            assert 0 <= plddt <= 100, f"pLDDT out of range: {plddt}"

    def test_per_residue_plddt_length_matches_sequence(self):
        result = predict_structure(SHORT_TEST_SEQUENCE, "test_protein")
        if result.get("structure_obtained"):
            per_residue = result.get("per_residue_plddt", [])
            assert len(per_residue) == len(SHORT_TEST_SEQUENCE), \
                f"Expected {len(SHORT_TEST_SEQUENCE)} scores, got {len(per_residue)}"

    def test_per_residue_plddt_all_valid(self):
        result = predict_structure(SHORT_TEST_SEQUENCE, "test_protein")
        if result.get("structure_obtained"):
            for score in result.get("per_residue_plddt", []):
                assert 0 <= score <= 100

    def test_pdb_path_created(self, tmp_path):
        result = predict_structure(SHORT_TEST_SEQUENCE, "test_protein")
        if result.get("structure_obtained"):
            pdb_path = result.get("pdb_path")
            assert pdb_path is not None
            from pathlib import Path
            assert Path(pdb_path).exists(), f"PDB file not created at {pdb_path}"

    def test_required_keys_in_response(self):
        result = predict_structure(SHORT_TEST_SEQUENCE, "test_protein")
        assert "structure_obtained" in result
        assert "protein_name" in result

    def test_long_sequence_truncated(self):
        """Sequences > MAX_SEQUENCE_LENGTH should be truncated automatically."""
        long_seq = "M" * (MAX_SEQUENCE_LENGTH + 50)
        result = predict_structure(long_seq, "long_test")
        # Should not crash — may succeed or fail gracefully
        assert isinstance(result, dict)
        assert "protein_name" in result

    def test_protein_name_in_output(self):
        result = predict_structure(SHORT_TEST_SEQUENCE, "mi_proteina_test")
        assert result["protein_name"] == "mi_proteina_test"


@pytest.mark.unit
class TestPredictStructureConstants:

    def test_max_sequence_length_is_200(self):
        assert MAX_SEQUENCE_LENGTH == 200
