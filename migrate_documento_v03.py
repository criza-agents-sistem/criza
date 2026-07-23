"""
Migración documento v0.3

Agrega las columnas nuevas de Documento introducidas en la sesión 2026-06-27:
  - texto_completo TEXT  (PDF extraído de fuente externa)
  - autores        TEXT  (JSON array serializado)
  - subjects       TEXT  (JSON array serializado)
  - fuente_url     VARCHAR con índice UNIQUE parcial (NOT NULL rows)
  - doi            VARCHAR

Idempotente — usa IF NOT EXISTS / IF NOT EXISTS en índices.
Safe to re-run.
"""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / "knowledge_module" / ".env")

import asyncpg

_SQL = [
    "ALTER TABLE documento ADD COLUMN IF NOT EXISTS texto_completo TEXT;",
    "ALTER TABLE documento ADD COLUMN IF NOT EXISTS autores TEXT;",
    "ALTER TABLE documento ADD COLUMN IF NOT EXISTS subjects TEXT;",
    "ALTER TABLE documento ADD COLUMN IF NOT EXISTS fuente_url VARCHAR;",
    "ALTER TABLE documento ADD COLUMN IF NOT EXISTS doi VARCHAR;",
    # Índice UNIQUE parcial: excluye NULLs para que docs internos (sin fuente_url) no colisionen
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_documento_fuente_url
    ON documento (fuente_url)
    WHERE fuente_url IS NOT NULL;
    """,
    # Expande constraints para aceptar valores de fuentes externas (harvest/ingest)
    "ALTER TABLE documento DROP CONSTRAINT IF EXISTS documento_agente_check;",
    """ALTER TABLE documento ADD CONSTRAINT documento_agente_check
       CHECK (agente IN ('divergente','convergente','harvest','ingest'));""",
    "ALTER TABLE documento DROP CONSTRAINT IF EXISTS documento_tipo_check;",
    """ALTER TABLE documento ADD CONSTRAINT documento_tipo_check
       CHECK (tipo IN ('analisis','informe','borrador','paper','reporte','norma','patente','otro'));""",
]


async def run():
    raw_url = os.getenv("DATABASE_URL", "")
    # asyncpg usa postgresql:// — strip el +asyncpg dialect tag
    url = raw_url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgres+asyncpg://", "postgresql://"
    )

    print(f"Conectando a DB...")
    conn = await asyncpg.connect(url)
    try:
        for stmt in _SQL:
            stmt = stmt.strip()
            short = stmt.split("\n")[0][:80]
            await conn.execute(stmt)
            print(f"  OK  {short}")
        print("\nMigración completada.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run())
