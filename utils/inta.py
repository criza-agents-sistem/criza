"""
INTA — conector para el repositorio institucional INTA Digital.

Dos modos de acceso:
  1. search(query)      — busca por keyword via discover (web scraping)
  2. harvest(set_id)    — cosecha bulk via OAI-PMH por instituto

Cada función retorna lista de dicts con estructura homogénea (ver _parse_record).
El llamador decide si persiste en el KM o usa los resultados directamente.

Para descargar PDFs:
  from knowledge_module.document_store.store import download_and_extract
  path, text = download_and_extract(record["pdf_url"], instance="criza")
"""

import html
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

# ── constantes ──────────────────────────────────────────────────────────────

_REPO     = "https://repositorio.inta.gob.ar"
_OAI_BASE = f"{_REPO}/oai/request"
_HEADERS  = {"User-Agent": "CRIZA-agent/1.0"}
_TIMEOUT  = 15

_NS_OAI = "http://www.openarchives.org/OAI/2.0/"
_NS_DC  = "http://purl.org/dc/elements/1.1/"
_NS     = {"oai": _NS_OAI, "dc": _NS_DC}

# Sets de los institutos biotech relevantes para CRIZA
SETS_BIOTECH = {
    "biotecnologia":  "com_20.500.12123_172",
    "microbiologia":  "com_20.500.12123_174",
    "patobiologia":   "com_20.500.12123_175",
    "genetica":       "com_20.500.12123_173",
    "virologia":      "com_20.500.12123_176",
    "civcya":         "com_20.500.12123_171",  # paraguas de los 5 anteriores
}


# ── helpers internos ─────────────────────────────────────────────────────────

def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        return r.read()


def _oai(verb: str, **params) -> ET.Element:
    p = "&".join(f"{k}={v}" for k, v in {"verb": verb, **params}.items())
    return ET.fromstring(_get(f"{_OAI_BASE}?{p}"))


def _dc(elem: ET.Element, tag: str) -> list[str]:
    """Todos los valores de un campo dc:tag dentro de un registro."""
    return [e.text for e in elem.findall(f".//{{{_NS_DC}}}{tag}") if e.text]


def _find_pdf_url(identifiers: list[str], rights: list[str]) -> Optional[str]:
    """
    Intenta encontrar la URL del PDF entre los identificadores del registro.
    Solo retorna URL si el acceso es openAccess.
    """
    is_open = any("openAccess" in r for r in rights)
    if not is_open:
        return None

    for ident in identifiers:
        low = ident.lower()
        # URL que apunta directo a un PDF (bitstream INTA o PDF externo)
        if low.endswith(".pdf") or "bitstream" in low or "epdf" in low:
            return ident
    return None


def _extract_date(dates: list[str]) -> Optional[str]:
    """
    De la lista de dc:date retorna el año de publicación.
    DSpace mete fecha de ingesta (ISO) y fecha de publicación (año o año-mes).
    Toma el valor más corto que parezca año de publicación.
    """
    years = [d for d in dates if re.match(r"^\d{4}$", d.strip())]
    if years:
        return years[0]
    # Fallback: primer valor que empiece con 4 dígitos
    for d in dates:
        m = re.match(r"^(\d{4})", d.strip())
        if m:
            return m.group(1)
    return None


