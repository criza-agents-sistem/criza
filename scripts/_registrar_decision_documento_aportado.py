import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="web",
        titulo="Etapa 17b — el archivo aportado queda conectado al caso, no solo a la conversación",
        decision=(
            "Sebas, apenas probó la Etapa 17: 'pero si quiero que esa información que subo quede "
            "guardada para que la analicen los agentes? no entiendo la lógica de que no quede "
            "guardada. Yo esperaba que actuar con el agente se sintiera como con vos, pero no es "
            "igual.' Diagnóstico correcto: el diseño de la Etapa 17 sumaba el texto extraído al "
            "mensaje de ESA conversación puntual -- ninguna conversación futura del Conductor ni "
            "ninguna corrida formal de un especialista sabía que el documento existía. Confirmado "
            "con Sebas antes de diseñar: los archivos que sube siempre son sobre un caso/frente "
            "puntual (elegido explícitamente 'siempre atado' sobre 'a veces sin caso, como la "
            "consulta libre'). Construido: tipo de ficha nuevo documento_aportado "
            "(config/plantillas/casos.yaml), conectado al frente vía "
            "frente_tiene_documento_aportado -- distinto de documento_caso (lo produce un "
            "especialista) y de artefacto_externo (link sin contenido propio). Flujo en dos pasos "
            "separados a propósito: POST /archivos/extraer (stateless, ya existía) extrae el "
            "texto; POST /frentes/{id}/documentos-aportados (nuevo) lo persiste. Si la página no "
            "sabe el frente todavía (/conductor, especialista en consulta libre), un picker "
            "inline (caso -> frente) pregunta antes de guardar; con ?frente= ya conocido, se "
            "guarda directo. El Conductor (ver_caso incluye documentos_aportados_por_sebas en el "
            "briefing, ver_documento trae el contenido) y las 3 corridas formales de especialista "
            "(build_input_desde_frente recibe documentos_aportados, mismo camino para "
            "iniciar_sesion) ahora lo tienen disponible. GET /documentos/{id} y la descarga .md "
            "aceptan documento_aportado además de documento_caso. /casos/[id] lista los "
            "documentos aportados por frente con el link '📎 ... (aportado por vos)'. Tests "
            "nuevos en utils/casos, api/main, conductor, y los 3 especialistas -- 496/496 unit en "
            "verde, auditor sin hallazgos nuevos. Verificado real de punta a punta contra "
            "producción: el mismo PDF de composición química de Helios se adjuntó desde "
            "/conductor, se eligió Helios + Frente técnico en el picker real, se confirmó -- "
            "persistido y conectado (verificado leyendo el KM directo), apareció en /casos/[id]. "
            "Una conversación NUEVA y SEPARADA del Conductor (sin mencionar el archivo) preguntó "
            "por él y citó el dato exacto (nitrógeno amoniacal 1.200 mg/L) con análisis correcto "
            "-- confirma que el documento sobrevive a la conversación en la que se subió."
        ),
        motivo=(
            "Sebas: 'pero si quiero que esa información que subo quede guardada para que la "
            "analicen los agentes? no entiendo la lógica de que no quede guardada. Yo esperaba "
            "que actuar con el agente se sintiera como con vos, pero no es igual.'"
        ),
        alternativas_consideradas=[
            "A veces sin caso (como la consulta libre) -- descartada explícitamente por Sebas: "
            "los archivos que sube siempre son sobre un caso/frente puntual, no hace falta un "
            "estado intermedio 'archivo huérfano sin caso'.",
            "Persistir el archivo original además del texto -- descartada por ahora, no la pedía "
            "el requerimiento; el texto extraído es lo que los agentes necesitan analizar.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
