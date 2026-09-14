import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="ai_client",
        titulo="Etapa 22 (cont.) — default de modelo pasa de Sonnet 4.6 a Sonnet 5 en todos los agentes",
        decision=(
            "DEFAULT_MODEL cambia de 'claude-sonnet-4-6' a 'claude-sonnet-5' en los 11 agentes que "
            "lo leen de .env con ese fallback (armador, conductor, evidence_generalista, "
            "market_agent, microbiologo_agent, investigacion_amplia, agronomo_agent, "
            "biotecnologo_agent, financiero_agent, ingeniero_ambiental_agent, "
            "scientific_agent/specialist_proteins.py). Se actualizó también: el override real en "
            "market_agent/.env (el único agente con un .env real fuera de .env.example que fijaba "
            "el modelo explícito), los 13 valores en los .env.example de cada agente (documentación "
            "del default), y utils/ai_client.py::MODELOS_DISPONIBLES (la lista que alimenta el "
            "selector de modelo por sesión de chat en la web, Etapa 15) para que Sonnet 5 aparezca "
            "como default y Sonnet 4.6 quede como opción disponible, no eliminada. orquestador/"
            ".env.example (ORQUESTADOR_MODEL) y scientific_agent/.env.example (SCOUT_MODEL) también "
            "actualizados por consistencia de documentación aunque no se encontró ningún os.getenv "
            "que los lea en el código actual -- quedan como var. no usada, no se investigó más a "
            "fondo por estar fuera del alcance de este cambio."
        ),
        motivo=(
            "Sebas pidió el cambio tras ver el dashboard real de uso de Anthropic (Console, "
            "2026-09-14): con el volumen real del período (18.5M tokens in / 411K out en 30 días, "
            "100% Sonnet 4.6), Sonnet 5 es la generación siguiente al mismo precio de tier "
            "'Sonnet' pero ~33% más barato por token ($2/$10 por MTok vs $3/$15 de Sonnet 4.6) -- "
            "bajaría el costo del período de ~USD 61.70 a ~USD 41.14 sin cambiar de tier. No se "
            "confirmó una mejora de calidad medida en las tareas específicas de CRIZA (búsqueda "
            "exhaustiva agéntica) -- eso queda a-confirmar, se ofreció una comparación real A/B y "
            "Sebas priorizó aplicar el cambio directo por el ahorro de costo ya confirmado."
        ),
        alternativas_consideradas=[
            "Mantener Sonnet 4.6 -- descartada: mismo tier de capacidad, pero ~33% más caro por "
            "token que la generación siguiente al mismo precio de lista.",
            "Migrar solo a Opus 5 -- descartada: Opus es un tier más caro ($5/$25 por MTok), no es "
            "el pedido (Sebas pidió específicamente 'más barato y mejor', que es Sonnet 5, no "
            "Opus 5).",
            "Comparación A/B real (correr el mismo caso con los dos modelos) antes de migrar -- "
            "ofrecida explícitamente, Sebas prefirió aplicar el cambio ya con el dato de costo "
            "confirmado en vez de esperar una corrida adicional.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
