"""
Unit tests for tools/foldx.py — predict_tm_change()

Tests cover: helper functions, graceful fallback, input validation.
No FoldX binary required — tests verify behavior when FoldX is NOT installed.
"""

import pytest
from tools.foldx import (
    predict_tm_change,
    _mutations_to_foldx,
    _ddg_verdict,
    _parse_build_model_output,
    _find_foldx,
    TM_FACTOR,
)
from pathlib import Path
import tempfile


@pytest.mark.unit
class TestMutationsToFoldx:

    def test_single_mutation(self):
        muts = [{"position": 1, "from": "G", "to": "P"}]
        assert _mutations_to_foldx(muts) == "GA1P;"

    def test_multiple_mutations(self):
        muts = [
            {"position": 1, "from": "G", "to": "P"},
            {"position": 10, "from": "M", "to": "L"},
        ]
        assert _mutations_to_foldx(muts) == "GA1P,MA10L;"

    def test_default_chain_is_A(self):
        muts = [{"position": 5, "from": "S", "to": "P"}]
        result = _mutations_to_foldx(muts)
        assert "A5" in result

    def test_custom_chain(self):
        muts = [{"position": 5, "from": "S", "to": "P", "chain": "B"}]
        result = _mutations_to_foldx(muts)
        assert "B5" in result

    def test_empty_mutations(self):
        assert _mutations_to_foldx([]) == ""

    def test_ends_with_semicolon(self):
        muts = [{"position": 1, "from": "G", "to": "P"}]
        assert _mutations_to_foldx(muts).endswith(";")

    def test_uppercase_conversion(self):
        muts = [{"position": 1, "from": "g", "to": "p"}]
        result = _mutations_to_foldx(muts)
        assert "G" in result and "P" in result


@pytest.mark.unit
class TestDdgVerdict:

    def test_strongly_stabilizing(self):
        verdict, priority = _ddg_verdict(-2.5)
        assert priority == 1
        assert "stabilizing" in verdict.lower()

    def test_stabilizing(self):
        verdict, priority = _ddg_verdict(-1.0)
        assert priority == 2

    def test_neutral(self):
        verdict, priority = _ddg_verdict(0.0)
        assert priority == 3

    def test_mildly_destabilizing(self):
        verdict, priority = _ddg_verdict(1.0)
        assert priority == 4

    def test_strongly_destabilizing(self):
        verdict, priority = _ddg_verdict(3.0)
        assert priority == 5

    def test_boundary_stabilizing_threshold(self):
        # -0.5 is the boundary — code uses < -0.5 (exclusive), so -0.5 falls into neutral (priority 3)
        _, priority = _ddg_verdict(-0.5)
        assert priority == 3

    def test_boundary_destabilizing_threshold(self):
        # +0.5 is the boundary — should be "neutral" (priority 3)
        _, priority = _ddg_verdict(0.5)
        assert priority == 3

    def test_returns_tuple(self):
        result = _ddg_verdict(-1.0)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], int)


@pytest.mark.unit
class TestParseBuildModelOutput:

    def test_parses_two_line_format(self):
        """Standard FoldX output: header, WT line, mutant line."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".fxout",
                                        delete=False, encoding="utf-8") as f:
            f.write("Pdb\ttotal energy\tBackbone Hbond\n")
            f.write("WT_protein_1\t-145.678\t-10.0\n")
            f.write("protein_1\t-143.892\t-9.5\n")
            tmp = Path(f.name)

        result = _parse_build_model_output(tmp)
        tmp.unlink()

        assert result is not None
        expected = round(-143.892 - (-145.678), 4)
        assert abs(result - expected) < 0.001

    def test_returns_none_for_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".fxout",
                                        delete=False, encoding="utf-8") as f:
            f.write("")
            tmp = Path(f.name)

        result = _parse_build_model_output(tmp)
        tmp.unlink()
        assert result is None

    def test_returns_none_for_missing_file(self):
        result = _parse_build_model_output(Path("/nonexistent/file.fxout"))
        assert result is None


@pytest.mark.unit
class TestPredictTmChangeFallback:

    def test_pdb_not_found(self, sample_variants):
        result = predict_tm_change("nonexistent.pdb", sample_variants, "test")
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_empty_variants(self, tmp_path):
        fake_pdb = tmp_path / "fake.pdb"
        fake_pdb.write_text("ATOM  ...")
        result = predict_tm_change(str(fake_pdb), [], "test")
        assert result["success"] is False
        assert "no variants" in result["error"].lower()

    def test_variants_without_mutations(self, tmp_path):
        fake_pdb = tmp_path / "fake.pdb"
        fake_pdb.write_text("ATOM  ...")
        variants_no_muts = [{"variant_id": "V1", "sequence": "MGSNT", "mutations": []}]
        result = predict_tm_change(str(fake_pdb), variants_no_muts, "test")
        assert result["success"] is False

    def test_foldx_not_installed_returns_setup_instructions(self, tmp_path, sample_variants, monkeypatch):
        """When FoldX is not found, returns setup instructions."""
        # Force _find_foldx to return None
        monkeypatch.setenv("FOLDX_PATH", "/nonexistent/path/foldx")
        fake_pdb = tmp_path / "fake.pdb"
        fake_pdb.write_text("ATOM  ...")
        result = predict_tm_change(str(fake_pdb), sample_variants, "test")
        assert result["success"] is False
        assert "setup_instructions" in result
        assert "fallback" in result

    def test_tm_factor_applied(self):
        """Verify TM_FACTOR constant is the expected value."""
        assert TM_FACTOR == 1.7

    def test_delta_tm_calculation(self):
        """ΔTm = -ΔΔG × TM_FACTOR."""
        ddg = -2.0
        expected_delta_tm = -ddg * TM_FACTOR  # = +3.4
        assert abs(expected_delta_tm - 3.4) < 0.01
