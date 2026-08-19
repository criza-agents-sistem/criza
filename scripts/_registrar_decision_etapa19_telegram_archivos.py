import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="conductor",
        titulo="Etapa 19 (cont.) -- el bot de Telegram acepta archivos, no solo texto",
        decision=(
            "Con el bot de Telegram de solo texto ya verificado, Sebas: 'le puedo subir docs?'. "
            "El webhook solo procesaba message.text -- un documento se ignoraba en silencio como "
            "cualquier update sin texto. Sebas pidio agregarlo ahora mismo. Refactor en "
            "api/main.py: /archivos/extraer (endpoint que ya usaba la web, Etapa 17) comparte "
            "ahora su logica de extraccion (pdf/docx/txt, truncado a _MAX_CARACTERES_ARCHIVO) via "
            "una funcion nueva _extraer_texto_generico + excepcion _ExtraccionInvalida, en vez de "
            "duplicarla para Telegram -- el endpoint HTTP mantiene el mismo comportamiento "
            "(400/422), confirmado con los tests existentes sin tocarlos. Al llegar un "
            "message.document por el webhook, se descarga via getFile + el link de descarga de "
            "Telegram, se extrae el texto con la misma logica que la web, se combina con el "
            "caption (mismo formato que combinarMensajeConArchivo de web/lib/api.ts) y se manda "
            "al Conductor como un mensaje mas -- reusa _procesar_mensaje_telegram tal cual. "
            "Simplificacion deliberada frente a la web: sin el paso de 'guardar como documento "
            "aportado a un frente' (Etapa 17b) -- armar ese flujo de varios turnos por Telegram "
            "(elegir frente por texto) es trabajo aparte no pedido; el archivo entra directo a la "
            "conversacion como texto. 7 tests nuevos. Regresion completa: 86 passed, 1 deselected. "
            "Verificado real por Sebas: subio un PDF con una instruccion de a que frente "
            "conectarlo -- el Conductor lo leyo y lo ubico donde pidio, usando sus propias "
            "herramientas de la costura (el mismo mecanismo que ya usa desde la web), sin que "
            "hiciera falta el flujo separado de 'elegir frente' que tiene la web."
        ),
        motivo="Sebas: 'le puedo subir docs?' -> 'agregalo ahora'.",
        alternativas_consideradas=[
            "Flujo de varios turnos por Telegram para elegir el frente antes de guardar el "
            "documento (paridad total con la web, Etapa 17b) -- descartada por ahora: mas trabajo "
            "no pedido, y la verificacion real mostro que el Conductor ya puede resolver la "
            "conexion al frente el solo, via sus propias herramientas, a partir de una "
            "instruccion en el mismo mensaje.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
