"""
Tests for scout.py — Scout Científico Multidominio

Unit tests: prueban lógica interna sin llamadas de red ni API de Anthropic.
Integration tests: requieren acceso real a OpenAlex + Anthropic. Correr con: pytest -m integration

El scout es el PRIMER FILTRO del pipeline — sus tests cubren:
- dispatch_tool: ruteo correcto de herramientas
- Que solo expone search_literature (no tools del especialista)
- run_scout: loop agéntico con mocks (end_turn y tool_use)
- Configuración de modelo y defaults
- Comportamiento ante herramientas desconocidas
"""

import json
import pytest
from unittest.mock import patch, MagicMock, call


# ──────────────────────────────────────────────
# UNIT TESTS — sin red ni API
# ──────────────────────────────────────────────

class TestScoutConfig:

    def test_default_model_is_sonnet(self):
        """El scout usa Sonnet por defecto — más barato que Opus, suficiente para scouting."""
        from scout import DEFAULT_MODEL
        assert "sonnet" in DEFAULT_MODEL.lower()

    def test_default_model_env_override(self, monkeypatch):
        """SCOUT_MODEL en .env sobreescribe el default."""
        monkeypatch.setenv("SCOUT_MODEL", "claude-test-model")
        import importlib
        import scout
        importlib.reload(scout)
        assert scout.DEFAULT_MODEL == "claude-test-model"
        importlib.reload(scout)  # restaurar

    def test_tools_list_has_exactly_one_tool(self):
        """El scout solo expone search_literature — sin herramientas pesadas."""
        from scout import TOOLS
        assert len(TOOLS) == 1

    def test_tools_list_contains_search_literature(self):
        """La única herramienta disponible es search_literature."""
        from scout import TOOLS
        assert TOOLS[0]["name"] == "search_literature"

    def test_tools_schema_has_required_query(self):
        """El schema de search_literature requiere el campo 'query'."""
        from scout import TOOLS
        required = TOOLS[0]["input_schema"]["required"]
        assert "query" in required

    def test_system_prompt_is_not_empty(self):
        """El system prompt existe y tiene contenido sustancial."""
        from scout import SYSTEM_PROMPT
        assert len(SYSTEM_PROMPT) > 500

    def test_system_prompt_has_no_fermentation_hard_requirement(self):
        """El prompt NO restringe a fermentación como único método de producción."""
        from scout import SYSTEM_PROMPT
        # El prompt debe mencionar "requiere_socio" o "subcontrat" como opción válida
        assert "requiere_socio" in SYSTEM_PROMPT or "subcontrat" in SYSTEM_PROMPT.lower()

    def test_system_prompt_mentions_human_nutrition(self):
        """El prompt incluye nutrición humana B2B como sector válido."""
        from scout import SYSTEM_PROMPT
        assert "humana" in SYSTEM_PROMPT.lower() or "human" in SYSTEM_PROMPT.lower()

    def test_system_prompt_gmo_is_context_not_criteria(self):
        """GMO+peletizado aparece en el prompt como contexto habilitador, no como criterio."""
        from scout import SYSTEM_PROMPT
        # Debe estar en sección CONTEXTO HABILITADOR, no en CRITERIOS DE OPORTUNIDAD
        context_idx = SYSTEM_PROMPT.find("CONTEXTO HABILITADOR")
        criteria_idx = SYSTEM_PROMPT.find("CRITERIOS DE OPORTUNIDAD")
        gmo_idx = SYSTEM_PROMPT.find("GMO")
        assert context_idx != -1, "Debe existir sección CONTEXTO HABILITADOR"
        assert criteria_idx != -1, "Debe existir sección CRITERIOS DE OPORTUNIDAD"
        assert gmo_idx != -1, "GMO debe estar mencionado en el prompt"
        # GMO debe aparecer en o antes de la sección de criterios (no dentro de criterios)
        assert gmo_idx < criteria_idx or gmo_idx > criteria_idx + 500


