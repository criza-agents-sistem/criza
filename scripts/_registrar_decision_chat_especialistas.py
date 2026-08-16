import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="web",
        titulo="Etapa 10 — chat directo con cada especialista (no solo con el Conductor)",
        decision=(
            "Mismo patrón en los 3 especialistas (microbiologo_agent.py, "
            "ingeniero_ambiental_agent.py, agronomo_agent.py): el dispatch de tools que vivía "
            "inline en el if/elif de _run_loop se extrajo a _despachar_tool() propia (refactor "
            "behavior-preserving, verificado corriendo los tests existentes sin cambios antes de "
            "sumar nada nuevo) para que el chat la reuse sin duplicar ~170 líneas por agente. "
            "iniciar_sesion(frente_id) arma el primer mensaje con el mismo contexto que la corrida "
            "formal; enviar_mensaje(messages, texto, frente_id) es un loop conversacional tipo "
            "conductor.enviar_mensaje(). TOOLS_CHAT excluye submit_evaluacion_tecnica a propósito: "
            "el chat da acceso al mismo conocimiento pero la evaluación formal persistida sigue "
            "siendo exclusiva del camino de un turno vía la costura -- mismo principio de 'nunca "
            "bypasear la costura' que ya rige el Conductor. api/main.py sumó POST "
            "/especialistas/{nombre}/sesiones y POST /especialistas/sesiones/{id}/mensajes, área "
            "nueva especialista_sesiones en el KM. Web: web/app/especialistas/[nombre]/page.tsx "
            "(client component, scoped a frente vía ?frente=<id>) + links por frente en "
            "/casos/[id]. Hallazgo real no cosmético: conectar api/main.py a los 3 especialistas "
            "rompió la regresión combinada -- los 3 agentes tienen DOS consumidores incompatibles "
            "en el mismo proceso (orquestador/registry.py::get_registry(), package-qualificado y "
            "perezoso; el conftest.py/run.py de cada agente, bare) -- cualquiera de los dos "
            "estilos que tocara primero sys.modules[nombre] rompía al otro, y el propio archivo "
            "del agente inserta su carpeta al frente de sys.path como efecto de lado al cargar, lo "
            "que por sí solo ya alcanza para romper una resolución posterior. Resuelto con "
            "importlib.util.spec_from_file_location bajo una clave propia (_api_<nombre>), "
            "restaurando sys.path después de cada carga -- verificado que get_registry() sigue "
            "funcionando después. 11 tests nuevos en los 3 agentes + 6 en api/tests, 436/436 unit "
            "en verde, auditor sin hallazgos nuevos. Verificado real: sesión de chat real con el "
            "Microbiólogo sobre el Frente técnico de Helios, respuesta sustancial con fuentes "
            "reales -- confirmado leyendo el KM que NO se creó un 4to documento_caso (seguían "
            "siendo los mismos 3 de las corridas formales), la separación chat/persistencia formal "
            "funciona como se diseñó."
        ),
        motivo=(
            "Sebas, en el mismo hilo donde se confirmó la persistencia de sesiones del Conductor: "
            "pidió explícitamente poder hablar con cada especialista, no solo con el Conductor, "
            "junto con el panel de características (Etapa 11) y que el Conductor escriba "
            "lecciones (Etapa 9, ya resuelta)."
        ),
        alternativas_consideradas=[
            "Reemplazar run() por un loop conversacional en cada especialista -- descartado: "
            "run() (contrato SEB-115, de un turno) sigue siendo lo que usa el Motor/la costura "
            "para la evaluación formal; forzar todo a un loop conversacional hubiera roto ese "
            "contrato sin necesidad.",
            "Bare import o package-qualificado para que api/main.py acceda a los 3 especialistas "
            "-- ambos descartados tras confirmar en vivo que cualquiera de los dos colisiona con "
            "el otro consumidor real (get_registry() vs. los propios tests/run.py de cada agente) "
            "en el mismo proceso del server.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
