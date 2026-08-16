import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="web",
        titulo="Sesiones del chat del Conductor persistidas en el KM, no en memoria del proceso",
        decision=(
            "Área nueva `conductor_sesiones` (config/plantillas/conductor_sesiones.yaml), tipo "
            "`sesion`, sin vectorizar. `session_id` que ve el browser es directamente el id de la "
            "ficha — no hay traducción. conductor/conductor.py sumó serializar_mensajes() "
            "(convierte ContentBlock a dict plano vía dataclasses.asdict; no hace falta función "
            "inversa porque utils/ai_client.py::_mensajes_a_formato_openai ya acepta ContentBlock "
            "o dict plano indistintamente al armar la siguiente llamada al modelo). "
            "api/main.py reescrito: POST /conductor/sesiones crea la ficha (motor_api.guardar_ficha), "
            "POST /conductor/sesiones/{id}/mensajes lee props.mensajes (motor_api.obtener), lo pasa "
            "a enviar_mensaje(), reescribe props.mensajes (motor_api.actualizar_props). Eliminado "
            "el dict en memoria (_sesiones_conductor) por completo. SYSTEM_PROMPT del Conductor "
            "corregido — decía 'no persistís nada de esta conversación', ya no es cierto; ahora "
            "distingue historial crudo (sí persiste) de lección destilada (todavía no, Etapa 9). "
            "Verificado con el criterio de aceptación real: sesión creada, mensaje respondido, "
            "servidor matado con taskkill /F (no shutdown limpio), proceso nuevo levantado, segundo "
            "mensaje a la misma sesión recordó el primero — confirmado leyendo la ficha directo del "
            "KM (6 mensajes, incluido tool-use, serializados sin pérdida). Encontrado en el camino: "
            "api/.env nunca había existido (solo .env.example) — el chat de la Etapa 6 funcionaba "
            "porque nadie había reiniciado el server en un proceso fresco sin el entorno ya "
            "exportado a mano; corregido copiando .env (root) a api/.env, mismo patrón que ya "
            "documentaba api/.env.example. 409/409 unit activos en verde, auditor sin hallazgos "
            "nuevos."
        ),
        motivo=(
            "Sebas, mirando el chat recién construido en la misma sesión: 'las sesiones del chat "
            "viven en memoria del servidor (si reiniciás api/run.py, se pierden), cómo resolvemos "
            "esto?' — la deuda que el Design Gate de web/ había documentado como aceptada para v1 "
            "dejó de ser aceptable apenas la vio de cerca. Coherente con el principio ya vigente en "
            "CLAUDE.md: 'si el output de un agente no está en el KM, no existe para el sistema' — "
            "mismo precedente que pipeline_status/token_usage."
        ),
        alternativas_consideradas=[
            "Archivo JSON local en disco — descartado: invisible para cualquier otra instancia del "
            "sistema (Armador, Orquestador, un futuro agente), mismo argumento que ya excluye "
            "outputs/ local para cualquier otro agente.",
            "Cliente (browser) sostiene el historial serializado sin sesión en el server — "
            "descartado en la decisión original del mismo día (ver decisión previa 'Chat del "
            "Conductor en la web'), sigue sin ser la respuesta correcta incluso resuelto el "
            "problema de serialización, porque expondría el historial completo de negocio al "
            "cliente sin necesidad.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
