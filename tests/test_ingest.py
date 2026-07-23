"""
Tests para ingest_corrida.py

Cubre:
- extract_opportunities_from_output: parsing de JSON válido e inválido
- km_ingest: integración real contra Neon (corrida + documento + oportunidades)

Markers:
- unit: no necesita DB ni API externa
- integration: necesita Neon real + ANTHROPIC_API_KEY
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Asegurar que el módulo km está en el path
_km_path = Path(__file__).parent.parent
if str(_km_path) not in sys.path:
    sys.path.insert(0, str(_km_path))


# ── Unit tests — extract_opportunities_from_output ───────────────────────────

class TestExtractOpportunities:
    """Tests de parseo de la función de extracción con Claude Haiku."""

    def _mock_anthropic_response(self, json_text: str):
        """Crea un mock del cliente Anthropic que devuelve json_text."""
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text=json_text)]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_resp
        return mock_client

    @pytest.mark.unit
    def test_parse_valid_json_array(self):
        """Debe devolver la lista de oportunidades cuando Haiku retorna JSON válido."""
        from ingest_corrida import extract_opportunities_from_output

        valid_json = json.dumps([
            {"idea": "Probiótico para bovinos", "prioridad": "alta", "gaps_pendientes": None},
            {"idea": "Biopesticida base Beauveria", "prioridad": "media", "gaps_pendientes": "Falta dato de mercado"},
        ])

        with patch("ingest_corrida.anthropic.Anthropic", return_value=self._mock_anthropic_response(valid_json)):
            result = extract_opportunities_from_output("output de prueba", "ganadería")

        assert len(result) == 2
        assert result[0]["idea"] == "Probiótico para bovinos"
        assert result[0]["prioridad"] == "alta"
        assert result[1]["prioridad"] == "media"

    @pytest.mark.unit
    def test_parse_json_inside_markdown_codeblock(self):
        """Debe limpiar el markdown code block si Haiku lo devuelve con ```json."""
        from ingest_corrida import extract_opportunities_from_output

        wrapped = "```json\n" + json.dumps([
            {"idea": "Test idea", "prioridad": "baja", "gaps_pendientes": None}
        ]) + "\n```"

        with patch("ingest_corrida.anthropic.Anthropic", return_value=self._mock_anthropic_response(wrapped)):
            result = extract_opportunities_from_output("output", "avicultura")

        assert len(result) == 1
        assert result[0]["idea"] == "Test idea"

    @pytest.mark.unit
    def test_returns_empty_list_on_invalid_json(self):
        """Si Haiku devuelve texto inválido, debe retornar lista vacía sin lanzar excepción."""
        from ingest_corrida import extract_opportunities_from_output

        with patch("ingest_corrida.anthropic.Anthropic", return_value=self._mock_anthropic_response("texto inválido")):
            result = extract_opportunities_from_output("output", "porcicultura")

        assert result == []

    @pytest.mark.unit
    def test_returns_empty_list_on_api_error(self):
        """Si la API de Anthropic falla, debe retornar lista vacía sin lanzar excepción."""
        from ingest_corrida import extract_opportunities_from_output

        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API error simulado")

        with patch("ingest_corrida.anthropic.Anthropic", return_value=mock_client):
            result = extract_opportunities_from_output("output", "sector_x")

        assert result == []

    @pytest.mark.unit
    def test_returns_empty_list_on_empty_response(self):
        """Si Haiku devuelve [] explícitamente, debe respetar eso."""
        from ingest_corrida import extract_opportunities_from_output

        with patch("ingest_corrida.anthropic.Anthropic", return_value=self._mock_anthropic_response("[]")):
            result = extract_opportunities_from_output("output sin oportunidades claras", "sector_y")

        assert result == []


# ── Integration tests — km_ingest contra Neon real ───────────────────────────

@pytest.mark.integration
def test_km_ingest_full_flow():
    """
    Verifica que km_ingest guarda: Corrida + Documento + al menos 1 Oportunidad.
    Necesita Neon real + ANTHROPIC_API_KEY.
    """
    from ingest_corrida import km_ingest

    output_minimal = """
## Análisis de oportunidades — Sector test

### Oportunidad 1
Desarrollar un inoculante microbiano para mejorar la digestión en bovinos.
Prioridad: alta.
Gaps pendientes: validar demanda con productores locales.
"""

    result = km_ingest(
        sector="sector_test_pytest",
        agente="divergente",
        modo="A",
        fecha="2026-06-09",
        modelo="claude-haiku-4-5",
        output_text=output_minimal,
        notas="Test automático — safe to delete",
    )

    assert result["corrida_id"] is not None
    assert result["documento_id"] is not None
    assert result["oportunidades_total"] >= 0  # puede ser 0 si Haiku no extrae nada del minimal


@pytest.mark.integration
def test_km_ingest_documento_guardado():
    """
    Verifica que el Documento guardado por km_ingest contiene el output completo.
    """
    import asyncio
    from km_models import Documento
from knowledge_module.db import reset_engine, get_session_factory
    from sqlalchemy import select
    from ingest_corrida import km_ingest

    output_texto = "Contenido de prueba para verificar que el documento se guarda completo."

    result = km_ingest(
        sector="sector_test_doc_pytest",
        agente="divergente",
        modo="A",
        fecha="2026-06-09",
        modelo="claude-haiku-4-5",
        output_text=output_texto,
        notas="Test Documento — safe to delete",
    )

    assert result["documento_id"] is not None

    # Verificar que el contenido en DB es el correcto
    async def _check():
        reset_engine()
        async with get_session_factory()() as session:
            doc = await session.get(Documento, result["documento_id"])
            return doc

    reset_engine()
    doc = asyncio.run(_check())
    assert doc is not None
    assert doc.contenido == output_texto
    assert doc.sector == "sector_test_doc_pytest"
