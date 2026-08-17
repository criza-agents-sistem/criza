import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="web",
        titulo="Etapa 14 (arranque) — descarga de informes en Markdown",
        decision=(
            "GET /documentos/{id}/descargar en api/main.py -- Content-Disposition: attachment, "
            "nombre de archivo derivado del título vía _slug_archivo() (normaliza acentos/"
            "símbolos con unicodedata, no depende de que el header HTTP maneje bien UTF-8 en el "
            "filename). Link <a href> directo en /documentos/[id] y en la lista de documentos de "
            "/casos/[id] -- sin JS del lado del cliente, el navegador dispara la descarga solo "
            "por el header. Formato elegido explícitamente por Sebas: Markdown (el contenido ya "
            "está guardado así, sin conversión) en vez de PDF o Word. 5 tests nuevos, 456/456 "
            "unit en verde, auditor sin hallazgos nuevos. Verificado real contra el server de "
            "producción: descarga completa de un informe real de Helios (105 líneas, contenido "
            "íntegro), verificado por curl y en el navegador en ambos lugares donde aparece el "
            "link. Además, se usó la Etapa 12 (consulta libre) tal cual ya estaba construida para "
            "responder dos preguntas reales de composición química que Sebas quería hacerle al "
            "Microbiólogo sin el sesgo de los 3 documentos ya existentes de Helios -- confirma "
            "que el diseño de consulta libre cumple lo que promete, sin necesitar ningún cambio."
        ),
        motivo=(
            "Sebas, al arrancar la Etapa 14 (corregir/reiniciar un caso mal encarado): antes de "
            "diseñar, se le preguntó qué específicamente sentía mal encarado en Helios. Su "
            "respuesta reencuadró el problema (no es un dato mal cargado, es un ángulo de "
            "abordaje distinto) y de paso pidió, sobre la marcha, poder descargar los informes."
        ),
        alternativas_consideradas=[
            "PDF o Word (.docx) para la descarga -- descartados: Sebas eligió explícitamente "
            "Markdown para arrancar, más simple y sin necesitar una librería de conversión nueva.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
