"""
Web fetch dirigido — extrae texto limpio de páginas web específicas.

Diseñado para fuentes argentinas sin API pública:
- BCR (Bolsa de Cereales de Rosario): bcr.com.ar
- CAENA (Cámara Argentina de Empresas de Nutrición Animal): caena.org.ar
- INTA: inta.gob.ar
- SENASA: senasa.gob.ar
- MAGYP: magyp.gob.ar

Devuelve texto limpio (sin HTML) listo para que el agente lo procese.
No tiene API key — hace requests HTTP directos con User-Agent real.
"""

import re
import requests
from typing import Optional

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
}

MAX_TEXT_CHARS = 8000


def fetch_page_text(url: str, max_chars: int = MAX_TEXT_CHARS) -> dict:
    """
    Descarga una URL y retorna el texto limpio (HTML removido).

    Args:
        url: URL a descargar (debe ser pública, sin login)
        max_chars: Máximo de caracteres de texto a retornar

    Returns:
        dict con:
          success: bool
          url: URL consultada
          text: texto limpio extraído (hasta max_chars caracteres)
          char_count: largo del texto extraído
          truncated: bool — si el texto fue truncado
          source: "web_fetch [ESTIMADO, fuente: {dominio}]"
          error: mensaje si falla
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        html = resp.text
    except requests.RequestException as e:
        return {
            "success": False,
            "url": url,
            "text": "",
            "char_count": 0,
            "truncated": False,
            "source": f"web_fetch",
            "error": f"Error al acceder a {url}: {e}",
        }

    text = _clean_html(html)
    truncated = len(text) > max_chars
    text_out = text[:max_chars]

    domain = _extract_domain(url)

    return {
        "success": True,
        "url": url,
        "text": text_out,
        "char_count": len(text_out),
        "truncated": truncated,
        "source": f"web_fetch [ESTIMADO, fuente: {domain}]",
        "error": None,
    }


def _clean_html(html: str) -> str:
    """Extrae texto limpio de HTML — remueve scripts, styles y tags."""
    # Remover scripts y styles completos
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    # Remover todos los tags HTML
    text = re.sub(r"<[^>]+>", " ", text)
    # Decodificar entidades HTML básicas
    text = (
        text.replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&nbsp;", " ")
            .replace("&quot;", '"')
            .replace("&#39;", "'")
    )
    # Colapsar whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_domain(url: str) -> str:
    """Extrae el dominio de una URL."""
    match = re.search(r"https?://([^/]+)", url)
    return match.group(1) if match else url
