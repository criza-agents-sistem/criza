import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="orquestador",
        titulo="Etapa 3 del plan de construcción del nuevo sistema — protocolo de lectura del Conductor (Caso B)",
        decision=(
            "Cerrado el diseño del 'Caso B' pendiente de PROPUESTA_DESTINO.md §11 — qué consulta "
            "el Conductor, en qué orden, y cómo arma contexto antes de responder cuando 'se "
            "despierta' sobre un caso. Documento nuevo: docs/PROTOCOLO_LECTURA_CONDUCTOR.md. "
            "7 pasos en orden: (1) identidad del caso, (2) qué falta vía inspeccionar_caso "
            "(Etapa 2), (3) sanity check de que lo 'completo' tiene contenido real (no solo "
            "status=completo), (4) costo gastado + estimado restante vía estimar_costo (Etapa 2), "
            "(5) lecciones relevantes (aprendizaje.leer_lecciones_caso/proceso), (6) decisiones "
            "de sistema vigentes, (7) inconsistencias entre agentes que solo el Conductor puede "
            "ver (PROPUESTA_CONDUCTOR.md §3.1). Define también el shape del 'briefing' "
            "estructurado que el Conductor arma antes de generar su respuesta conversacional. "
            "Verificado corriendo los 7 pasos de verdad contra un caso real del KM (no solo "
            "diseñado en el papel) — la corrida real encontró y documentó un matiz genuino: "
            "inspeccionar_caso está acotado al flow que se le pasa, un especialista invocado "
            "directo (como el Microbiólogo hoy) no aparece ahí aunque su prop exista, el "
            "Conductor necesita el paso 1 (identidad completa) para no asumir que "
            "inspeccionar_caso de un solo flow es la vista completa. Declara explícitamente qué "
            "NO resuelve (decisiones de negocio dentro de un caso siguen sin lugar dedicado — gap "
            "conocido, no inventado). PROPUESTA_DESTINO.md §11 actualizado marcando Caso B "
            "resuelto."
        ),
        motivo=(
            "PROPUESTA_DESTINO.md §11 dejó esto como requisito explícito 'para cuando se diseñe "
            "el Conductor (no antes)' — la Etapa 5 (construir el Conductor) no puede empezar sin "
            "esto resuelto primero, o se construye adivinando su propio protocolo de lectura, "
            "exactamente el riesgo que Sebas nombró al pedir esta etapa ('el Conductor es clave, "
            "no opcional')."
        ),
        alternativas_consideradas=[
            "Diseñar el protocolo dentro de PROPUESTA_CONDUCTOR.md (EMPRESAS-IA) — descartado: "
            "ese documento es de plataforma/pre-capa, y el contenido concreto de este protocolo "
            "(nombres de props, flows, funciones reales) es específico de CRIZA — va en "
            "criza/docs/, mismo criterio que PROPUESTA_DESTINO.md.",
            "Resolver esto dentro de la implementación del Conductor (Etapa 5), sin documento "
            "separado — descartado: mezclaría diseño de protocolo con código de un agente "
            "conversacional nuevo, y el plan ya identificó esto como prerrequisito de diseño "
            "separado, no parte de la construcción.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
