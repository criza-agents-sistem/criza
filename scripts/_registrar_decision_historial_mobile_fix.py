import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="web",
        titulo="Etapa 22 (cont.) — el botón Historial del Conductor quedaba fuera de pantalla en mobile",
        decision=(
            "Sebas reportó 'no puedo cambiar entre conversaciones con el conductor' probando en "
            "el sitio desplegado. Reproducido en el navegador (local y contra el sitio real vía "
            "Chrome ya autenticado): en desktop, el mecanismo de Historial (web/app/conductor/"
            "page.tsx) funcionaba perfecto -- probado 4 veces sin fallar. La causa real apareció "
            "recién al emular un viewport de celular (375px): la fila de botones del header "
            "(selector de modelo, Características, Historial, Nueva conversación) no tenía "
            "flex-wrap, así que la página se desbordaba a 632px de ancho y el botón Historial "
            "quedaba literalmente fuera del viewport visible, alcanzable solo scrolleando la "
            "página entera hacia la derecha -- algo que nadie intenta instintivamente en un chat. "
            "Confirmado con el propio tooling de automatización, que no pudo hacer click en el "
            "botón por estar 'entirely outside the viewport'. Fix: agregado flex-wrap al "
            "contenedor del header y al de los botones, y el panel desplegable de Historial "
            "(antes 'w-96' anclado a la derecha, sin cap de ancho) ahora usa 'w-72' anclado a la "
            "izquierda en pantallas chicas (con un max-width relativo al viewport) y vuelve al "
            "comportamiento original ('w-96' anclado a la derecha) desde el breakpoint sm en "
            "adelante -- verificado que desktop quedó idéntico. Verificado real en mobile "
            "(375x812): el botón Historial es alcanzable, el panel abre completamente dentro del "
            "viewport sin recortes, y hacer click en una conversación distinta sí cambia el chat "
            "visible al contenido de esa conversación."
        ),
        motivo=(
            "Sebas: 'no puedo cambiar entre conversaciones con el conductor'. Antes de arreglar "
            "nada se investigó a fondo -- el mecanismo en sí (endpoints, fetch, estado de React) "
            "funcionaba bien en cada prueba de escritorio, lo que descartó un bug de lógica y "
            "apuntó a algo específico del entorno/dispositivo real de Sebas. La emulación mobile "
            "confirmó la causa raíz real antes de tocar código."
        ),
        alternativas_consideradas=[
            "Preguntar directamente por más detalles sin investigar -- descartado como primer "
            "paso porque el bug era reproducible por mi cuenta con las herramientas de browser "
            "disponibles (local + Chrome ya autenticado del propio Sebas), más rápido que una "
            "ida y vuelta.",
            "Centrar el panel del historial en vez de anclarlo a la izquierda en mobile -- "
            "descartado por simplicidad: anclar a la izquierda del botón (que ya está cerca del "
            "borde izquierdo en mobile) resuelve el overflow con un cambio de una clase, sin "
            "necesitar JS para calcular la posición.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
