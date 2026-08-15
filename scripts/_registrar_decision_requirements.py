import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="infra",
        titulo="requirements.txt en la raíz de criza/ (no existía)",
        decision=(
            "Armado a partir de un escaneo real de imports en todo el código: anthropic, "
            "litellm, python-dotenv, requests, pyyaml, pydantic, sqlalchemy, asyncpg, pgvector, "
            "modal (solo deploy), pytest, pytest-asyncio. Excluidos a propósito: torch/esm/"
            "fastapi/uvicorn (solo en scientific_agent/pod_server.py, RunPod ya reemplazado) y "
            "FlagEmbedding (corre dentro del contenedor de Modal). Hallazgo de paso sin "
            "resolver: server.py (KM legacy MCP server) importa mcp, no instalado — roto tal "
            "cual hoy, comentado en el archivo con nota."
        ),
        motivo=(
            "Las dependencias se instalaban a mano en el entorno global sin manifiesto que las "
            "fijara — riesgo real de que un clon nuevo del repo no supiera qué instalar, más "
            "consecuente ahora que litellm es dependencia real de 3 agentes en producción."
        ),
        alternativas_consideradas=[
            "pip freeze completo del entorno — descartado: el entorno es global (sin venv), "
            "captura paquetes de otros proyectos ajenos a CRIZA.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
