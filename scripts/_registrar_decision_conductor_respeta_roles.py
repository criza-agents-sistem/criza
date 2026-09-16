import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="conductor",
        titulo="Etapa 22 (cont.) — el Conductor respeta el rol de cada agente, incluido el suyo",
        decision=(
            "Segundo bug de mezcla de roles encontrado en el mismo día, distinto del de "
            "fabricación (ver decisión 'previsualización de Excel confiable'): en el producto "
            "real desplegado, ante una pregunta sobre estabilidad de T401 y su relación con los "
            "sustratos de ingreso, el Conductor calculó él mismo rangos de pH/conductividad/"
            "FOS-TAC leyendo a ojo 5 filas de muestra de una previsualización, y concluyó 'indica "
            "proceso biológico controlado' -- una lectura técnica que le corresponde al "
            "Ingeniero Ambiental o al Microbiólogo, sobre una base de 5 filas que ni de "
            "casualidad alcanza para representar un dataset de cientos de registros. No era una "
            "fabricación (los números eran reales, leídos de celdas reales) pero sí una "
            "generalización no representativa presentada con la confianza de un cálculo real -- "
            "un problema epistémico distinto pero emparentado. Se agregó un 'SEGUNDO PRINCIPIO' "
            "al SYSTEM_PROMPT del Conductor (conductor/conductor.py), a la par del PRINCIPIO "
            "CENTRAL de no inventar el estado de un caso: respetar el rol de cada agente "
            "(microbiólogo/ingeniero ambiental/agrónomo/biotecnólogo/mercado/financiero, cada "
            "uno dueño de un tipo de pregunta) incluido el propio -- el Conductor orquesta, no "
            "analiza. Regla operativa dada: puede CITAR un hecho ya calculado por una tool real "
            "(ej. el rango de fechas o la cantidad de filas que la previsualización corregida "
            "hoy sí calcula), pero no puede promediar, sacar rangos, comparar tendencias ni sacar "
            "conclusiones técnicas de lo que ve -- eso siempre se deriva al especialista que "
            "corresponde."
        ),
        motivo=(
            "Sebas, mostrando la conversación real donde esto pasó y corrigiendo al Conductor en "
            "el momento: '¿por qué me respondés con datos, para eso están los agentes, lo que te "
            "pido que hagamos es entender cómo conducirlos?'. El Conductor se autocorrigió bien "
            "cuando se lo señalaron ('tenés razón, me confundí de rol, eso es trabajo de los "
            "agentes, no mío') y armó una secuencia de conducción razonable -- pero Sebas no "
            "debería tener que corregirlo cada vez. Pedido explícito de encuadre para el fix: "
            "'qué te parece si ir por el lado de respetar las funciones de cada agente, "
            "incluyendo la suya' -- no un parche puntual sobre esa pregunta, sino un principio "
            "general de rol, igual de central que el de no inventar."
        ),
        alternativas_consideradas=[
            "Prohibir puntualmente 'no calcules rangos de pH/conductividad' -- descartado: es un "
            "parche sobre el síntoma de hoy, no cubre la próxima variable o el próximo tipo de "
            "análisis que el Conductor intente hacer por su cuenta.",
            "Sumar tools de cómputo real al Conductor para que la respuesta sea correcta en vez "
            "de evitada -- descartado, ya decidido en la sesión de hoy (ver decisión previa): el "
            "Conductor orquesta, los especialistas calculan; revertir esa frontera no se "
            "justificaba por este bug.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