def _parse_record(record: ET.Element) -> Optional[dict]:
    """
    Convierte un elemento <record> OAI-PMH en un dict homogéneo.
    Retorna None si el registro está marcado como deleted.
    """
    header = record.find(f"{{{_NS_OAI}}}header")
    if header is not None and header.attrib.get("status") == "deleted":
        return None

    meta = record.find(f".//{{{_NS_OAI}}}metadata")
    if meta is None:
        return None

    identifier_elem = record.find(f".//{{{_NS_OAI}}}identifier")
    oai_id = identifier_elem.text if identifier_elem is not None else ""

    # handle: oai:repositorio.inta.gob.ar:20.500.12123/113 → 20.500.12123/113
    handle_id = oai_id.split(":")[-1] if oai_id else ""
    handle_url = f"https://hdl.handle.net/{handle_id}" if handle_id else ""

    titles       = _dc(meta, "title")
    creators     = _dc(meta, "creator")
    dates        = _dc(meta, "date")
    subjects     = _dc(meta, "subject")
    descriptions = _dc(meta, "description")
    identifiers  = _dc(meta, "identifier")
    rights       = _dc(meta, "rights")
    types        = _dc(meta, "type")
    languages    = _dc(meta, "language")
    sources      = _dc(meta, "source")

    # El abstract es el primer dc:description que tenga más de 80 chars
    abstract = next((d for d in descriptions if len(d) > 80), "")

    # DOI: identificador que empieza con doi.org o 10.
    doi = next(
        (i for i in identifiers if "doi.org" in i.lower() or i.startswith("10.")),
        None
    )

    pdf_url = _find_pdf_url(identifiers, rights)
    is_open = any("openAccess" in r for r in rights)

    return {
        "oai_id":      oai_id,
        "handle_id":   handle_id,
        "handle_url":  handle_url,
        "titulo":      titles[0] if titles else "",
        "autores":     creators,
        "año":         _extract_date(dates),
        "subjects":    subjects,
        "abstract":    abstract,
        "doi":         doi,
        "pdf_url":     pdf_url,
        "open_access": is_open,
        "tipo":        next((t for t in types if "article" in t or "thesis" in t or "report" in t), types[0] if types else ""),
        "idioma":      languages[0] if languages else "",
        "fuente":      sources[0] if sources else "",
        "institutos":  [s.text for s in record.findall(f".//{{{_NS_OAI}}}setSpec") if s.text],
    }


# ── API pública ──────────────────────────────────────────────────────────────

def search(query: str, max_results: int = 20) -> list[dict]:
    """
    Busca en INTA Digital por keyword via discover (scraping HTML).

    Retorna lista de dicts con metadata básica + handle.
    Para metadata completa, usar get_record() sobre cada resultado.

    Args:
        query:       Término de búsqueda (ej. "garrapata control biologico").
        max_results: Máximo de resultados a retornar (el discover pagina de a 10).
    """
    results = []
    page = 1
    while len(results) < max_results:
        url = f"{_REPO}/discover?query={urllib.parse.quote(query)}&rpp=10&start={(page-1)*10}"
        try:
            body = _get(url).decode("utf-8", errors="replace")
        except urllib.error.HTTPError:
            break

        handles = re.findall(r'href="(/handle/20\.500\.12123/\d+)"', body)
        if not handles:
            break

        titles_raw  = re.findall(r"<h4>(.*?)</h4>", body, re.DOTALL)
        authors_raw = re.findall(r'<span class="author h4">(.*?)</span>', body, re.DOTALL)
        dates_raw   = re.findall(r'<span class="publisher-date h4"><small>(.*?)</small>', body, re.DOTALL)

        for i, handle_path in enumerate(handles):
            handle_id  = handle_path.lstrip("/handle/")
            title_html = titles_raw[i] if i < len(titles_raw) else ""
            title      = html.unescape(re.sub(r"<[^>]+>", "", title_html)).replace("\xa0", "").strip()
            author_html = authors_raw[i] if i < len(authors_raw) else ""
            authors    = [re.sub(r"<[^>]+>", "", a).strip()
                          for a in re.findall(r'<span[^>]*>(.*?)</span>', author_html)]
            date_html  = dates_raw[i] if i < len(dates_raw) else ""
            date_clean = re.sub(r"<[^>]+>", "", date_html).strip()
            year_m     = re.search(r"\d{4}", date_clean)

            results.append({
                "handle_id":  handle_id,
                "handle_url": f"https://hdl.handle.net/{handle_id}",
                "titulo":     title,
                "autores":    [a for a in authors if a],
                "año":        year_m.group(0) if year_m else None,
                "fuente_html": date_clean,
            })
            if len(results) >= max_results:
                break

        # Si en esta página no llegamos al máximo → no hay más páginas
        if len(handles) < 10:
            break
        page += 1
        time.sleep(0.3)

    return results


