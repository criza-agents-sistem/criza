"""
download_pdfs.py — Descarga PDFs open-access de INTA y actualiza texto_completo en el KM.

Flujo:
  1. Re-cosecha metadata OAI-PMH de CICVyA (solo headers, no descarga PDFs aún)
     → construye mapa handle_url → {pdf_url, open_access, handle_id}
  2. Consulta KM: documentos INTA sin texto_completo
  3. Para cada uno con pdf_url disponible:
       a. Si ya está en disco → solo extrae y actualiza KM
       b. Si no → descarga → extrae → actualiza KM
  4. Si --scrape-missing: para los open_access sin pdf_url en metadata,
     scrapea la página INTA para buscar el bitstream (1 req extra por doc)

Idempotente:
  - No re-descarga PDFs ya en disco (DocumentStore usa hash de URL)
  - Solo actualiza documentos donde texto_completo IS NULL

Uso:
    python criza/ingest/download_pdfs.py                # todo CICVyA
    python criza/ingest/download_pdfs.py --limit 50     # primeros 50 con PDF
    python criza/ingest/download_pdfs.py --dry-run      # muestra sin descargar
    python criza/ingest/download_pdfs.py --scrape-missing  # busca más PDFs via scraping
"""

import argparse
import asyncio
import sys
import time
from pathlib import Path

# ── encoding Windows ─────────────────────────────────────────────────────────
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── paths ─────────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).parent.parent.parent
_KM   = _ROOT / "knowledge_module"

