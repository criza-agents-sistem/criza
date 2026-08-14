"""
Shared fixtures and configuration for the scientific agent test suite.

Markers:
  unit        — no external dependencies, always fast
  integration — requires API access (Semantic Scholar, UniProt, ESMFold)
                Skip with: pytest -m "not integration"

Usage:
  pytest tests/                          # all tests
  pytest tests/ -m "not integration"     # unit + mock tests only (fast)
  pytest tests/ -m integration           # API tests only
  pytest tests/ -v                       # verbose output
"""

import pytest


# ── Pytest marker registration ────────────────────────────────────────────────

def pytest_configure(config):
    config.addinivalue_line("markers", "unit: unit tests — no external dependencies")
    config.addinivalue_line("markers", "integration: integration tests — require API access")


# ── Shared fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def short_sequence():
    """
    20aa synthetic sequence designed for unit tests.
    Contains: G, A, S (proline substitution targets), N, M (consensus targets).
    """
    return "MGSNTAGNAGKTGLTQGASM"


@pytest.fixture
def lactoferrin_sequence_fragment():
    """
    First 30aa of bovine lactoferrin (UniProt P24627).
    Used for integration tests — real protein, short enough for API.
    """
    return "MKLVFLVLLFLGALGLCLAAPAKEAPKAEAKS"


@pytest.fixture
def synthetic_plddt_with_weak_region():
    """
    Synthetic pLDDT scores: first 10 residues high confidence,
    last 10 low confidence (below threshold of 70).
    Sequence length: 20aa.
    """
    return [85.0] * 10 + [55.0] * 10


@pytest.fixture
def synthetic_plddt_all_stable():
    """All residues above threshold — no weak regions expected."""
    return [82.0] * 20


@pytest.fixture
def sample_weak_regions():
    """Weak regions matching the synthetic_plddt_with_weak_region fixture."""
    return [
        {
            "start": 11,
            "end": 20,
            "length": 10,
            "avg_plddt": 55.0,
            "sequence": "KTGLTQGASM",
            "min_plddt": 55.0,
        }
    ]


@pytest.fixture
def sample_variants():
    """
    Minimal variant list for testing compare_variants and predict_tm_change.
    Uses the short_sequence as base.
    """
    return [
        {
            "variant_id": "PRO_2GS",
            "strategy": "Proline substitution",
            "mutations": [{"position": 2, "from": "G", "to": "P"}],
            "sequence": "MPSNTAGNAGKTGLTQGASM",
            "predicted_delta_Tm": "+1 to +3°C",
            "confidence": "High",
            "rationale": "Test variant",
            "wet_lab_validation": "Test DSF",
        },
        {
            "variant_id": "CONS_5NE",
            "strategy": "Consensus mutation",
            "mutations": [{"position": 5, "from": "N", "to": "D"}],
            "sequence": "MGSTDAGNAGKTGLTQGASM",
            "predicted_delta_Tm": "+1 to +5°C",
            "confidence": "Medium-High",
            "rationale": "Test consensus variant",
            "wet_lab_validation": "Test DSF",
        },
    ]
