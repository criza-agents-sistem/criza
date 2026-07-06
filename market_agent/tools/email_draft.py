"""
Redacción de emails de contacto comercial.

Regla no negociable: NUNCA envía. Solo redacta.
El usuario revisa y aprueba antes de cualquier acción externa.

El agente usa esta tool para redactar emails a empresas relevantes
solicitando precios, condiciones comerciales o información técnica.
"""


def draft_outreach_email(
    recipient_company: str,
    recipient_role: str,
    product_or_ingredient: str,
    context: str,
    sender_name: str = "Equipo CRIZA",
    sender_org: str = "CRIZA — Plataforma de Transferencia Tecnológica",
    language: str = "es",
) -> dict:
    """
    Redacta un email de contacto comercial para aprobación humana.

    IMPORTANTE: Esta tool NUNCA envía el email. Solo lo redacta.
    El usuario debe revisar y aprobar antes de enviarlo.

    Args:
        recipient_company: Nombre de la empresa destinataria
        recipient_role: Cargo/área del destinatario (ej: "Gerente Comercial", "Área de Compras")
        product_or_ingredient: Producto o ingrediente sobre el que se consulta
        context: Contexto del análisis de mercado (por qué se contacta, qué info se necesita)
        sender_name: Nombre del remitente
        sender_org: Organización del remitente
        language: Idioma del email ("es" o "en")

    Returns:
        dict con:
          success: bool
          draft: texto completo del email (asunto + cuerpo)
          subject: asunto del email
          body: cuerpo del email
          recipient_company: empresa destinataria
          status: "PENDIENTE_APROBACION" — siempre, nunca cambia a enviado aquí
          warning: recordatorio de que requiere aprobación humana
    """
    if language == "en":
        subject = f"Inquiry: {product_or_ingredient} — pricing and commercial conditions"
        body = _draft_english(
            recipient_company, recipient_role, product_or_ingredient,
            context, sender_name, sender_org,
        )
    else:
        subject = f"Consulta: {product_or_ingredient} — precios y condiciones comerciales"
        body = _draft_spanish(
            recipient_company, recipient_role, product_or_ingredient,
            context, sender_name, sender_org,
        )

    full_draft = f"Asunto: {subject}\n\n{body}"

    return {
        "success": True,
        "draft": full_draft,
        "subject": subject,
        "body": body,
        "recipient_company": recipient_company,
        "product": product_or_ingredient,
        "status": "PENDIENTE_APROBACION",
        "warning": (
            "⚠️ REQUIERE APROBACIÓN HUMANA antes de enviar. "
            "Este email NO fue enviado. Revisar contenido y confirmar destinatario."
        ),
    }


def _draft_spanish(
    company: str,
    role: str,
    product: str,
    context: str,
    sender: str,
    org: str,
) -> str:
    return f"""Estimado/a {role} de {company}:

Mi nombre es {sender}, del equipo de {org}. Estamos realizando un análisis de mercado
sobre {product} en el contexto de la industria argentina, y su empresa figura como
un referente relevante en el sector.

El motivo de este contacto es consultarles sobre:

1. Disponibilidad actual de {product} en el mercado local
2. Rango de precios orientativos (precio lista o precio por volumen)
3. Condiciones comerciales habituales (incoterm, tiempos de entrega, volumen mínimo)
4. Forma de presentación disponible (granel, envasado, especificación técnica)

Contexto adicional: {context}

Toda la información que compartan será tratada con absoluta confidencialidad
y utilizada exclusivamente para fines de análisis de transferencia tecnológica.

Quedamos a disposición para cualquier consulta o para coordinar una llamada breve.

Muchas gracias por su tiempo.

Saludos cordiales,

{sender}
{org}
"""


def _draft_english(
    company: str,
    role: str,
    product: str,
    context: str,
    sender: str,
    org: str,
) -> str:
    return f"""Dear {role} at {company},

My name is {sender}, from {org}. We are conducting a market analysis
on {product} in the context of the Argentine industry, and your company
is a relevant reference in the sector.

The purpose of this contact is to inquire about:

1. Current availability of {product} in the local market
2. Indicative price range (list price or volume pricing)
3. Standard commercial conditions (incoterm, lead times, minimum order)
4. Available presentation format (bulk, packaged, technical specification)

Additional context: {context}

All information shared will be treated with strict confidentiality
and used solely for technology transfer analysis purposes.

We are available for any questions or to schedule a brief call.

Thank you for your time.

Best regards,

{sender}
{org}
"""
