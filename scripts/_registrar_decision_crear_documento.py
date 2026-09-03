import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="conductor",
        titulo="Etapa 19 (cont.) -- el Conductor gana la funcion de crear documentos",
        decision=(
            "Sebas: 'necesito asignarle al conductor la funcion de crear documentos' -- hoy "
            "solo podia producir un documento_caso indirectamente, invocando a un especialista "
            "(correr_especialista). Antes de codear, 3 decisiones confirmadas con Sebas "
            "(AskUserQuestion): trigger AMBOS (pedido explicito guarda directo; deteccion propia "
            "sin pedido propone titulo+resumen y espera confirmacion, mismo patron ya "
            "establecido por crear_caso); alcance SIEMPRE atado a un caso/frente (consistente "
            "con documento_caso/documento_aportado); contenido REDACCION LIBRE (el Conductor "
            "redacta el, no una transcripcion literal del chat). Implementado: tool nueva "
            "crear_documento (caso, frente, titulo, contenido) en conductor/conductor.py -- "
            "_tool_crear_documento reusa utils/casos.py::guardar_documento_de_frente tal cual "
            "(ya existia, pensado para especialistas, no hizo falta persistencia nueva) con "
            "agente='conductor', mismo tipo documento_caso de siempre -- aparece automaticamente "
            "en documentos_producidos_detalle (Decision I, Etapa 19 cont. del 2026-08-18) sin "
            "tocar nada ahi. 7 tests nuevos, test_tools_count actualizado (7 a 8). Verificado "
            "real de punta a punta contra staging (no produccion): 3 conversaciones reales con "
            "enviar_mensaje() -- (1) pedido explicito, documento creado y confirmado leyendo el "
            "contenido de vuelta con ver_documento en una conversacion nueva; (2) pregunta normal "
            "sin pedir guardar, cero tool calls; (3) insinuacion sin confirmar, propuso titulo + "
            "resumen y pregunto '¿Lo guardo asi?' sin llamar la tool todavia. Los 3 caminos se "
            "comportaron exactamente como se diseno. Regresion completa: 567 passed (excluyendo "
            "el fallo ambiental preexistente de sentence_transformers)."
        ),
        motivo=(
            "Sebas: 'necesito asignarle al conductor la función de crear documentos.'"
        ),
        alternativas_consideradas=[
            "Solo trigger explicito (sin propuesta proactiva) -- descartada: Sebas eligio "
            "explicitamente 'en ambas situaciones' al preguntarle.",
            "Documentos sin caso/frente (charla libre) -- descartada: Sebas eligio 'siempre "
            "atado a un caso/frente', consistente con el resto del modelo de datos.",
            "Guardar tal cual el texto que Sebas pasa, sin que el modelo redacte -- descartada: "
            "Sebas eligio 'redaccion libre a partir de la conversacion' (minuta/sintesis real, "
            "no una transcripcion).",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
