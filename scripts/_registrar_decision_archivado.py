import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="infra",
        titulo="Archivado el subsistema muerto del pipeline scout/divergente/convergente",
        decision=(
            "Movidos a _archivo_temporal/: server.py (MCP server legacy), ingest_corrida.py, "
            "ingest_historico.py, km_tools/retrieve.py. Removidas de km_tools/store.py y "
            "search.py las funciones store_corrida/store_opportunity/store_document/"
            "store_learning/_link_corrida/search_knowledge — sin consumidor real desde que "
            "divergent_agent/ se borró el 2026-07-02. km_models.py quedó solo con la clase "
            "Documento (Corrida/Oportunidad/Aprendizaje/CorridaOportunidad/CorridaDocumento "
            "archivadas). Las tablas correspondientes en Neon NO se tocaron — solo el código "
            "que las escribía/exponía. km_tools/tests/test_tools.py perdió los 4 tests de "
            "funciones archivadas, tests/test_ingest.py se archivó completo."
        ),
        motivo=(
            "Encontrado al investigar por qué server.py estaba roto (item requirements.txt): "
            "sus 6 de 7 tools exponían un pipeline sin ningún consumidor vivo. Rastreado hasta "
            "confirmar que ingest_corrida.py e ingest_historico.py también dependían "
            "exclusivamente de ese mismo pipeline muerto — todo se originaba en el mismo punto: "
            "divergent_agent/ borrado el 02/07 sin limpiar lo que lo alimentaba/consumía."
        ),
        alternativas_consideradas=[
            "Solo instalar mcp y dejar server.py funcional — descartada por Sebas: quedaría "
            "exponiendo un pipeline que nada más usa.",
            "No tocar nada, documentar como hallazgo para otra sesión — descartada por Sebas, "
            "eligió 'archivar y confirmar borrado' explícitamente.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