class TestDispatchTool:

    def test_search_literature_dispatches_correctly(self):
        """dispatch_tool llama a search_literature con los parámetros correctos."""
        from scout import dispatch_tool
        mock_result = {"results": [], "total_found": 0, "query": "test"}
        with patch("scout.search_literature", return_value=mock_result) as mock_search:
            result = dispatch_tool("search_literature", {"query": "phytase feed", "max_results": 5})
            mock_search.assert_called_once_with("phytase feed", 5)
            parsed = json.loads(result)
            assert parsed["query"] == "test"

    def test_search_literature_uses_default_max_results(self):
        """Si max_results no se pasa, usa 8 (default del scout, más restrictivo que OpenAlex)."""
        from scout import dispatch_tool
        with patch("scout.search_literature", return_value={}) as mock_search:
            dispatch_tool("search_literature", {"query": "test"})
            mock_search.assert_called_once_with("test", 8)

    def test_unknown_tool_returns_error(self):
        """Herramientas no disponibles en el scout retornan error — no crashean."""
        from scout import dispatch_tool
        result = dispatch_tool("predict_structure", {"sequence": "ACGT", "protein_name": "test"})
        parsed = json.loads(result)
        assert "error" in parsed
        assert "not available in scout" in parsed["error"]

    def test_unknown_tool_does_not_call_search_literature(self):
        """Una herramienta desconocida no debe llamar a search_literature."""
        from scout import dispatch_tool
        with patch("scout.search_literature") as mock_search:
            dispatch_tool("get_protein_sequence", {"protein_name": "lactoferrin"})
            mock_search.assert_not_called()

    def test_dispatch_returns_json_string(self):
        """dispatch_tool siempre retorna un string JSON parseable."""
        from scout import dispatch_tool
        with patch("scout.search_literature", return_value={"results": []}):
            result = dispatch_tool("search_literature", {"query": "test"})
            assert isinstance(result, str)
            json.loads(result)  # no debe lanzar excepción

    def test_dispatch_preserves_non_ascii(self):
        """El resultado JSON preserva caracteres no-ASCII (español, griego)."""
        from scout import dispatch_tool
        with patch("scout.search_literature", return_value={"title": "Análisis de β-glucano"}):
            result = dispatch_tool("search_literature", {"query": "test"})
            assert "Análisis" in result
            assert "β-glucano" in result


