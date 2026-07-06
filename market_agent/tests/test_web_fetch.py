"""
Tests para tools/web_fetch.py
"""

import pytest
from unittest.mock import patch, MagicMock


# ── Unit tests ────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_fetch_page_text_extracts_clean_text():
    """Debe remover HTML y retornar texto limpio."""
    from tools.web_fetch import fetch_page_text
    html = "<html><head><style>body {}</style></head><body><h1>Fitasa</h1><p>Precio: USD 50/kg</p></body></html>"
    mock_resp = MagicMock()
    mock_resp.text = html
    mock_resp.raise_for_status.return_value = None

    with patch("tools.web_fetch.requests.get", return_value=mock_resp):
        result = fetch_page_text("https://example.com/fitasa")

    assert result["success"] is True
    assert "Fitasa" in result["text"]
    assert "Precio" in result["text"]
    assert "<" not in result["text"]
    assert "body {}" not in result["text"]


@pytest.mark.unit
def test_fetch_page_text_removes_scripts():
    """Scripts deben ser removidos del output."""
    from tools.web_fetch import fetch_page_text
    html = "<html><body><script>alert('xss')</script><p>Contenido real</p></body></html>"
    mock_resp = MagicMock()
    mock_resp.text = html
    mock_resp.raise_for_status.return_value = None

    with patch("tools.web_fetch.requests.get", return_value=mock_resp):
        result = fetch_page_text("https://example.com")

    assert "alert" not in result["text"]
    assert "Contenido real" in result["text"]


@pytest.mark.unit
def test_fetch_page_text_truncates_at_max_chars():
    """Textos largos deben truncarse y marcar truncated=True."""
    from tools.web_fetch import fetch_page_text
    html = f"<p>{'A' * 20_000}</p>"
    mock_resp = MagicMock()
    mock_resp.text = html
    mock_resp.raise_for_status.return_value = None

    with patch("tools.web_fetch.requests.get", return_value=mock_resp):
        result = fetch_page_text("https://example.com", max_chars=1000)

    assert result["truncated"] is True
    assert len(result["text"]) == 1000


@pytest.mark.unit
def test_fetch_page_text_http_error():
    """Error HTTP debe retornar success=False con mensaje claro."""
    import requests as req
    from tools.web_fetch import fetch_page_text

    with patch("tools.web_fetch.requests.get", side_effect=req.RequestException("404 Not Found")):
        result = fetch_page_text("https://example.com/notfound")

    assert result["success"] is False
    assert result["text"] == ""
    assert "error" in result


@pytest.mark.unit
def test_fetch_page_text_source_label_contains_domain():
    """El label de source debe contener el dominio de la URL."""
    from tools.web_fetch import fetch_page_text
    mock_resp = MagicMock()
    mock_resp.text = "<p>test</p>"
    mock_resp.raise_for_status.return_value = None

    with patch("tools.web_fetch.requests.get", return_value=mock_resp):
        result = fetch_page_text("https://bcr.com.ar/informes/fitasa")

    assert "bcr.com.ar" in result["source"]
    assert "ESTIMADO" in result["source"]


@pytest.mark.unit
def test_fetch_page_text_decodes_html_entities():
    """Entidades HTML básicas deben decodificarse."""
    from tools.web_fetch import fetch_page_text
    html = "<p>Precio &amp; condiciones: &lt;USD 50/kg&gt;</p>"
    mock_resp = MagicMock()
    mock_resp.text = html
    mock_resp.raise_for_status.return_value = None

    with patch("tools.web_fetch.requests.get", return_value=mock_resp):
        result = fetch_page_text("https://example.com")

    assert "&amp;" not in result["text"]
    assert "&" in result["text"]


# ── Integration tests ─────────────────────────────────────────────────────────

@pytest.mark.integration
def test_fetch_page_text_real_inta():
    """Fetch real de INTA — página pública sin login."""
    from tools.web_fetch import fetch_page_text
    result = fetch_page_text("https://www.inta.gob.ar", max_chars=2000)
    # INTA puede tener protección. Solo verificar que la función no explota.
    assert "success" in result
    assert "source" in result
    if result["success"]:
        assert len(result["text"]) > 0
