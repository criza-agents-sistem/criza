"""
Fixtures y configuración del suite de tests del Agente de Mercado.

Markers:
  unit        — sin dependencias externas, siempre rápido
  integration — requiere acceso a APIs reales (COMTRADE, datos.gob.ar)
                Saltar con: pytest -m "not integration"

Uso:
  pytest tests/                          # todos los tests
  pytest tests/ -m "not integration"     # solo unit (rápido)
  pytest tests/ -m integration           # solo integration (requiere APIs)
  pytest tests/ -v                       # verbose
"""

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "unit: unit tests — sin dependencias externas")
    config.addinivalue_line("markers", "integration: integration tests — requieren APIs externas")


@pytest.fixture
def sample_comtrade_response():
    """Respuesta simulada de COMTRADE para tests unitarios."""
    return {
        "data": [
            {
                "period": 2023,
                "reporterDesc": "Argentina",
                "partnerDesc": "China",
                "cmdCode": "3507",
                "cmdDesc": "Enzymes; prepared enzymes, not elsewhere specified or included",
                "primaryValue": 1_500_000.0,
                "netWgt": 50_000.0,
                "qty": 50_000.0,
                "qtyUnitAbbr": "kg",
            },
            {
                "period": 2023,
                "reporterDesc": "Argentina",
                "partnerDesc": "Denmark",
                "cmdCode": "3507",
                "cmdDesc": "Enzymes; prepared enzymes, not elsewhere specified or included",
                "primaryValue": 3_200_000.0,
                "netWgt": 80_000.0,
                "qty": 80_000.0,
                "qtyUnitAbbr": "kg",
            },
        ]
    }


@pytest.fixture
def sample_datosgobar_response():
    """Respuesta simulada de datos.gob.ar para tests unitarios."""
    return {
        "success": True,
        "result": {
            "count": 2,
            "results": [
                {
                    "title": "Exportaciones agropecuarias por producto",
                    "notes": "Estadísticas de exportaciones del sector agropecuario argentino.",
                    "name": "exportaciones-agropecuarias",
                    "organization": {"title": "MAGYP"},
                    "metadata_modified": "2024-01-15",
                    "resources": [
                        {"name": "CSV 2023", "format": "CSV", "url": "https://datos.gob.ar/dataset/export.csv"},
                    ],
                },
                {
                    "title": "Industria de alimentos balanceados",
                    "notes": "Producción y comercialización de alimentos balanceados.",
                    "name": "alimentos-balanceados",
                    "organization": {"title": "MAGYP"},
                    "metadata_modified": "2024-02-01",
                    "resources": [
                        {"name": "XLS", "format": "XLS", "url": "https://datos.gob.ar/dataset/balanceados.xls"},
                    ],
                },
            ],
        },
    }