def get_record(handle_id: str) -> Optional[dict]:
    """
    Obtiene metadata completa de un documento via OAI-PMH GetRecord.

    Args:
        handle_id: El handle sin prefijo "oai:" (ej. "20.500.12123/913").

    Returns:
        Dict con metadata completa, o None si no existe.
    """
    oai_id = f"oai:repositorio.inta.gob.ar:{handle_id}"
    try:
        root = _oai("GetRecord", identifier=oai_id, metadataPrefix="oai_dc")
        record = root.find(f".//{{{_NS_OAI}}}record")
        if record is None:
            return None
        return _parse_record(record)
    except urllib.error.HTTPError:
        return None


def harvest(
    set_id: str,
    from_date: Optional[str] = None,
    until_date: Optional[str] = None,
    max_records: Optional[int] = None,
    delay: float = 0.2,
) -> list[dict]:
    """
    Cosecha todos los registros de un set OAI-PMH.

    Args:
        set_id:      Spec del set (ej. "com_20.500.12123_172" o clave de SETS_BIOTECH).
        from_date:   Fecha inicio ISO (ej. "2022-01-01"). Opcional.
        until_date:  Fecha fin ISO. Opcional.
        max_records: Límite de registros. None = sin límite.
        delay:       Segundos entre páginas (default 0.2 para no sobrecargar).

    Returns:
        Lista de dicts con metadata completa de cada registro.
    """
    # Acepta claves cortas como "biotecnologia" o set specs directos
    resolved_set = SETS_BIOTECH.get(set_id, set_id)

    params: dict = {"metadataPrefix": "oai_dc", "set": resolved_set}
    if from_date:
        params["from"] = from_date
    if until_date:
        params["until"] = until_date

    records = []
    resumption_token = None

    while True:
        if resumption_token:
            root = _oai("ListRecords", resumptionToken=resumption_token)
        else:
            root = _oai("ListRecords", **params)

        for elem in root.findall(f".//{{{_NS_OAI}}}record"):
            parsed = _parse_record(elem)
            if parsed:
                records.append(parsed)
            if max_records and len(records) >= max_records:
                return records

        token_elem = root.find(f".//{{{_NS_OAI}}}resumptionToken")
        if token_elem is not None and token_elem.text:
            resumption_token = token_elem.text
            time.sleep(delay)
        else:
            break

    return records


def harvest_biotech(from_date: Optional[str] = None) -> list[dict]:
    """
    Cosecha todos los institutos biotech relevantes para CRIZA (CICVyA).
    Equivale a harvest("civcya") pero más explícito en el nombre.
    """
    return harvest("civcya", from_date=from_date)


def get_pdf_url(handle_id: str) -> Optional[str]:
    """
    Busca la URL del PDF en la página del item (bitstream alojado en INTA).

    Solo retorna URL para PDFs alojados en repositorio.inta.gob.ar.
    Los PDFs en publishers externos (Wiley, Springer, etc.) no son accesibles
    sin credenciales y no se devuelven aquí.

    Args:
        handle_id: ej. "20.500.12123/23889"

    Returns:
        URL completa al PDF o None si no hay bitstream PDF disponible.
    """
    url = f"{_REPO}/handle/{handle_id}"
    try:
        body = _get(url).decode("utf-8", errors="replace")
    except (urllib.error.HTTPError, Exception):
        return None

    # DSpace muestra los bitstreams como /bitstream/handle/{id}/{filename}.pdf
    matches = re.findall(
        r'href="(/bitstream/handle/[^"?]+\.pdf)(?:\?[^"]*)?"',
        body,
    )
    if matches:
        return f"{_REPO}{matches[0]}"
    return None
