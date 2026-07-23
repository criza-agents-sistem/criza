"""
Migración INTA: documento → ficha/corpus_cientifico

Lee los registros INTA cosechados en la tabla `documento` (agente='harvest')
y los inserta como fichas `fuente` en el área `corpus_cientifico` del motor del KM,
con embeddings BGE-m3 para búsqueda semántica.

No toca los registros en `documento` — los deja intactos.
Idempotente: si ya existe una ficha con el mismo identifier, la saltea.

Uso:
    python criza/ingest/migrate_inta_to_corpus.py            # migra todos
    python criza/ingest/migrate_inta_to_corpus.py --dry-run  # muestra qué haría sin escribir
    python criza/ingest/migrate_inta_to_corpus.py --limit 50 # prueba rápida
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

_CRIZA = Path(__file__).parent.parent

# Transicional: mientras CRIZA siga en el árbol de EMPRESAS-IA, la conexión al KM vive en
# knowledge_module/.env — cuando CRIZA salga del árbol tendrá su propio .env.
from dotenv import load_dotenv
load_dotenv(_CRIZA.parent / "knowledge_module" / ".env")

from knowledge_module.db import get_session_factory, reset_engine
from knowledge_module.motor import api as motor_api
from knowledge_module.motor.loader import load_plantilla
from sqlalchemy import text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logger = logging.getLogger(__name__)

# Config de instancia (Capa 2) — vive en criza/, no en knowledge_module/ (Capa Estructural es
# solo el loader genérico). Movido 2026-07-06, ver AUDITORIA_CUMPLIMIENTO_2026-07-05.md.
_PLANTILLA = _CRIZA / "config" / "plantillas" / "corpus_cientifico.yaml"
_TENANT    = "criza"


async def _cargar_identifiers_existentes() -> set[str]:
    """Carga en memoria todos los identifiers ya en corpus_cientifico (dedup exacto)."""
    async with get_session_factory()() as s:
        r = await s.execute(text("""
            SELECT f.props->>'identifier' AS ident
            FROM ficha f
            JOIN tipo_ficha tf ON tf.id = f.tipo_ficha_id
            JOIN area a ON a.id = tf.area_id
            WHERE a.nombre = 'corpus_cientifico'
              AND a.tenant_id = :t
              AND tf.nombre = 'fuente'
              AND f.props->>'identifier' IS NOT NULL
        """), {"t": _TENANT})
        return {row.ident for row in r.fetchall()}


async def _leer_inta_docs(limit: int | None = None) -> list[dict]:
    """Lee todos los registros INTA de la tabla documento."""
    lim_clause = f"LIMIT {limit}" if limit else ""
    async with get_session_factory()() as s:
        r = await s.execute(text(f"""
            SELECT
                id::text,
                titulo,
                contenido,
                texto_completo,
                autores,
                subjects,
                fuente_url,
                doi,
                fecha,
                tipo
            FROM documento
            WHERE tenant_id = :t
              AND agente = 'harvest'
              AND fuente_url IS NOT NULL
            ORDER BY fecha DESC NULLS LAST
            {lim_clause}
        """), {"t": _TENANT})
        return [dict(row._mapping) for row in r.fetchall()]


def _doc_a_campos(doc: dict) -> dict:
    """Convierte un registro de `documento` a los campos del tipo_ficha `fuente`."""
    titulo   = doc["titulo"] or ""
    abstract = doc["contenido"] or ""

    autores = []
    try:
        autores = json.loads(doc["autores"]) if doc["autores"] else []
    except Exception:
        pass

    subjects = []
    try:
        subjects = json.loads(doc["subjects"]) if doc["subjects"] else []
    except Exception:
        pass

    anio = str(doc["fecha"].year) if doc["fecha"] else ""

    # identifier: preferimos DOI si existe, sino la handle URL
    identifier = doc["doi"] or doc["fuente_url"] or ""

    # titulo_abstract: campo vectorizado — incluimos subjects (términos AGROVOC que INTA usa)
    partes = [titulo, abstract]
    if subjects:
        partes.append(" ".join(subjects))
    titulo_abstract = ". ".join(p for p in partes if p).strip()

    return {
        "titulo":          titulo,
        "abstract":        abstract,
        "autores":         autores,
        "anio":            anio,
        "identifier":      identifier,
        "url":             doc["fuente_url"] or "",
        "repositorio":     "INTA",
        "idioma":          "",
        "tipo_recurso":    doc["tipo"] or "paper",
        "sets":            [],
        "titulo_abstract": titulo_abstract,
        "texto_completo":  doc["texto_completo"] or None,
    }


async def migrar(dry_run: bool = False, limit: int | None = None) -> dict:
    reset_engine()

    logger.info("Cargando plantilla corpus_cientifico...")
    await load_plantilla(str(_PLANTILLA))

    logger.info("Cargando identifiers existentes en corpus_cientifico...")
    existentes = await _cargar_identifiers_existentes()
    logger.info("  %d fichas ya en corpus_cientifico", len(existentes))

    logger.info("Leyendo registros INTA de tabla documento...")
    docs = await _leer_inta_docs(limit=limit)
    logger.info("  %d registros INTA encontrados", len(docs))

    stats = {"total": len(docs), "ingeridos": 0, "deduplicados": 0, "sin_identifier": 0, "errores": 0}

    for i, doc in enumerate(docs, 1):
        campos = _doc_a_campos(doc)

        if not campos["identifier"]:
            logger.warning("[%d/%d] Sin identifier — saltear: %s", i, len(docs), campos["titulo"][:60])
            stats["sin_identifier"] += 1
            continue

        if campos["identifier"] in existentes:
            stats["deduplicados"] += 1
            continue

        if dry_run:
            logger.info(
                "[%d/%d] DRY-RUN — %s | %s | %s",
                i, len(docs),
                campos["tipo_recurso"],
                campos["anio"],
                campos["titulo"][:60],
            )
            stats["ingeridos"] += 1
            continue

        try:
            result = await motor_api.guardar_ficha(
                area="corpus_cientifico",
                tipo="fuente",
                campos=campos,
                tenant=_TENANT,
            )
            if result["success"]:
                existentes.add(campos["identifier"])
                stats["ingeridos"] += 1
                if i % 50 == 0 or i <= 5:
                    logger.info(
                        "[%d/%d] %s — %s",
                        i, len(docs), result["action"], campos["titulo"][:60]
                    )
            else:
                logger.error("[%d/%d] ERROR: %s | %s", i, len(docs), result.get("error"), campos["titulo"][:60])
                stats["errores"] += 1
        except Exception as exc:
            logger.error("[%d/%d] EXCEPCION: %s | %s", i, len(docs), exc, campos["titulo"][:60])
            stats["errores"] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(description="Migrar INTA de documento → ficha/corpus_cientifico")
    parser.add_argument("--dry-run", action="store_true", help="Mostrar qué haría sin escribir")
    parser.add_argument("--limit",   type=int, default=None, help="Procesar solo N documentos")
    args = parser.parse_args()

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    stats = asyncio.run(migrar(dry_run=args.dry_run, limit=args.limit))

    print()
    print("=== Resultado ===")
    print(f"  Total registros INTA: {stats['total']}")
    print(f"  Ingeridos:            {stats['ingeridos']}")
    print(f"  Ya existían:          {stats['deduplicados']}")
    print(f"  Sin identifier:       {stats['sin_identifier']}")
    print(f"  Errores:              {stats['errores']}")
    if args.dry_run:
        print()
        print("  [DRY-RUN — no se escribió nada]")


if __name__ == "__main__":
    main()
