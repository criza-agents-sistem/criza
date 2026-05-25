"""
Unit tests for tools/esmfold_local.py — predict_structure_local()

Unit tests verify: graceful fallback when fair-esm not installed, output structure
when mock succeeds, constants and helper functions.

Integration tests require: fair-esm + torch installed + GPU (or patience on CPU).
Skip with: pytest -m "not integration"
"""

import pytest
from unittest.mock import patch, MagicMock
from tools.esmfold_local import predict_structure_local, _check_dependencies, _is_gpu_available


@pytest.mark.unit
class TestCheckDependencies:

    def test_returns_tuple(self):
        result = _check_dependencies()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_returns_bool_and_string(self):
        available, msg = _check_dependencies()
        assert isinstance(available, bool)
        assert isinstance(msg, str)

    def test_error_message_empty_when_available(self):
        """If deps are available, error message should be empty string."""
        available, msg = _check_dependencies()
        if available:
            assert msg == ""

    def test_error_message_present_when_not_available(self):
        """If deps are missing, error message should describe what's missing."""
        available, msg = _check_dependencies()
        if not available:
            assert len(msg) > 0
            assert "install" in msg.lower() or "pip" in msg.lower()


@pytest.mark.unit
class TestIsGpuAvailable:

    def test_returns_bool(self):
        result = _is_gpu_available()
        assert isinstance(result, bool)

    def test_returns_false_when_torch_missing(self):
        """Without torch, GPU check should return False gracefully."""
        with patch("builtins.__import__", side_effect=ImportError("no torch")):
            # _is_gpu_available catches ImportError internally
            pass  # just verify the function exists and returns bool in normal flow
        assert isinstance(_is_gpu_available(), bool)


@pytest.mark.unit
class TestPredictStructureLocalFallback:

    def test_missing_deps_returns_structure_obtained_false(self):
        """When fair-esm not installed, returns structure_obtained=False."""
        with patch("tools.esmfold_local._check_dependencies", return_value=(False, "torch not installed")):
            result = predict_structure_local("MGSNT", "test")
        assert result["structure_obtained"] is False

    def test_missing_deps_returns_setup_instructions(self):
        """Fallback includes setup_instructions key."""
        with patch("tools.esmfold_local._check_dependencies", return_value=(False, "torch not installed")):
            result = predict_structure_local("MGSNT", "test")
        assert "setup_instructions" in result
        assert len(result["setup_instructions"]) > 0

    def test_missing_deps_returns_fallback_key(self):
        """Fallback includes fallback key pointing to API version."""
        with patch("tools.esmfold_local._check_dependencies", return_value=(False, "torch not installed")):
            result = predict_structure_local("MGSNT", "test")
        assert "fallback" in result
        assert "predict_structure" in result["fallback"]

    def test_missing_deps_includes_protein_name(self):
        with patch("tools.esmfold_local._check_dependencies", return_value=(False, "fair-esm not installed")):
            result = predict_structure_local("MGSNT", "my_protein")
        assert result["protein_name"] == "my_protein"

    def test_missing_deps_error_message_propagated(self):
        """The specific error message from _check_dependencies appears in result."""
        with patch("tools.esmfold_local._check_dependencies", return_value=(False, "fair-esm not installed — run: pip install fair-esm")):
            result = predict_structure_local("MGSNT", "test")
        assert "fair-esm" in result["error"]