for p in [str(_ROOT), str(_KM)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from dotenv import load_dotenv
load_dotenv(_KM / ".env")

from sqlalchemy import text as sa_text

from criza.utils.inta import harvest, get_pdf_url, SETS_BIOTECH
from plataforma.document_store.store import download_and_extract, pdf_exists, pdf_path
from db import get_session_factory

# ── constantes ─────────────────────────────────────────────────────────────────
_MAX_TEXTO = 60_000   # chars máx por documento (≈30 páginas densas)
_DELAY_SCRAPE = 0.5   # segundos entre scraping de páginas INTA


# ── helpers de DB ─────────────────────────────────────────────────────────────

async def _get_docs_sin_texto() -> list[dict]:
    """Retorna documentos INTA cosechados que no tienen texto_completo aún."""
    async with get_session_factory()() as s:
        r = await s.execute(
            sa_text("""
                SELECT id::text, fuente_url
                FROM documento
                WHERE agente = 'harvest'
                  AND texto_completo IS NULL
                  AND fuente_url LIKE '%hdl.handle.net%'
                ORDER BY fecha DESC
            """)
        )
        return [{"id": row.id, "fuente_url": row.fuente_url} for row in r.fetchall()]


def _sanitize(text: str) -> str:
    """Strip characters PostgreSQL/asyncpg cannot store: null bytes and lone surrogates."""
    text = text.replace('\x00', '')
    text = text.encode('utf-8', errors='surrogatepass').decode('utf-8', errors='ignore')
    return text


async def _update_texto(documento_id: str, texto: str) -> bool:
    """
    Actualiza texto_completo de un documento.
    Solo actúa si texto_completo IS NULL (no sobrescribe).
    """
    async with get_session_factory()() as s:
        r = await s.execute(
            sa_text("""
                UPDATE documento
                SET texto_completo = :texto
                WHERE id = :id AND texto_completo IS NULL
                RETURNING id
            """),
            {"texto": _sanitize(texto[:_MAX_TEXTO]), "id": documento_id},
        )
        updated = r.fetchone() is not None
        await s.commit()
        return updated


# ── lógica principal ──────────────────────────────────────────────────────────

def _handle_id_from_url(fuente_url: str) -> str:
    """https://hdl.handle.net/20.500.12123/23889 → 20.500.12123/23889"""
    return (
        fuente_url
        .replace("https://hdl.handle.net/", "")
        .replace("http://hdl.handle.net/", "")
        .strip("/")
    )


def _build_pdf_map(records: list[dict]) -> dict[str, dict]:
    """
    Construye mapa: handle_url → {pdf_url, open_access, handle_id}.
    Usa los datos del OAI-PMH (sin scraping extra).
    """
    m = {}
    for rec in records:
        url = rec.get("handle_url", "")
        if url:
            m[url] = {
                "pdf_url":     rec.get("pdf_url"),
                "open_access": rec.get("open_access", False),
                "handle_id":   rec.get("handle_id", ""),
            }
    return m


async def run(
    set_id: str = "civcya",
    limit: int | None = None,
    dry_run: bool = False,
    scrape_missing: bool = False,
) -> dict:
    stats = {
        "docs_sin_texto": 0,
        "con_pdf_metadata": 0,
        "scrapeados": 0,
        "descargados": 0,
        "ya_en_disco": 0,
        "actualizados_km": 0,
        "sin_texto_en_pdf": 0,
        "sin_pdf": 0,
        "errores": 0,
    }

    # ── 1. Re-cosechar metadata OAI-PMH ──────────────────────────────────────
    print(f"Re-cosechando metadata de '{set_id}' (sin PDFs)...")
    records = harvest(set_id)
    print(f"  {len(records)} registros en OAI-PMH")
    pdf_map = _build_pdf_map(records)

    con_pdf_directo = sum(1 for v in pdf_map.values() if v["pdf_url"])
    con_oa_sin_pdf  = sum(1 for v in pdf_map.values() if v["open_access"] and not v["pdf_url"])
    print(f"  Con PDF en metadata: {con_pdf_directo} | Open access sin PDF directo: {con_oa_sin_pdf}")

    # ── 2. Documentos sin texto en KM ─────────────────────────────────────────
    print("\nConsultando KM — documentos sin texto_completo...")
    docs = await _get_docs_sin_texto()
    stats["docs_sin_texto"] = len(docs)
    print(f"  {len(docs)} documentos pendientes")

    if not docs:
        print("  Nada que hacer.")
        return stats

    if limit:
        print(f"  (limitado a {limit} por --limit)")

    # ── 3. Procesar ──────────────────────────────────────────────────────────
    print()
    procesados = 0
    for i, doc in enumerate(docs, 1):
        fuente_url = doc["fuente_url"]
        doc_id     = doc["id"]
        info       = pdf_map.get(fuente_url, {})

        pdf_url    = info.get("pdf_url")
        open_access = info.get("open_access", False)
        handle_id  = info.get("handle_id") or _handle_id_from_url(fuente_url)

        # Buscar PDF via scraping si --scrape-missing y no hay pdf_url en metadata
        if not pdf_url and open_access and scrape_missing:
            time.sleep(_DELAY_SCRAPE)
            pdf_url = get_pdf_url(handle_id)
            if pdf_url:
                stats["scrapeados"] += 1

        if not pdf_url:
            stats["sin_pdf"] += 1
            continue

        stats["con_pdf_metadata"] += 1
        procesados += 1

        if limit and procesados > limit:
            break

        # ── Dry run ───────────────────────────────────────────────────────
        if dry_run:
            print(f"  DRY [{procesados}] {handle_id} → {pdf_url[:70]}")
            continue

        # ── Descargar si no está en disco ─────────────────────────────────
        try:
            already = pdf_exists(pdf_url, "criza")
            if already:
                stats["ya_en_disco"] += 1
                # Extrae de disco (no red)
                from plataforma.document_store.store import extract_text as _extract
                p = pdf_path(pdf_url, "criza")
                texto = _extract(p) if p else ""
            else:
                _, texto = download_and_extract(pdf_url, "criza")
                stats["descargados"] += 1

            if not texto.strip():
                stats["sin_texto_en_pdf"] += 1
                tag = "vacío/escaneado"
            else:
                updated = await _update_texto(doc_id, texto)
                if updated:
                    stats["actualizados_km"] += 1
                tag = f"{len(texto):,} chars → KM"

            sym = "✓" if texto.strip() else "·"
            print(f"  {sym} [{procesados}] {handle_id[:30]}  {tag}")

        except Exception as exc:
            stats["errores"] += 1
            print(f"  ✗ [{procesados}] {handle_id[:30]}  ERROR: {exc}")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Descargar PDFs INTA → texto_completo en KM")
    parser.add_argument("--set",     default="civcya",
                        help=f"Set OAI-PMH. Claves: {list(SETS_BIOTECH.keys())}. Default: civcya")
    parser.add_argument("--limit",   type=int, default=None,
                        help="Máximo de PDFs a procesar en esta corrida (default: sin límite)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Muestra qué haría sin descargar ni actualizar")
    parser.add_argument("--scrape-missing", action="store_true",
                        help="Para docs open_access sin pdf_url en metadata, scrapea la página INTA")
    args = parser.parse_args()

    from db import reset_engine
    reset_engine()

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    stats = asyncio.run(run(
        set_id=args.set,
        limit=args.limit,
        dry_run=args.dry_run,
        scrape_missing=args.scrape_missing,
    ))

    print()
    print("=== Resultado ===")
    print(f"  Docs sin texto en KM:      {stats['docs_sin_texto']}")
    print(f"  Con PDF (metadata OAI):    {stats['con_pdf_metadata']}")
    if args.scrape_missing:
        print(f"  Con PDF (via scraping):    {stats['scrapeados']}")
    print(f"  Descargados (nuevo):       {stats['descargados']}")
    print(f"  Ya en disco (skip):        {stats['ya_en_disco']}")
    print(f"  Actualizados en KM:        {stats['actualizados_km']}")
    print(f"  Sin texto en PDF:          {stats['sin_texto_en_pdf']}")
    print(f"  Sin PDF disponible:        {stats['sin_pdf']}")
    print(f"  Errores:                   {stats['errores']}")


if __name__ == "__main__":
    main()
