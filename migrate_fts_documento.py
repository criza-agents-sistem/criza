"""
Agrega índice GIN de full-text search sobre tabla documento.

Crea un índice sobre to_tsvector('spanish', titulo || ' ' || contenido)
para que buscar_fuentes_externas() sea rápido sobre miles de registros.

Idempotente — CREATE INDEX IF NOT EXISTS.
"""
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")
import asyncpg

_SQL = [
    # Columna generada con tsvector (más eficiente que re-computar en cada query)
    """
    ALTER TABLE documento
    ADD COLUMN IF NOT EXISTS fts_vector tsvector
    GENERATED ALWAYS AS (
        to_tsvector('simple',
            coalesce(titulo, '') || ' ' ||
            coalesce(contenido, '') || ' ' ||
            coalesce(subjects, '')
        )
    ) STORED;
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_documento_fts
    ON documento USING GIN (fts_vector);
    """,
]

async def run():
    url = os.getenv("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(url)
    try:
        for stmt in _SQL:
            s = stmt.strip()
            short = s.split("\n")[0][:80]
            await conn.execute(s)
            print(f"  OK  {short}")
        print("\nÍndice FTS creado.")
    finally:
        await conn.close()

asyncio.run(run())
