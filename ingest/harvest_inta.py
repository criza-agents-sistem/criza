"""
Harvest INTA → KM

Cosecha los institutos biotech de INTA Digital y persiste los registros
en el Knowledge Module como nodos Documento.

Uso:
    python criza/ingest/harvest_inta.py                     # cosecha CICVyA completo
    python criza/ingest/harvest_inta.py --set biotecnologia # un solo instituto
    python criza/ingest/harvest_inta.py --desde 2023-01-01  # solo desde esa fecha
    python criza/ingest/harvest_inta.py --con-pdf           # también baja PDFs open access

Flags:
    --set {nombre}   Clave de SETS_BIOTECH o spec de set directo
    --desde YYYY-MM-DD
    --con-pdf        Activa descarga de PDFs + extracción de texto
    --dry-run        Muestra qué haría sin escribir al KM
"""

import argparse
import asyncio
import sys
from datetime import date
from pathlib import Path

# Evita UnicodeEncodeError en terminales cp1252 (Windows PowerShell)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── paths ──────────────────────────────────────────────────────────────────
_CRIZA = Path(__file__).parent.parent
if str(_CRIZA) not in sys.path:
    sys.path.insert(0, str(_CRIZA))

from dotenv import load_dotenv
load_dotenv(_CRIZA / ".env")

from utils.inta import harvest, get_pdf_url, SETS_BIOTECH
from knowledge_module.document_store.store import download_and_extract, pdf_exists
from km_tools.store import store_fuente_externa, batch_store_fuentes_externas

# ── constantes ─────────────────────────────────────────────────────────────
SECTOR_DEFAULT = "Biotecnología agrícola"

# INTA usa el mismo dc:type ("report"/"article") tanto para Informes Técnicos
# reales como para Folletos, y tanto para Artículos Científicos como para
# Artículos de Divulgación — el dc:type NO los distingue. La única forma
# confiable de distinguirlos es por la colección (setSpec) de origen.
# Mapeo construido auditando las 5 institutos de CICVyA (2026-06-30).
COLECCION_TIPO = {
    # Artículos científicos (uno por instituto)
    "col_20.500.12123_333":  "paper",
    "col_20.500.12123_396":  "paper",
    "col_20.500.12123_409":  "paper",
    "col_20.500.12123_462":  "paper",
    "col_20.500.12123_490":  "paper",
    # Tesis (uno por instituto)
    "col_20.500.12123_2078": "tesis",
    "col_20.500.12123_3588": "tesis",
    "col_20.500.12123_3589": "tesis",
    "col_20.500.12123_3590": "tesis",
    "col_20.500.12123_3591": "tesis",
    # Informes técnicos
    "col_20.500.12123_551":   "reporte",
    "col_20.500.12123_21744": "reporte",
    # Libros
    "col_20.500.12123_811":  "libro",
    "col_20.500.12123_1968": "libro",
    # Partes de libro
    "col_20.500.12123_3736": "parte_libro",
    # Presentaciones a Congresos (ponencias)
    "col_20.500.12123_933":  "ponencia",
    "col_20.500.12123_5334": "ponencia",
    "col_20.500.12123_6346": "ponencia",
    "col_20.500.12123_9835": "ponencia",
    # Artículos de divulgación
    "col_20.500.12123_6378": "divulgacion",
    "col_20.500.12123_6381": "divulgacion",
    # Folletos
    "col_20.500.12123_22363": "folleto",
}

# Fallback por dc:type crudo — solo se usa si la colección no está en
# COLECCION_TIPO (ej. institutos fuera de CICVyA que se cosechen a futuro).
TIPO_MAP = {
    "thesis":   "tesis",
    "bookpart": "parte_libro",
    "book":     "libro",
    "report":   "reporte",
    "article":  "paper",
    "other":    "otro",
}


def _tipo(inta_type: str, institutos: list[str] | None = None) -> str:
    """Clasifica el tipo real de un documento INTA. Prioridad: colección de
    origen (confiable) → dc:type crudo (ambiguo, ver comentario arriba)."""
    for setspec in institutos or []:
        if setspec in COLECCION_TIPO:
            return COLECCION_TIPO[setspec]
    t = (inta_type or "").lower()
    for k, v in TIPO_MAP.items():
        if k in t:
            return v
    return "paper"