class TestRunScoutLoop:

    def _make_mock_client(self, responses):
        """Crea un mock de anthropic.Anthropic() que retorna responses en secuencia."""
        client = MagicMock()
        client.messages.create.side_effect = responses
        return client

    def _make_end_turn_response(self, text="Scouting completado."):
        """Respuesta final del modelo (end_turn con texto)."""
        block = MagicMock()
        block.type = "text"
        block.text = text
        response = MagicMock()
        response.stop_reason = "end_turn"
        response.content = [block]
        return response

    def _make_tool_use_response(self, tool_name, tool_inputs, tool_id="tool_123"):
        """Respuesta del modelo pidiendo una tool call."""
        block = MagicMock()
        block.type = "tool_use"
        block.name = tool_name
        block.input = tool_inputs
        block.id = tool_id
        response = MagicMock()
        response.stop_reason = "tool_use"
        response.content = [block]
        return response

    def test_run_scout_returns_string(self):
        """run_scout siempre retorna un string."""
        from scout import run_scout
        end_response = self._make_end_turn_response("Resultado del scouting.")
        mock_client = self._make_mock_client([end_response])
        with patch("scout.anthropic.Anthropic", return_value=mock_client):
            result = run_scout("test query", verbose=False)
        assert isinstance(result, str)
        assert "Resultado" in result

    def test_run_scout_uses_configured_model(self):
        """run_scout llama a la API con el modelo especificado."""
        from scout import run_scout
        end_response = self._make_end_turn_response()
        mock_client = self._make_mock_client([end_response])
        with patch("scout.anthropic.Anthropic", return_value=mock_client):
            run_scout("test", model="claude-test-model-123", verbose=False)
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["model"] == "claude-test-model-123"

    def test_run_scout_passes_system_prompt(self):
        """run_scout pasa el SYSTEM_PROMPT correcto a la API."""
        from scout import run_scout, SYSTEM_PROMPT
        end_response = self._make_end_turn_response()
        mock_client = self._make_mock_client([end_response])
        with patch("scout.anthropic.Anthropic", return_value=mock_client):
            run_scout("test", verbose=False)
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["system"] == SYSTEM_PROMPT

    def test_run_scout_passes_only_scout_tools(self):
        """run_scout pasa solo las tools del scout (no las del especialista)."""
        from scout import run_scout, TOOLS
        end_response = self._make_end_turn_response()
        mock_client = self._make_mock_client([end_response])
        with patch("scout.anthropic.Anthropic", return_value=mock_client):
            run_scout("test", verbose=False)
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["tools"] == TOOLS
        assert len(call_kwargs["tools"]) == 1

    def test_run_scout_executes_tool_call_and_continues(self):
        """Cuando el modelo pide una tool call, el scout la ejecuta y continúa."""
        from scout import run_scout
        tool_response = self._make_tool_use_response(
            "search_literature",
            {"query": "phytase animal feed"},
        )
        end_response = self._make_end_turn_response("Candidatos encontrados.")
        mock_client = self._make_mock_client([tool_response, end_response])
        lit_result = {"results": [{"title": "Phytase paper", "abstract": "..."}], "total_found": 1}
        with patch("scout.anthropic.Anthropic", return_value=mock_client):
            with patch("scout.search_literature", return_value=lit_result):
                result = run_scout("test", verbose=False)
        assert mock_client.messages.create.call_count == 2
        assert "Candidatos" in result

    def test_run_scout_retry_on_rate_limit(self):
        """run_scout reintenta hasta 4 veces ante RateLimitError de Anthropic."""
        from scout import run_scout
        import anthropic as anthropic_module
        end_response = self._make_end_turn_response("OK")
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            anthropic_module.RateLimitError.__new__(anthropic_module.RateLimitError),
            end_response,
        ]
        with patch("scout.anthropic.Anthropic", return_value=mock_client):
            with patch("scout.time.sleep"):  # no esperar en tests
                result = run_scout("test", verbose=False)
        assert mock_client.messages.create.call_count == 2

    def test_run_scout_max_tokens_returns_text(self):
        """Si stop_reason es max_tokens, run_scout igual retorna el texto disponible."""
        from scout import run_scout
        block = MagicMock()
        block.type = "text"
        block.text = "Análisis parcial por límite de tokens."
        response = MagicMock()
        response.stop_reason = "max_tokens"
        response.content = [block]
        mock_client = self._make_mock_client([response])
        with patch("scout.anthropic.Anthropic", return_value=mock_client):
            result = run_scout("test", verbose=False)
        assert "parcial" in result


# ──────────────────────────────────────────────
# INTEGRATION TESTS — requieren red y API keys
# ──────────────────────────────────────────────

@pytest.mark.integration
class TestScoutIntegration:

    def test_scout_returns_nonempty_result(self):
        """Un run real devuelve texto no vacío."""
        from scout import run_scout
        result = run_scout(
            "Identificar una oportunidad B2B en biotecnología para nutrición animal.",
            verbose=False,
        )
        assert len(result) > 100

    def test_scout_output_mentions_candidatos(self):
        """El output real incluye la sección de candidatos."""
        from scout import run_scout
        result = run_scout(
            "Identificar una oportunidad B2B en biotecnología para nutrición animal.",
            verbose=False,
        )
        assert "candidato" in result.lower() or "Candidato" in result

    def test_scout_uses_search_literature(self):
        """Un run real llama a search_literature al menos una vez."""
        from scout import run_scout
        with patch("scout.search_literature", wraps=__import__("tools").search_literature) as mock_search:
            run_scout(
                "Identificar una oportunidad en biotecnología.",
                verbose=False,
            )
        assert mock_search.call_count >= 1
