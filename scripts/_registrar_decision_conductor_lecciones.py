import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="conductor",
        titulo="Etapa 9 — el Conductor escribe lecciones al KM (automático al cerrar sesión + explícito a pedido)",
        decision=(
            "conductor.py sumó cerrar_sesion(messages, *, tenant, verbose=False): corta si hay "
            "menos de 2 turnos reales; si no, lee lecciones ya existentes sobre temas análogos "
            "(aprendizaje.leer_lecciones_caso) y le pasa el transcript completo a un juez de una "
            "sola llamada (tool submit_leccion, sin forzar tool_choice, mismo patrón submit_* sin "
            "forzado que ya usan los especialistas) que decide hay_leccion_nueva; si true y no "
            "cubierta, guarda con fuente=agente_auto. Tool nueva anotar_leccion para el trigger "
            "explícito (fuente=humano), misma guardar_leccion_caso que ya usa el resto del sistema "
            "(SEB-156) -- nada nuevo del lado de persistencia. CLI (run.py) llama cerrar_sesion al "
            "salir (punto de cierre natural). Web: nuevo endpoint POST "
            "/conductor/sesiones/{id}/cerrar, botón 'Nueva conversación' en /conductor lo llama "
            "awaited antes de crear sesión nueva, más beforeunload+sendBeacon como red de "
            "contención best-effort. SYSTEM_PROMPT corregido -- ya no dice que el Conductor no "
            "persiste nada de la conversación (desactualizado apenas se resolvió la persistencia "
            "de sesiones horas antes el mismo día). 11 tests nuevos (8 conductor + 3 api), "
            "419/419 unit activos en verde, auditor sin hallazgos nuevos. Verificado real (no solo "
            "mocks): trigger explícito guardó 3 lecciones reales bien formadas contra el modelo "
            "real; trigger automático dijo 'no' correctamente en una conversación de solo-lectura; "
            "anti-duplicación confirmada (reconoció como 'ya cubierta' una lección que el trigger "
            "explícito ya había guardado en la misma sesión). Observación real, no bug: el modelo "
            "tendió a invocar anotar_leccion por su cuenta ante afirmaciones sustanciales aunque el "
            "prompt pide no hacerlo sin pedido explícito -- deja la rama 'automático positivo sin "
            "pedido previo' cubierta solo por tests con mock en esta sesión, documentado como "
            "observación no urgente en el Design Gate."
        ),
        motivo=(
            "Al confirmar la persistencia de sesiones del chat, Sebas aclaró una confusión real: "
            "pensaba que el Conductor ya escribía al KM una parte de 'aprender de la experiencia' "
            "-- el área lecciones (SEB-156) ya existe y el Conductor ya la lee (ver_caso -> "
            "leer_lecciones_caso), pero nunca escribía ninguna. Trigger confirmado por Sebas ante "
            "pregunta explícita: ambos (automático al cerrar sesión + explícito a pedido) -- "
            "cierra el loop de aprendizaje transversal que CLAUDE.md exige para todo agente "
            "('leer lecciones análogas antes de actuar, escribir después'), del que el Conductor "
            "era el único agente que solo leía."
        ),
        alternativas_consideradas=[
            "Forzar tool_choice en la llamada del juez de cierre -- descartado: utils/ai_client.py "
            "no expone tool_choice hoy, y el patrón submit_* sin forzado ya es suficientemente "
            "confiable en el resto del sistema (verificado en corridas reales de los 3 "
            "especialistas) -- no vale la pena el costo de sumar el parámetro para este caso.",
            "Inferir el cierre de sesión por inactividad (con un cron/job periódico) -- descartado: "
            "sin infraestructura de scheduled jobs en el proyecto hoy, hubiera sido construir "
            "infraestructura nueva especulativa para un caso de uso (Sebas cerrando la pestaña sin "
            "avisar) que ya tiene una solución más simple (beforeunload+sendBeacon, best-effort) "
            "suficiente para v1.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
