import sys
from pathlib import Path

_CRIZA = Path(__file__).parent.parent.parent
_MODULE = Path(__file__).parent.parent

sys.path.insert(0, str(_CRIZA))
sys.path.insert(0, str(_MODULE))


def pytest_configure(config):
    config.addinivalue_line("markers", "unit: unit tests — sin dependencias externas")
    config.addinivalue_line("markers", "integration: integration tests — requieren APIs y KM")
