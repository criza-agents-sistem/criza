"""
Backfill: completa `texto_completo` en las fichas INTA de corpus_cientifico que ya existen.

Gap encontrado 2026-07-02: `migrate_inta_to_corpus.py::_doc_a_campos` nunca copiaba
`texto_completo` de `documento` a la ficha — 1.643 fichas INTA en corpus_cientifico quedaron
con el campo vacío pese a que ~984 de esos 1.643 documentos originales sí lo tenían en la
tabla legacy `documento`. Ese bug ya se corrigió en `migrate_inta_to_corpus.py` (para
migraciones futuras), pero las fichas ya insertadas necesitan este backfill porque
`migrar()` saltea (no reprocesa) cualquier identifier que ya exista en corpus_cientifico.

Usa `motor_api.actualizar_props` (merge shallow, no re-vectoriza) — no toca el embedding.
Idempotente: solo toca fichas con texto_completo IS NULL o vacío.

Uso:
    python criza/ingest/backfill_inta_texto_completo.py            # aplica
    python criza/ingest/backfill_inta_texto_completo.py --dry-run  # solo cuenta
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
_KM   = _ROOT / "knowledge_module"

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_KM) not in sys.path:
    sys.path.insert(0, str(_KM))

from dotenv import load_dotenv
load_dotenv(_KM / ".env")

from db import get_session_factory, reset_engine
from motor import api as motor_api
from sqlalchemy import text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logger = logging.getLogger(__name__)
_TENANT = "criza"


async def _fichas_inta_sin_texto() -> list[dict]:
    """Fichas INTA en corpus_cientifico con texto_completo vacío, con su identifier."""
    async with get_session_factory()() as s:
        r = await s.execute(text("""
            SELECT f.id::text AS id, f.props->>'identifier' AS identifier
            FROM ficha f
            JOIN tipo_ficha tf ON tf.id = f.tipo_ficha_id
            JOIN area a ON a.id = tf.area_id
            WHERE a.nombre = 'corpus_cientifico' AND a.tenant_id = :t
              AND tf.nombre = 'fuente' AND f.props->>'repositorio' = 'INTA'
              AND (f.props->>'texto_completo' IS NULL OR f.props->>'texto_completo' = '')
              AND f.props->>'identifier' IS NOT NULL
        """), {"t": _TENANT})
        return [dict(row._mapping) for row in r.fetchall()]


async def _mapa_texto_por_identifier() -> dict[str, str]:
    """documento.doi o documento.fuente_url -> texto_completo, para los que lo tienen."""
    async with get_session_factory()() as s:
        r = await s.execute(text("""
            SELECT doi, fuente_url, texto_completo
            FROM documento
            WHERE tenant_id = :t AND agente = 'harvest'
              AND texto_completo IS NOT NULL AND texto_completo != ''
        """), {"t": _TENANT})
        mapa: dict[str, str] = {}
        for row in r.fetchall():
            texto = row.texto_completo
            # mismo orden de preferencia que _doc_a_campos: doi primero, sino fuente_url
            if row.doi:
                mapa[row.doi] = texto
            elif row.fuente_url:
                mapa[row.fuente_url] = texto
        return mapa


async def backfill(dry_run: bool = False) -> dict:
    reset_engine()

    logger.info("Buscando fichas INTA sin texto_completo...")
    fichas = await _fichas_inta_sin_texto()
    logger.info("  %d fichas INTA sin texto_completo", len(fichas))

    logger.info("Cargando texto_completo disponible en tabla documento...")
    mapa = await _mapa_texto_por_identifier()
    logger.info("  %d documentos con texto_completo disponible", len(mapa))

    stats = {"total": len(fichas), "actualizadas": 0, "sin_match": 0, "errores": 0}

    for i, ficha in enumerate(fichas, 1):
        texto = mapa.get(ficha["identifier"])
        if not texto:
            stats["sin_match"] += 1
            continue

        if dry_run:
            stats["actualizadas"] += 1
            continue

        try:
            result = await motor_api.actualizar_props(
                ficha_id=ficha["id"],
                cambios={"texto_completo": texto},
                tenant=_TENANT,
            )
            if result["success"]:
                stats["actualizadas"] += 1
                if i % 100 == 0 or i <= 5:
                    logger.info("[%d/%d] actualizada — %s", i, len(fichas), ficha["identifier"][:70])
            else:
                logger.error("[%d/%d] ERROR: %s", i, len(fichas), result.get("error"))
                stats["errores"] += 1
        except Exception as exc:
            logger.error("[%d/%d] EXCEPCION: %s", i, len(fichas), exc)
            stats["errores"] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(description="Backfill texto_completo en fichas INTA de corpus_cientifico")
    parser.add_argument("--dry-run", action="store_true", help="Solo contar, no escribir")
    args = parser.parse_args()

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    stats = asyncio.run(backfill(dry_run=args.dry_run))

    print()
    print("=== Resultado ===")
    print(f"  Fichas INTA sin texto_completo (antes): {stats['total']}")
    print(f"  Actualizadas:                            {stats['actualizadas']}")
    print(f"  Sin match en documento:                  {stats['sin_match']}")
    print(f"  Errores:                                 {stats['errores']}")
    if args.dry_run:
        print()
        print("  [DRY-RUN — no se escribió nada]")


if __name__ == "__main__":
    main()
