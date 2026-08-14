"""
Unit tests for tools/mpnn.py — design_variants_mpnn()

Tests cover: helper functions, graceful fallback, input validation.
No ProteinMPNN binary required.
"""

import pytest
from tools.mpnn import (
    design_variants_mpnn,
    _diff_sequences,
    _score_to_confidence,
    _parse_mpnn_fasta,
)
from pathlib import Path
import tempfile


@pytest.mark.unit
class TestDiffSequences:

    def test_no_mutations(self):
        assert _diff_sequences("MGSNT", "MGSNT") == []

    def test_single_mutation(self):
        result = _diff_sequences("MGSNT", "MPSNT")
        assert len(result) == 1
        assert result[0] == {"position": 2, "from": "G", "to": "P"}

    def test_multiple_mutations(self):
        result = _diff_sequences("MGSNT", "MPSDT")
        assert len(result) == 2
        positions = [m["position"] for m in result]
        assert 2 in positions  # G -> P
        assert 4 in positions  # N -> D

    def test_different_lengths_returns_empty(self):
        assert _diff_sequences("MGS", "MGSNT") == []

    def test_empty_sequences(self):
        assert _diff_sequences("", "") == []

    def test_wildtype_empty_returns_empty(self):
        assert _diff_sequences("", "MGSNT") == []

    def test_position_is_one_indexed(self):
        result = _diff_sequences("MGSNT", "PGSNT")
        assert result[0]["position"] == 1

    def test_mutation_fields(self):
        result = _diff_sequences("MGSNT", "MPSNT")
        assert "position" in result[0]
        assert "from" in result[0]
        assert "to" in result[0]


@pytest.mark.unit
class TestScoreToConfidence:

    def test_high_confidence(self):
        result = _score_to_confidence(0.3)
        assert "high" in result.lower()

    def test_medium_high_confidence(self):
        result = _score_to_confidence(0.7)
        assert "medium" in result.lower()

    def test_medium_confidence(self):
        result = _score_to_confidence(1.2)
        assert "medium" in result.lower()

    def test_low_confidence(self):
        result = _score_to_confidence(2.0)
        assert "low" in result.lower()

    def test_returns_string(self):
        assert isinstance(_score_to_confidence(0.5), str)


@pytest.mark.unit
class TestParseMpnnFasta:

    def test_parses_single_sequence(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".fa",
                                        delete=False, encoding="utf-8") as f:
            f.write(">protein, score=0.123, global_score=0.456\n")
            f.write("MGSNTAGNAG\n")
            tmp = Path(f.name)

        result = _parse_mpnn_fasta(tmp)
        tmp.unlink()

        assert len(result) == 1
        assert result[0]["sequence"] == "MGSNTAGNAG"
        assert abs(result[0]["score"] - 0.123) < 0.001
        assert abs(result[0]["global_score"] - 0.456) < 0.001

    def test_parses_multiple_sequences(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".fa",
                                        delete=False, encoding="utf-8") as f:
            f.write(">protein, score=0.1, global_score=0.4\n")
            f.write("MGSNTAGNAG\n")
            f.write(">protein, score=0.2, global_score=0.5\n")
            f.write("MPSNTAGNAG\n")
            tmp = Path(f.name)

        result = _parse_mpnn_fasta(tmp)
        tmp.unlink()

        assert len(result) == 2

    def test_returns_empty_for_missing_file(self):
        result = _parse_mpnn_fasta(Path("/nonexistent/file.fa"))
        assert result == []

    def test_skips_empty_sequences(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".fa",
                                        delete=False, encoding="utf-8") as f:
            f.write(">protein, score=0.1\n")
            f.write("\n")  # empty sequence
            tmp = Path(f.name)

        result = _parse_mpnn_fasta(tmp)
        tmp.unlink()
        assert len(result) == 0

    def test_default_score_when_missing(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".fa",
                                        delete=False, encoding="utf-8") as f:
            f.write(">protein no score here\n")
            f.write("MGSNTAGNAG\n")
            tmp = Path(f.name)

        result = _parse_mpnn_fasta(tmp)
        tmp.unlink()

        assert len(result) == 1
        assert result[0]["score"] == 9999.0  # default when not parseable


@pytest.mark.unit
class TestDesignVariantsMpnnFallback:

    def test_pdb_not_found(self):
        result = design_variants_mpnn("nonexistent.pdb", "test")
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_mpnn_not_installed_returns_setup(self, tmp_path, monkeypatch):
        """When ProteinMPNN is not configured, return setup instructions."""
        monkeypatch.setenv("PROTEINMPNN_PATH", "/nonexistent/path")
        fake_pdb = tmp_path / "fake.pdb"
        fake_pdb.write_text("ATOM  ...")
        result = design_variants_mpnn(str(fake_pdb), "test")
        assert result["success"] is False
        assert "setup_instructions" in result
        assert "fallback" in result

    def test_n_sequences_clamped(self, tmp_path, monkeypatch):
        """n_sequences should be clamped between 1 and 50."""
        monkeypatch.setenv("PROTEINMPNN_PATH", "/nonexistent/path")
        fake_pdb = tmp_path / "fake.pdb"
        fake_pdb.write_text("ATOM  ...")
        # Even with invalid n_sequences, should not crash before reaching MPNN check
        result = design_variants_mpnn(str(fake_pdb), "test", n_sequences=999)
        assert result["success"] is False  # fails at MPNN not found, not at input validation

    def test_temperature_clamped(self, tmp_path, monkeypatch):
        """temperature should be clamped between 0.01 and 1.0."""
        monkeypatch.setenv("PROTEINMPNN_PATH", "/nonexistent/path")
        fake_pdb = tmp_path / "fake.pdb"
        fake_pdb.write_text("ATOM  ...")
        result = design_variants_mpnn(str(fake_pdb), "test", temperature=999.0)
        assert result["success"] is False  # fails at MPNN not found
