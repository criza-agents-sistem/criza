import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="web",
        titulo="Etapa 17 — adjuntar un archivo al chat del Conductor/especialistas",
        decision=(
            "Sebas pidió poder subirle un archivo al Conductor (Andrés le había mandado "
            "información de composición del efluente). No había ningún camino, ni web ni "
            "Conductor. Elegido explícitamente entre 'pasame el texto y lo pego yo' o 'construí "
            "carga de archivos real': carga real, con el criterio 'si vas a subir más seguido'. "
            "Diseño deliberadamente simple: POST /archivos/extraer NO persiste el archivo en "
            "ningún lado (ni KM ni disco) -- solo extrae el texto y lo devuelve; el frontend lo "
            "suma al próximo mensaje del chat, como si Sebas lo hubiera tipeado, mismo mecanismo "
            "de siempre (texto plano), sin inventar un tipo de contenido nuevo en el KM. "
            "Formatos: PDF, Word (.docx), texto (.txt/.md) -- cubre lo que alguien manda por "
            "mail/WhatsApp. Fuera de v1: .doc legacy y escaneos sin capa de texto (422 con "
            "mensaje claro). Regla de capa aplicada: extracción de PDF reusa "
            "knowledge_module.document_store.store.extract_text() (ya genérico de plataforma, "
            "existía para PDFs descargados por URL) sin reimplementarlo; extracción de "
            ".docx/.txt/.md se implementa en CRIZA por ahora, anotada como candidata a promover "
            "a knowledge_module si otra instancia la necesita. El texto combinado (archivo + "
            "mensaje tipeado) es exactamente lo que se manda y lo que se muestra en pantalla -- "
            "mismo string -- para no divergir de lo que aparece al reabrir la conversación desde "
            "el Historial (Etapa 16). Botón 📎 + chip de archivo adjunto en /conductor y "
            "/especialistas/[nombre]. 7 tests nuevos con archivos reales (PDF vía PyMuPDF, .docx "
            "vía python-docx, no mockeados), 482/482 unit en verde, auditor sin hallazgos nuevos. "
            "Verificado real: PDF con datos de composición química real, adjuntado desde el "
            "navegador, extraído correctamente, enviado a una sesión real del Conductor que leyó "
            "el contenido y respondió con un resumen correcto -- confirmado leyendo la ficha del "
            "KM que el mensaje persistido tiene el texto extraído completo. Durante esta "
            "verificación se encontró y arregló un bug real no relacionado (_tool_ver_documento "
            "sin capturar un ID inválido) -- registrado por separado, componente=conductor."
        ),
        motivo=(
            "Sebas: 'cómo le subo un archivo al conductor? Andrés me pasó información de la "
            "composición del efluente.'"
        ),
        alternativas_consideradas=[
            "Fix rápido: pedirle a Sebas que pegue el texto a mano cada vez -- descartado "
            "explícitamente por Sebas ('construí carga de archivos real, si vas a subir más "
            "seguido').",
            "Persistir el archivo original (no solo el texto extraído) -- descartado por ahora: "
            "no lo pedía el requerimiento de hoy, es una decisión aparte si surge la necesidad "
            "real de recuperar el archivo original más adelante.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
