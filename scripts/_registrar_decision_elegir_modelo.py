import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="web",
        titulo="Etapa 15 — elegir modelo de IA por sesión de chat desde la web",
        decision=(
            "Granularidad: por sesión de chat, no global ni por agente -- las sesiones ya son la "
            "unidad natural del sistema (cada una su propia ficha KM), así que no hizo falta "
            "persistencia nueva, solo sumar un campo `modelo` a conductor_sesiones.yaml y "
            "especialista_sesiones.yaml y pasarlo como model= a enviar_mensaje() (ya aceptaba ese "
            "kwarg desde utils/ai_client.py, 2026-08-15). Lista curada, no texto libre: "
            "utils/ai_client.py::MODELOS_DISPONIBLES (4 modelos Anthropic) es la única fuente -- "
            "GET /modelos la expone tal cual. Lista curada en vez de texto libre porque hoy solo "
            "hay ANTHROPIC_API_KEY configurada (verificado en .env); ofrecer proveedores sin "
            "credenciales rompería al elegirlos. El modelo queda fijado al crear la sesión -- el "
            "selector se deshabilita apenas hay un turno, cambiarlo antes del primer mensaje "
            "recrea la sesión con el modelo nuevo. 12 tests nuevos, 464/464 unit en verde, "
            "auditor sin hallazgos nuevos. Verificado real (no solo tests): desde el navegador, "
            "elegido Haiku 4.5 en /conductor, mensaje real enviado, confirmado leyendo la ficha "
            "del KM que props.modelo == claude-haiku-4-5-20251001 y el turno quedó persistido; "
            "repetido en /especialistas/microbiologo con Opus 5, misma confirmación."
        ),
        motivo=(
            "Sebas pidió poder elegir qué modelo de IA usa una conversación desde la web, sin "
            "reiniciar el server con otra env var -- la abstracción de backend "
            "(utils/ai_client.py::resolver_modelo, PROPUESTA_DESTINO.md §8) ya existía y estaba "
            "verificada desde el 2026-08-15, pero no había ninguna superficie para elegirlo en "
            "runtime."
        ),
        alternativas_consideradas=[
            "Selección global (una env var por deployment) -- descartada: ya era el estado "
            "actual, no resuelve el pedido de elegir por conversación.",
            "Selección por agente (fija para todas las sesiones de un mismo especialista) -- "
            "descartada: menos flexible que por sesión sin ahorrar complejidad real.",
            "Texto libre para el modelo (cualquier string de LiteLLM) -- descartada: hoy solo hay "
            "credenciales de Anthropic, texto libre permitiría elegir un proveedor que rompe al "
            "usarlo.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
