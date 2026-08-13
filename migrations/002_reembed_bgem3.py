"""
Migración SEB-121 — Re-embedear oportunidades y aprendizajes de MiniLM (384 dims) a BGE-m3 (1024 dims).

Requiere:
- EMBEDDING_PROVIDER=bgem3 en .env (ya configurado)
- BGEM3_URL apuntando al servicio Modal live

Uso:
    python migrations/002_reembed_bgem3.py [--dry-run]

--dry-run: solo imprime cuántas filas se migrarían, no escribe nada.
"""

import argparse
import asyncio
import os
import sys

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from sqlalchemy import text

# Asegurar que el módulo raíz del KM está en el path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

from knowledge_module.db import AsyncSession, async_sessionmaker, create_async_engine
from knowledge_module.embeddings import get_embedder

engine = create_async_engine(os.getenv("DATABASE_URL"))
Session = async_sessionmaker(engine)


async def reembed_table(session, table: str, text_col: str, dry_run: bool) -> int:
    """Re-embea todas las filas de una tabla que tienen embedding de dim != 1024."""
    rows = await session.execute(
        text(
            f"SELECT id, {text_col} FROM {table} "
            f"WHERE embedding IS NULL OR vector_dims(embedding) != 1024"
        )
    )
    rows = rows.fetchall()

    if dry_run:
        print(f"  {table}: {len(rows)} filas para migrar (dry-run, sin cambios)")
        return len(rows)

    embedder = get_embedder()
    texts = [r[1] for r in rows]
    ids   = [r[0] for r in rows]

    if not texts:
        print(f"  {table}: 0 filas para migrar")
        return 0

    print(f"  {table}: generando {len(texts)} embeddings BGE-m3...")
    # Batch de hasta 64 para no saturar el servicio
    all_vecs = []
    batch_size = 64
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        vecs = embedder.embed_batch(batch)
        all_vecs.extend(vecs)
        print(f"    {min(i + batch_size, len(texts))}/{len(texts)} listos")

    # Actualizar en Neon
    for row_id, vec in zip(ids, all_vecs):
        await session.execute(
            text(f"UPDATE {table} SET embedding = :v WHERE id = :id"),
            {"v": str(vec), "id": str(row_id)},
        )

    await session.commit()
    print(f"  {table}: {len(rows)} filas migradas ✅")
    return len(rows)


async def main(dry_run: bool):
    provider = os.getenv("EMBEDDING_PROVIDER", "local")
    if provider != "bgem3":
        print(f"ERROR: EMBEDDING_PROVIDER={provider}. Debe ser 'bgem3' para migrar.")
        sys.exit(1)

    print(f"{'[DRY RUN] ' if dry_run else ''}Migrando embeddings MiniLM → BGE-m3...\n")

    async with Session() as session:
        total = 0
        total += await reembed_table(session, "oportunidad", "idea",      dry_run)
        total += await reembed_table(session, "aprendizaje", "contenido", dry_run)

    print(f"\nTotal: {total} filas {'para migrar' if dry_run else 'migradas'} ✅")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.dry_run))
