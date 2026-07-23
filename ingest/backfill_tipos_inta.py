"""
backfill_tipos_inta.py — Recalcula documento.tipo para los docs INTA ya cosechados.

Motivo: harvest_inta.py clasificaba todo como "paper"/"reporte" porque dc:type
de INTA no distingue tesis/ponencias/libros/divulgación/folletos de artículos
científicos reales — la única señal confiable es la colección de origen
(setSpec), que antes tampoco se leía bien (bug en inta.py: ver fix 2026-06-30).

No vuelve a descargar nada. Solo re-cosecha metadata OAI-PMH (liviano) y
actualiza la columna tipo por fuente_url cuando difiere de lo ya guardado.

Uso:
    python criza/ingest/backfill_tipos_inta.py            # aplica
    python criza/ingest/backfill_tipos_inta.py --dry-run  # solo muestra
"""

import argparse
import asyncio
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_CRIZA_DIR = Path(__file__).parent.parent
if str(_CRIZA_DIR) not in sys.path:
    sys.path.insert(0, str(_CRIZA_DIR))

# Transicional: mientras CRIZA siga en el árbol de EMPRESAS-IA, la conexión al KM vive en
# knowledge_module/.env — cuando CRIZA salga del árbol tendrá su propio .env.
from dotenv import load_dotenv
load_dotenv(_CRIZA_DIR.parent / "knowledge_module" / ".env")

from sqlalchemy import text as sa_text

from utils.inta import harvest
from ingest.harvest_inta import _tipo
from knowledge_module.db import get_session_factory


async def run(set_id: str = "civcya", dry_run: bool = False) -> dict:
    print(f"Re-cosechando metadata de '{set_id}'...")
    records = harvest(set_id)
    print(f"  {len(records)} registros en OAI-PMH")

    cambios: dict[str, int] = {}
    updates = []
    for rec in records:
        handle_url = rec.get("handle_url")
        if not handle_url:
            continue
        nuevo_tipo = _tipo(rec.get("tipo", ""), rec.get("institutos"))
        updates.append((handle_url, nuevo_tipo))

    print(f"\nAplicando contra KM ({'dry-run' if dry_run else 'UPDATE real'})...")
    actualizados = 0
    sin_cambio = 0
    no_encontrados = 0

    async with get_session_factory()() as s:
        for handle_url, nuevo_tipo in updates:
            r = await s.execute(
                sa_text("SELECT tipo FROM documento WHERE fuente_url = :u"),
                {"u": handle_url},
            )
            row = r.fetchone()
            if row is None:
                no_encontrados += 1
                continue
            if row.tipo == nuevo_tipo:
                sin_cambio += 1
                continue

            cambios[f"{row.tipo} → {nuevo_tipo}"] = cambios.get(f"{row.tipo} → {nuevo_tipo}", 0) + 1
            if not dry_run:
                await s.execute(
                    sa_text("UPDATE documento SET tipo = :t WHERE fuente_url = :u"),
                    {"t": nuevo_tipo, "u": handle_url},
                )
            actualizados += 1
        if not dry_run:
            await s.commit()

    print()
    print("=== Cambios por tipo ===")
    for k, v in sorted(cambios.items(), key=lambda x: -x[1]):
        print(f"  {k:<30} {v}")

    print()
    print("=== Resultado ===")
    print(f"  Actualizados:    {actualizados}")
    print(f"  Sin cambio:      {sin_cambio}")
    print(f"  No encontrados:  {no_encontrados}")

    return {"actualizados": actualizados, "sin_cambio": sin_cambio, "no_encontrados": no_encontrados}


def main():
    parser = argparse.ArgumentParser(description="Backfill documento.tipo para corpus INTA")
    parser.add_argument("--set", default="civcya")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    from knowledge_module.db import reset_engine
    reset_engine()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(run(set_id=args.set, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
