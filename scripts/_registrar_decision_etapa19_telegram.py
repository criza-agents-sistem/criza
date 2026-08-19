import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="conductor",
        titulo="Etapa 19 (cont.) -- bot de Telegram, segunda interfaz al Conductor, verificado real",
        decision=(
            "Con Vercel/Railway ya funcionando de punta a punta, Sebas pregunto cuanta complejidad "
            "tenia conectar el Conductor a Telegram. Baja-moderada: el Conductor ya expone sesiones "
            "de chat por HTTP (crear/enviar/cerrar), un bot de Telegram solo necesitaba un webhook "
            "nuevo que reuse esas mismas funciones, sin logica de chat duplicada. Sebas eligio "
            "arrancar. Dos decisiones de seguridad tomadas explicitamente por Sebas antes de "
            "codear (AskUserQuestion): (1) crear un bot nuevo via @BotFather en vez de reusar algo "
            "existente, (2) restringir el bot a un solo chat_id (el suyo, via @userinfobot) en vez "
            "de dejarlo abierto -- mismo criterio que SITE_AUTH en la web: un usuario real hoy, sin "
            "login complejo. Implementado: POST /telegram/webhook en api/main.py, reusa "
            "conductor_sesiones (plantilla extendida con telegram_chat_id opcional, nuevo campo) y "
            "_enviar_mensaje_conductor tal cual -- una sesion por chat_id, encontrada por "
            "telegram_chat_id en vez de por session_id como hace la web con localStorage (Telegram "
            "no tiene ese concepto, el chat_id ES la identidad persistente). Seguridad de dos "
            "capas: (a) el endpoint queda exento del middleware global de API_AUTH_USER/PASSWORD "
            "(Telegram no manda ese header) pero se autentica solo con TELEGRAM_WEBHOOK_SECRET, "
            "que Telegram reenvia en X-Telegram-Bot-Api-Secret-Token en cada pedido -- falla "
            "CERRADO si no esta configurado, al reves del criterio de API_AUTH que falla abierto "
            "en dev local (este endpoint es alcanzable desde internet en cuanto existe, no hay "
            "'modo local' seguro aca); (b) whitelist de TELEGRAM_ALLOWED_CHAT_ID -- mensajes de "
            "otro chat_id se ignoran en silencio (200 sin procesar), no confirmarle a nadie ajeno "
            "que el bot existe. Ack inmediato + BackgroundTasks (_procesar_mensaje_telegram): una "
            "corrida de especialista real puede tardar varios minutos, Telegram espera respuesta "
            "rapida al webhook, no el resultado de la conversacion -- la respuesta real se manda "
            "aparte via sendMessage cuando esta lista. Mensajes largos (informe de especialista > "
            "4096 caracteres, el limite de Telegram) se parten en trozos de 4000. Un error durante "
            "el procesamiento se le avisa a Sebas por el chat mismo -- es el unico lugar donde se "
            "entera, nadie mira logs del server desde Telegram. scripts/telegram_set_webhook.py "
            "registra la URL + secret en la API de Telegram (setWebhook), corrida manual una sola "
            "vez. 9 tests nuevos en api/tests/test_main.py -- secret ausente/incorrecto (403, "
            "falla cerrado), update sin texto (200 silencioso), chat_id no autorizado (200 "
            "silencioso), chat autorizado (procesa), sesion activa encuentra la mas reciente por "
            "telegram_chat_id o crea una nueva, respuesta real enviada por Telegram, error real "
            "avisado por Telegram. Regresion completa: 81 passed, 1 deselected (sentence_transformers "
            "no instalado en el entorno local, no relacionado). Verificado real de punta a punta "
            "por Sebas: '/start' + 'que hay pendiente?' en t.me/criza_conductor_bot -- el bot "
            "respondio con los 2 casos reales del KM (MicroBigs, Helios)."
        ),
        motivo=(
            "Sebas: '¿cuánta complejidad tiene conectar al conductor a Telegram?' -> 'dale, arrancá' "
            "tras la explicacion del tradeoff real (latencia de una corrida de especialista vs. "
            "el patron de ack-inmediato-mas-BackgroundTasks)."
        ),
        alternativas_consideradas=[
            "Bot abierto a cualquiera (sin whitelist) -- descartada explicitamente por Sebas al "
            "presentarle el tradeoff: cualquiera que encuentre el bot podria gastar tokens reales "
            "de su cuenta de Anthropic, mismo criterio que ya aplico en SITE_AUTH de la web.",
            "Responder sincronicamente en el webhook (esperar a que termine la corrida antes de "
            "devolver 200 a Telegram) -- descartada: una corrida de especialista real puede tardar "
            "varios minutos, Telegram no espera tanto a un webhook.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
