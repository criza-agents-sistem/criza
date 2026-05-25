"""
Tests for tools/uniprot.py — get_protein_sequence()

Integration tests: require UniProt API access.
Skip with: pytest -m "not integration"
"""

import pytest
from tools.uniprot import get_protein_sequence

LACTOFERRIN_UNIPROT_ID = "P24627"
LACTOFERRIN_LENGTH = 708


@pytest.mark.integration
class TestGetProteinSequenceIntegration:

    def test_lactoferrin_returns_sequence(self):
        result = get_protein_sequence("lactoferrin", organism="Bos taurus")
        assert result.get("sequence"), "No sequence returned"
        assert isinstance(result["sequence"], str)
        assert len(result["sequence"]) > 0

    def test_lactoferrin_sequence_length(self):
        result = get_protein_sequence("lactoferrin", organism="Bos taurus")
        seq = result.get("sequence", "")
        # Lactoferrin is 708aa — allow ± 10 for isoforms
        assert abs(len(seq) - LACTOFERRIN_LENGTH) <= 10, \
            f"Unexpected length: {len(seq)} (expected ~{LACTOFERRIN_LENGTH})"

    def test_lactoferrin_sequence_is_amino_acids(self):
        result = get_protein_sequence("lactoferrin", organism="Bos taurus")
        seq = result.get("sequence", "")
        valid_aa = set("ACDEFGHIKLMNPQRSTVWY")
        assert all(c in valid_aa for c in seq.upper()), \
            "Sequence contains non-amino acid characters"

    def test_required_keys_in_response(self):
        result = get_protein_sequence("lactoferrin")
        required = {"sequence", "protein_name"}
        assert required.issubset(result.keys()), \
            f"Missing keys: {required - result.keys()}"

    def test_organism_filter_works(self):
        result_bovine = get_protein_sequence("lactoferrin", organism="Bos taurus")
        assert result_bovine.get("sequence"), "No sequence for Bos taurus"

    def test_nonexistent_protein_handled(self):
        """Completely made-up protein should return without crashing."""
        result = get_protein_sequence("xyzxyz_nonexistent_protein_12345")
        # Should return a result dict, possibly with an error or empty sequence
        assert isinstance(result, dict)

    def test_sequence_starts_with_methionine(self):
        """Most mature proteins start with M (methionine)."""
        result = get_protein_sequence("lactoferrin", organism="Bos taurus")
        seq = result.get("sequence", "")
        if seq:
            assert seq[0] == "M", f"Sequence starts with {seq[0]}, expected M"
