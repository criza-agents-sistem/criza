import sys
from pathlib import Path

_KM = Path(__file__).parent.parent.parent.parent / "knowledge_module"
_AGENT = Path(__file__).parent.parent
sys.path.insert(0, str(_KM))
sys.path.insert(0, str(_AGENT))


def pytest_configure(config):
    config.addinivalue_line("markers", "unit: fast unit tests (no external calls)")
    config.addinivalue_line("markers", "integration: tests that require network or KM")
