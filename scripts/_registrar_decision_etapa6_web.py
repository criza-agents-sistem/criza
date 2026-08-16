import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="web",
        titulo="Etapa 6 del plan — scaffold real de la app web (api/ + web/)",
        decision=(
            "Construido api/ (FastAPI, 3 endpoints de solo lectura: GET /casos, GET /casos/{id}, "
            "GET /documentos/{id} — reusa knowledge_module/utils/casos.py directo, cero SQL "
            "duplicado en TypeScript) + web/ (Next.js 15, App Router, TypeScript, Tailwind — "
            "create-next-app real). 3 páginas: / (lista de casos), /casos/[id] (frentes con "
            "estado de documentos, pendientes, artefactos externos), /documentos/[id] (contenido "
            "completo, renderizado como markdown real con react-markdown+remark-gfm+"
            "@tailwindcss/typography, no texto plano). api/ lee de producción (estrictamente "
            "de solo lectura, sin el riesgo de escritura que forzó staging en la Etapa 4). "
            "7 unit + 1 integration test (Python), 361/361 activos en verde, auditor sin "
            "ALTO/MEDIO nuevos. Verificado en el navegador de verdad (Claude Browser, no solo "
            "curl): lista de casos con datos reales, detalle de Helios con frentes/pendientes "
            "reales, npm run build sin errores. Encontrado en el camino: el TestClient síncrono "
            "de FastAPI rompe con 'Event loop is closed' al hacer 2+ requests en el mismo test "
            "contra el engine async de knowledge_module — resuelto con httpx.AsyncClient."
        ),
        motivo=(
            "Etapa 6 del plan aprobado el 16/08 — el modelo de datos y las páginas ya estaban "
            "diseñados (config/plantillas/casos.yaml, docs/PROPUESTA_DESTINO.md §7), esta etapa "
            "era el código en sí. Fork de arquitectura real (cómo Next.js accede a los datos) "
            "resuelto con Sebas antes de escribir código, no asumido."
        ),
        alternativas_consideradas=[
            "Next.js conectado directo a Postgres (cliente TS: postgres.js/drizzle) — descartado "
            "por decisión explícita de Sebas: duplicaría en TypeScript la lógica de queries/"
            "tenant_id scoping que ya existe en Python, riesgo real de que diverjan.",
            "Mostrar el contenido de documento_caso como texto plano (whitespace-pre-wrap) — "
            "descartado tras verificar en navegador que el markdown quedaba ilegible (## y ** "
            "literales) para el caso de uso central de la etapa ('ver los documentos que se "
            "generen').",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