async def harvest_y_persistir(
    set_id: str = "civcya",
    desde: str = None,
    con_pdf: bool = False,
    dry_run: bool = False,
    sector: str = SECTOR_DEFAULT,
) -> dict:
    """
    Cosecha los registros del set indicado y los persiste en el KM.

    Returns:
        dict con contadores: cosechados, creados, skipped, errores, pdfs_descargados
    """
    print(f"Cosechando set '{set_id}'{' (desde ' + desde + ')' if desde else ''}...")
    records = harvest(set_id, from_date=desde)
    print(f"  {len(records)} registros obtenidos del OAI-PMH")

    stats = {"cosechados": len(records), "creados": 0, "skipped": 0,
             "errores": 0, "pdfs_descargados": 0}

    # ── Dry run ────────────────────────────────────────────────────────────────
    if dry_run:
        for i, rec in enumerate(records, 1):
            titulo = rec["titulo"]
            año    = rec["año"] or str(date.today().year)
            if titulo:
                print(f"  DRY [{i}] {titulo[:60]} | año={año} | open={rec['open_access']}")
                stats["creados"] += 1
            else:
                stats["errores"] += 1
        return stats

    # ── Modo con PDF: procesar uno a uno (necesita PDF por registro) ───────────
    if con_pdf:
        for i, rec in enumerate(records, 1):
            titulo     = rec["titulo"]
            handle_url = rec["handle_url"]
            abstract   = rec["abstract"]
            año        = rec["año"] or str(date.today().year)

            if not titulo or not handle_url:
                stats["errores"] += 1
                continue

            texto_completo = None
            if rec["open_access"]:
                pdf_url = rec.get("pdf_url") or get_pdf_url(rec["handle_id"])
                if pdf_url:
                    try:
                        if not pdf_exists(pdf_url, "criza"):
                            _, texto_completo = download_and_extract(pdf_url, "criza")
                            stats["pdfs_descargados"] += 1
                            print(f"  PDF [{i}/{len(records)}] {titulo[:50]}...")
                    except Exception as e:
                        print(f"  WARN PDF {rec['handle_id']}: {e}")

            result = await store_fuente_externa(
                titulo=titulo,
                contenido=abstract or f"[Sin abstract] {titulo}",
                fuente_url=handle_url,
                sector=sector,
                fecha=año,
                tipo=_tipo(rec.get("tipo", ""), rec.get("institutos")),
                autores=rec["autores"],
                subjects=rec["subjects"],
                texto_completo=texto_completo,
                doi=rec.get("doi"),
            )
            if result["success"]:
                action = result["data"]["action"]
                stats[action if action in stats else "creados"] += 1
                if action == "created" and (i % 50 == 0 or i <= 5):
                    print(f"  [{i}/{len(records)}] creado: {titulo[:55]}")
            else:
                stats["errores"] += 1
                print(f"  ERROR [{i}]: {result['error']}")
        return stats

    # ── Modo batch: 2 queries para todo el set (default, sin PDF) ─────────────
    batch = []
    for rec in records:
        if not rec["titulo"] or not rec["handle_url"]:
            stats["errores"] += 1
            continue
        batch.append({
            "titulo":    rec["titulo"],
            "contenido": rec["abstract"] or f"[Sin abstract] {rec['titulo']}",
            "fuente_url": rec["handle_url"],
            "sector":    sector,
            "fecha":     rec["año"] or str(date.today().year),
            "tipo":      _tipo(rec.get("tipo", ""), rec.get("institutos")),
            "autores":   rec["autores"],
            "subjects":  rec["subjects"],
            "doi":       rec.get("doi"),
        })

    print(f"  Enviando batch de {len(batch)} registros al KM...")
    result = await batch_store_fuentes_externas(batch, tenant_id="criza")
    if result["success"]:
        d = result["data"]
        stats["creados"]  = d["created"]
        stats["skipped"]  = d["skipped"]
        stats["errores"] += d.get("errors", 0)
        print(f"  Creados: {d['created']} | Ya existian: {d['skipped']} | Errores: {d.get('errors',0)}")
    else:
        stats["errores"] += len(batch)
        print(f"  ERROR batch: {result['error']}")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Harvest INTA → KM")
    parser.add_argument("--set",    default="civcya",
                        help=f"Set a cosechar. Claves: {list(SETS_BIOTECH.keys())} o spec directo")
    parser.add_argument("--desde",  default=None, help="Fecha de inicio ISO (YYYY-MM-DD)")
    parser.add_argument("--con-pdf", action="store_true", help="Descargar PDFs open access")
    parser.add_argument("--dry-run", action="store_true", help="Simular sin escribir al KM")
    args = parser.parse_args()

    from knowledge_module.db import reset_engine
    reset_engine()  # necesario en standalone para evitar event loop collision con SQLAlchemy async
    stats = asyncio.run(harvest_y_persistir(
        set_id=args.set,
        desde=args.desde,
        con_pdf=args.con_pdf,
        dry_run=args.dry_run,
    ))

    print()
    print("=== Resultado ===")
    print(f"  Cosechados:        {stats['cosechados']}")
    print(f"  Creados en KM:     {stats['creados']}")
    print(f"  Ya existían:       {stats['skipped']}")
    print(f"  PDFs descargados:  {stats['pdfs_descargados']}")
    print(f"  Errores:           {stats['errores']}")


if __name__ == "__main__":
    # asyncpg requiere SelectorEventLoop en Windows (ProactorEventLoop no es compatible)
    import sys
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    main()
