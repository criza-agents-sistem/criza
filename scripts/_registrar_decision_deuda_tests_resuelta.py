import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision, listar_decisiones_vigentes


async def main():
    previas = await listar_decisiones_vigentes(componente="deuda_tests")
    supera_id = previas[0]["id"] if previas else None
    print(f"Superando decisión: {supera_id}")

    r = await registrar_decision(
        componente="deuda_tests",
        titulo="Deuda de tests de km_tools/tests resuelta — 6/28 verde pasó a 22/24 + 2 skips",
        decision=(
            "Reabierta la decisión del 13/08 (que la dejaba para sesión dedicada aparte) "
            "porque investigar el archivado del pipeline muerto (item 7 de hoy) reveló la "
            "causa concreta de la mayoría de las fallas — dejó de ser un misterio grande. "
            "Fix 1 (15 fallas): varios tests hacían patch(\"tools.store...\")/patch(\"tools."
            "search...\") con el nombre de módulo previo al rename a km_tools — corregido a "
            "km_tools.store/km_tools.search. Fix 2 (2 fallas): 2 tests de integración "
            "reusaban una URL fija sin limpiarla, así que la segunda corrida contra el Neon "
            "real siempre fallaba (dedup funcionaba bien, el test no era idempotente) — "
            "ahora generan un uuid4() por corrida. Fix 3 (4 tests con \"Event loop is closed\" "
            "intermitente): faltaba reset_engine() antes de la primera query async — mismo "
            "patrón ya usado en otros tests de integración del repo (armador, market_agent). "
            "Fix 4 (2 tests): LocalEmbedder depende de sentence-transformers, que "
            "knowledge_module declara como extra OPCIONAL ([local-embeddings]), no dependencia "
            "base — CRIZA usa bgem3 en producción. Esos 2 tests ahora hacen pytest.importorskip "
            "en vez de fallar en rojo por un extra que nunca se pidió instalar."
        ),
        motivo=(
            "km_tools/tests/ pasó de 6/28 verde a 22/24 passed + 2 skipped (justificados). "
            "utils/tests (que colgaba) queda fuera de esta resolución, sin investigar hoy."
        ),
        alternativas_consideradas=[
            "Instalar sentence-transformers para que los últimos 2 tests pasen en vez de "
            "saltear — descartado: es un extra opcional pesado (arrastra torch) que la "
            "instancia real no usa (EMBEDDING_PROVIDER=bgem3); requirements.txt de hoy ya "
            "excluyó torch por el mismo motivo.",
        ],
        quien="Sebas + Claude",
        supera_id=supera_id,
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
