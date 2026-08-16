import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="agronomo",
        titulo="Tercer especialista — Ingeniero Agrónomo, pedido explícito de Sebas con señal real",
        decision=(
            "Construido agronomo_agent/, tercer consumidor del template validado (Microbiólogo, "
            "Ingeniero Ambiental) — mismas simplificaciones que el Ingeniero Ambiental: solo "
            "frente_id, mismas 4 tools genéricas de corpus, mismo schema exacto de "
            "submit_evaluacion_tecnica. Evalúa uso agronómico (dosis, compatibilidad de cultivo/"
            "suelo, normativa de aplicación) de un producto/enfoque ya identificado por otro "
            "especialista — ángulo distinto del Microbiólogo (biología) y el Ingeniero Ambiental "
            "(ingeniería de proceso). El Conductor no necesitó cambios estructurales — sumar el "
            "tercer especialista fue una línea en _ESPECIALISTAS_CASOS (la generalización de la "
            "Etapa 7 pagó su costo de diseño en el primer uso real). 27 tests nuevos, 402/402 "
            "activos en verde, auditor sin ALTO/MEDIO nuevos. Verificado de punta a punta contra "
            "staging, vía la costura desde el primer intento (la lección de la Etapa 7 se aplicó "
            "sin repetir el error): documento_caso real (10.994 chars) creado y conectado al "
            "'Frente técnico' real de Helios — ahora hay 3 documentos de 3 especialistas "
            "distintos sobre el mismo frente, confirmando que frente_produce_documento escala a "
            "múltiples especialistas sin cambio de diseño."
        ),
        motivo=(
            "Sebas pidió explícitamente sumar el agrónomo. El Design Gate del Ingeniero Ambiental "
            "y PROPUESTA_DESTINO.md §11 habían dejado explícito que este especialista 'queda para "
            "si aparece un caso real que lo pida' — no se construyó por completar el trío de "
            "candidatos, se le preguntó primero si había señal real (mismo patrón que ya "
            "funcionó con las tools bioquímicas del Microbiólogo). Sebas confirmó: Helios "
            "necesita destino para su efluente, el sector agropecuario es un destino probable — "
            "señal real y concreta."
        ),
        alternativas_consideradas=[
            "Construir el agrónomo sin confirmar señal real primero, solo porque el trío de "
            "PROPUESTA_DESTINO.md §5 quedaba incompleto — descartado explícitamente: se preguntó "
            "primero, siguiendo el criterio de toda la sesión de no diseñar en abstracto.",
            "Rol general de producción agrícola en vez de 'uso agronómico de un enfoque ya "
            "identificado' — descartado: rompería el patrón de los otros 2 especialistas (cada "
            "uno evalúa una dimensión de un enfoque existente, no arranca de cero) y sería más "
            "genérico de lo que la señal real de Sebas pedía.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
