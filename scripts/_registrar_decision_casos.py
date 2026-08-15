import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="casos",
        titulo="Diseño concreto de la app: modelo de datos de caso + páginas (sin scaffold Next.js todavía)",
        decision=(
            "Área KM `casos` (config/plantillas/casos.yaml): tipo_ficha caso (nombre, "
            "descripcion, estadio, participantes embebidos), frente, pendiente, "
            "artefacto_externo, documento_caso (modo chat/documento — bisagra del §7.3), "
            "dato_extraido (contacto/cifra/plazo). 5 conexiones tipadas dentro del área. "
            "Páginas propuestas: / (lista de casos), /casos/[id] (frentes/pendientes/"
            "artefactos), /casos/[id]/frente/[id] (chat o documento), /casos/nuevo. "
            "Cargados los 2 casos reales (Biogás/Helios, MicroBigs) con datos sacados de "
            "casos/*.md — no inventados."
        ),
        motivo=(
            "PROPUESTA_DESTINO.md §7: 7 ideas ya confirmadas por Sebas a partir de releer los "
            "2 casos reales. El scaffold de Next.js en sí queda para una sesión propia con su "
            "Design Gate — esto es la parte de \"diseño concreto\" verificable hoy sin escribir "
            "frontend."
        ),
        alternativas_consideradas=[
            "Conexión tipada participa_en (usuario -> caso) — descartada otra vez por la misma "
            "restricción del loader (ver docs/MEJORAS_KM.md #1): se resuelve con participantes "
            "embebido en caso.props.",
            "Construir también el scaffold de Next.js hoy — descartado: módulo nuevo, necesita "
            "su propio Design Gate por CLAUDE.md, alcance mucho mayor que una sesión.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
