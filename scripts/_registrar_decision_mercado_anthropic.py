import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="ai_client",
        titulo="Mercado es Anthropic-only — excepción permanente, no pendiente de migrar",
        decision=(
            "Definido con Sebas: Mercado NO se migra al traductor de proveedores "
            "(utils/ai_client.py) — queda 100% Anthropic directo, de forma permanente, no "
            "'hasta que haga falta migrarlo'. Depende de la tool nativa `web_search_20250305` "
            "(búsqueda del lado del servidor de Anthropic), que no tiene equivalente en el "
            "formato de función que el traductor entiende (LiteLLM/formato OpenAI). Comentario "
            "agregado en market_agent/market_agent.py explicando la excepción para quien lea "
            "el código y se pregunte por qué este agente no sigue el mismo patrón que los otros "
            "4."
        ),
        motivo=(
            "Evita dejarlo como pendiente eterno sin resolución clara. La tool nativa es "
            "central para el Cruce 3 de Mercado (descubrir competidores/regulación reales) — "
            "cambiar de proveedor implicaría perder esa capacidad o reconstruirla distinto por "
            "proveedor, sin ningún driver real hoy que lo justifique."
        ),
        alternativas_consideradas=[
            "Dejarlo como 'pendiente de migrar cuando haga falta' — descartado por Sebas, "
            "prefiere una decisión cerrada a un TODO abierto sin fecha.",
        ],
        quien="Sebas",
        supera_id="f6e6a4bc-72be-4136-af78-36aa75581d8a",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
