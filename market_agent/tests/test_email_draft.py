"""
Tests para tools/email_draft.py

La tool NUNCA envía emails — solo redacta.
Los tests verifican que el draft sea correcto y que el status sea siempre PENDIENTE_APROBACION.
"""

import pytest
from market_agent.tools.email_draft import draft_outreach_email


# ── Unit tests ────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_draft_email_returns_pendiente():
    """El status siempre debe ser PENDIENTE_APROBACION — nunca enviado."""
    result = draft_outreach_email(
        recipient_company="DSM Argentina",
        recipient_role="Gerente Comercial",
        product_or_ingredient="fitasa enzimática",
        context="Análisis de mercado para producción local por fermentación",
    )
    assert result["success"] is True
    assert result["status"] == "PENDIENTE_APROBACION"


@pytest.mark.unit
def test_draft_email_warning_present():
    """Debe incluir warning explícito de que requiere aprobación."""
    result = draft_outreach_email(
        recipient_company="Novozymes",
        recipient_role="Area Ventas",
        product_or_ingredient="xilanasa",
        context="Relevamiento de precios y disponibilidad",
    )
    assert "REQUIERE APROBACIÓN" in result["warning"] or "APROBACI" in result["warning"]


@pytest.mark.unit
def test_draft_email_contains_product():
    """El draft debe mencionar el producto en el asunto y en el cuerpo."""
    result = draft_outreach_email(
        recipient_company="BASF Argentina",
        recipient_role="Gerente de Compras",
        product_or_ingredient="lactoferrina bovina",
        context="Precio CIF y condiciones de importación",
    )
    assert "lactoferrina bovina" in result["draft"].lower() or "lactoferrina" in result["subject"].lower()
    assert result["product"] == "lactoferrina bovina"


@pytest.mark.unit
def test_draft_email_spanish_by_default():
    """El idioma por defecto debe ser español."""
    result = draft_outreach_email(
        recipient_company="Empresa Test",
        recipient_role="Gerente",
        product_or_ingredient="fitasa",
        context="test",
    )
    assert "Estimado" in result["body"] or "estimado" in result["body"].lower()
    assert "Asunto" in result["draft"]


@pytest.mark.unit
def test_draft_email_english_option():
    """Con language='en' debe redactar en inglés."""
    result = draft_outreach_email(
        recipient_company="Novozymes",
        recipient_role="Sales Manager",
        product_or_ingredient="phytase",
        context="Market research for local production",
        language="en",
    )
    assert "Dear" in result["body"]
    assert "phytase" in result["body"].lower()


@pytest.mark.unit
def test_draft_email_recipient_company_in_result():
    """El nombre de la empresa debe estar en el resultado para trazabilidad."""
    result = draft_outreach_email(
        recipient_company="Biogénesis Bagó",
        recipient_role="Área Técnica",
        product_or_ingredient="enzimas digestivas",
        context="Precios de referencia para análisis competitivo",
    )
    assert result["recipient_company"] == "Biogénesis Bagó"


@pytest.mark.unit
def test_draft_email_has_subject_and_body():
    """El resultado debe tener subject, body y draft (subject + body combinados)."""
    result = draft_outreach_email(
        recipient_company="Test Co",
        recipient_role="Gerente",
        product_or_ingredient="xilanasa",
        context="test context",
    )
    assert result["subject"]
    assert result["body"]
    assert result["draft"]
    assert result["subject"] in result["draft"]
    assert result["body"] in result["draft"]


@pytest.mark.unit
def test_draft_email_custom_sender():
    """El nombre del remitente personalizado debe aparecer en el cuerpo."""
    result = draft_outreach_email(
        recipient_company="Test Co",
        recipient_role="Gerente",
        product_or_ingredient="fitasa",
        context="test",
        sender_name="Sebastián Bizzi",
    )
    assert "Sebastián Bizzi" in result["body"]
