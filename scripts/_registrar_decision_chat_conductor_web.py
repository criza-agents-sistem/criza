import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="web",
        titulo="Chat del Conductor en la web — v1.2 adelantada el mismo día, más promoción de staging a producción",
        decision=(
            "api/main.py sumó POST /conductor/sesiones y POST /conductor/sesiones/{id}/mensajes, "
            "envolviendo conductor.enviar_mensaje() tal cual — misma función que usa el CLI. "
            "Sesiones en memoria del proceso (session_id -> messages) porque messages mezcla "
            "dicts planos y objetos del SDK de Anthropic no serializables a JSON — válido para "
            "un usuario local, no para multi-usuario. web/app/conductor/page.tsx: único client "
            "component de la app (los otros 3 son Server Components), interactivo. Corregido en "
            "el camino: api/main.py importaba 'from conductor.conductor import enviar_mensaje' "
            "(calificado por paquete), lo que cacheaba el paquete vacío en "
            "sys.modules['conductor'] y rompía 'import conductor as cond' de "
            "conductor/tests/test_conductor.py cuando ambas suites corrían en el mismo proceso "
            "pytest (17 tests fallaban solo en la regresión combinada) — corregido insertando "
            "conductor/ al frente del sys.path e importando bare, mismo truco de "
            "conductor/run.py. Además, promovidos a producción los 3 documento_caso reales "
            "(microbiólogo, ingeniero ambiental, agrónomo) que vivían en staging — Sebas eligió "
            "explícitamente promoverlos en vez de dejarlos solo en staging o re-correr contra "
            "producción. Verificado en el navegador de verdad: conversación real de 2 turnos, "
            "el Conductor reportó correctamente los 3 documentos recién promovidos y sintetizó "
            "el cuello de botella real del caso (pendientes de negocio, no técnicos). "
            "407/407 unit activos en verde, npm run build sin errores, auditor sin cambios."
        ),
        motivo=(
            "Sebas pidió acceso a la web esperando poder hablar con los agentes, no solo "
            "navegar en modo lectura — al aclarársele que eso era v1.2 (ya anotado, no v1), "
            "respondió 'no le encuentro mucha utilidad a lo que hay ahora, no había entendido "
            "eso' y eligió explícitamente adelantar v1.2 en la misma sesión en vez de dejarlo "
            "pendiente."
        ),
        alternativas_consideradas=[
            "Cliente (browser) sostiene el historial de mensajes entre requests, sin sesión en "
            "el server — descartado: messages incluye objetos del SDK de Anthropic no "
            "serializables a JSON tal cual, hubiera exigido reconstruirlos en cada ida y vuelta "
            "sin garantía de que la reconstrucción coincida con lo que utils/ai_client.py espera.",
            "Dejar los 3 documentos solo en staging y no darle acceso a Sebas hasta re-correr "
            "contra producción — descartado: Sebas prefirió promover lo ya verificado en vez de "
            "re-pagar tokens de una corrida ya probada exitosa.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
