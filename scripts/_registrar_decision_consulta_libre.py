import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="web",
        titulo="Etapa 12 — consulta libre a un especialista, sin necesitar un caso",
        decision=(
            "frente_id: str | None = None en enviar_mensaje() de los 3 especialistas. Sin "
            "frente_id: no se llama obtener_frente_con_caso (cero queries de más), y la consulta "
            "de lecciones usa el texto de la pregunta en vez de una descripción de caso que no "
            "existe -- más preciso, no un downgrade. Resultado neto: la consulta libre es MÁS "
            "barata en tokens que el modo con caso, no una alternativa degradada. api/main.py: "
            "frente_id opcional en POST /especialistas/{nombre}/sesiones -- sin él, la sesión "
            "arranca vacía sin llamar iniciar_sesion. web/app/especialistas/[nombre]/page.tsx sin "
            "?frente= entra en modo libre automáticamente (antes mostraba un error). "
            "web/app/especialistas/page.tsx (listado) suma link 'Consulta libre' por especialista. "
            "4 tests nuevos, 441/441 unit en verde, auditor sin hallazgos nuevos. Verificado real: "
            "sesión libre con el Microbiólogo respondida correctamente sin ningún caso de por "
            "medio, confirmado leyendo el KM que la ficha quedó con frente_id: None."
        ),
        motivo=(
            "Sebas, mirando el chat de un especialista recién construido, preguntó tres cosas de "
            "una: por qué el chat requería un frente ('¿no puedo hacerles preguntas que no sean "
            "en el marco de un caso?'), le preocupaba el consumo de tokens para una consulta "
            "simple, y preguntó cómo abrir un caso nuevo. Se le respondió con honestidad que hoy "
            "NINGÚN camino (ni la web ni el Conductor) permite crear un caso -- gap real, no "
            "resuelto, anotado como Etapa 13 aparte. Eligió resolver primero la consulta libre "
            "(su necesidad inmediata) y dejar crear-casos para después."
        ),
        alternativas_consideradas=[
            "Dejar frente_id obligatorio y decirle a Sebas que siempre tiene que crear un caso "
            "primero -- descartado: no resolvía su necesidad real (consulta rápida antes de "
            "decidir si vale la pena abrir un caso) y hubiera significado gastar tokens en armar "
            "un caso para una pregunta que quizás no lo amerita.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