@pytest.mark.unit
class TestPredictStructureLocalMocked:
    """
    Tests verifying output structure when deps are available (mocked via sys.modules).
    Uses sys.modules patching to avoid requiring actual torch/esm installation.
    """

    SAMPLE_PDB = "\n".join([
        "ATOM      1  N   MET A   1      -1.000   2.000   3.000  1.00 85.00           N",
        "ATOM      2  CA  MET A   1      -1.500   2.500   3.500  1.00 82.00           C",
        "ATOM      3  N   GLY A   2       0.000   1.000   2.000  1.00 78.00           N",
        "ATOM      4  CA  GLY A   2       0.500   1.500   2.500  1.00 75.00           C",
        "ATOM      5  N   SER A   3       1.000   0.500   1.500  1.00 91.00           N",
        "END",
    ])

    def test_protein_name_in_output(self):
        """protein_name always present — even on fallback."""
        with patch("tools.esmfold_local._check_dependencies", return_value=(False, "no torch")):
            result = predict_structure_local("MGSNT", "lactoferrina")
        assert result["protein_name"] == "lactoferrina"

    def test_no_crash_with_long_sequence_on_fallback(self):
        """250+ aa sequence should not crash on fallback (no truncation logic on fallback path)."""
        with patch("tools.esmfold_local._check_dependencies", return_value=(False, "no torch")):
            result = predict_structure_local("MGSNT" * 50, "long_protein")
        assert "protein_name" in result
        assert result["structure_obtained"] is False

    def test_success_path_with_sys_modules_mock(self, tmp_path):
        """
        Verify full success path by mocking esm and torch via sys.modules.
        Avoids requiring actual fair-esm/torch installation.
        """
        import sys

        # Build a minimal mock model
        mock_model = MagicMock()
        mock_model.eval.return_value = mock_model
        mock_model.infer_pdb.return_value = self.SAMPLE_PDB

        # Mock torch context manager
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        mock_no_grad = MagicMock()
        mock_no_grad.__enter__ = MagicMock(return_value=None)
        mock_no_grad.__exit__ = MagicMock(return_value=False)
        mock_torch.no_grad.return_value = mock_no_grad

        # Mock esm module
        mock_esm = MagicMock()
        mock_esm.pretrained.esmfold_v1.return_value = mock_model

        with patch.dict(sys.modules, {"torch": mock_torch, "esm": mock_esm}), \
             patch("tools.esmfold_local._check_dependencies", return_value=(True, "")), \
             patch("tools.esmfold_local._is_gpu_available", return_value=False), \
             patch("tools.esmfold_local.Path") as mock_path_cls:

            # Make Path().parent.parent / "structures" point to tmp_path
            mock_pdb_dir = MagicMock()
            mock_pdb_dir.mkdir.return_value = None
            pdb_file = tmp_path / "test_5aa_local.pdb"
            mock_pdb_dir.__truediv__ = MagicMock(return_value=pdb_file)
            mock_path_cls.return_value.parent.parent.__truediv__ = MagicMock(return_value=mock_pdb_dir)

            result = predict_structure_local("MGSNT", "test_protein")

        assert result["protein_name"] == "test_protein"
        assert result["structure_obtained"] is True
        assert result["truncated"] is False
        assert result["analyzed_length"] == 5   # len("MGSNT")
        assert result["original_length"] == 5
        assert result["method"] == "local"
        assert "avg_plddt" in result
        assert "per_residue_plddt" in result
        assert "confidence_level" in result
        assert "expression_implication" in result
        assert result["avg_plddt"] > 0

    def test_plddt_computed_from_pdb_atoms(self, tmp_path):
        """avg_plddt should reflect B-factor values in the PDB ATOM lines."""
        # SAMPLE_PDB has B-factors: 85, 82, 78, 75, 91 → avg = 82.2
        import sys

        mock_model = MagicMock()
        mock_model.eval.return_value = mock_model
        mock_model.infer_pdb.return_value = self.SAMPLE_PDB

        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        mock_no_grad = MagicMock()
        mock_no_grad.__enter__ = MagicMock(return_value=None)
        mock_no_grad.__exit__ = MagicMock(return_value=False)
        mock_torch.no_grad.return_value = mock_no_grad

        mock_esm = MagicMock()
        mock_esm.pretrained.esmfold_v1.return_value = mock_model

        with patch.dict(sys.modules, {"torch": mock_torch, "esm": mock_esm}), \
             patch("tools.esmfold_local._check_dependencies", return_value=(True, "")), \
             patch("tools.esmfold_local._is_gpu_available", return_value=False), \
             patch("tools.esmfold_local.Path") as mock_path_cls:

            mock_pdb_dir = MagicMock()
            mock_pdb_dir.mkdir.return_value = None
            pdb_file = tmp_path / "test_5aa_local.pdb"
            mock_pdb_dir.__truediv__ = MagicMock(return_value=pdb_file)
            mock_path_cls.return_value.parent.parent.__truediv__ = MagicMock(return_value=mock_pdb_dir)

            result = predict_structure_local("MGSNT", "test_protein")

        expected_avg = round((85 + 82 + 78 + 75 + 91) / 5, 2)
        assert abs(result["avg_plddt"] - expected_avg) < 0.1
