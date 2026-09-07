import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="market_agent",
        titulo="Etapa 20 -- Agente de Mercado reconectado a casos.yaml, los 5 especialistas se leen entre si",
        decision=(
            "El Conductor propuso (en la reunion de preparacion de Helios, 2026-08-24) 4 roles "
            "sin cubrir en el equipo IA: Analisis de mercado, Modelo economico-financiero, "
            "Propiedad intelectual, Vinculacion/laboratorios. Cruzado contra los 4 agentes viejos "
            "del expediente, el unico con cobertura real ya construida es market_agent -- pero "
            "desconectado del modelo de casos.yaml desde julio. Sebas: 'Vamos con el analisis de "
            "mercado.' Decision previa resuelta antes de codear (Sebas dudo si adaptar o "
            "construir de cero, 'me preocupa que adaptar sea un error') -- resuelto: adaptar, "
            "porque el problema real de specialist_proteins.py (abandonado, no adaptado) era "
            "supuestos INCORRECTOS hardcodeados a un caso cancelado, y aca el gap era una "
            "consideracion AUSENTE, no una equivocada -- las tools/framework/excepcion de "
            "web_search nativo son hard-won, adaptarlas no arriesga el mismo sesgo. Punto "
            "central: como evitar sesgo exportador SIN caer en el sesgo opuesto (asumir local "
            "por default). Sebas corrigio el primer planteo: 'no quiero que lo del flete sea un "
            "sesgo... que tipo de analisis haga dependera de los productos que son viables "
            "realizar tecnicamente.' Resuelto: el agente deriva el alcance geografico de la "
            "DENSIDAD DE VALOR del producto candidato real (valor economico por unidad de "
            "volumen/peso), caso por caso, nunca asumido de antemano en ninguna direccion. Esto "
            "exigio una capacidad nueva que Sebas generalizo a los 5 especialistas (no solo "
            "mercado): 'estaria bueno que todos puedan ver que esta realizando el resto' -- con "
            "preocupacion explicita de costo de tokens y escala ('a medida que crece el proyecto "
            "es mayor la cantidad de documentos... cuales ve y cuales no?'). Resuelto con el "
            "mismo patron que ya usa el Conductor: lista liviana SIEMPRE (todos los documentos "
            "del frente, solo metadata -- titulo/agente/fecha/id, barata sin importar la escala) "
            "+ lectura completa on-demand via tool nueva ver_informe_especialista, acotada por "
            "instruccion explicita de no leer todo. Implementado: utils/casos.py::"
            "obtener_documento_por_id (nuevo, extraido de conductor.py::_tool_ver_documento, "
            "preserva el fix de UUID invalido de la Etapa 16, reusado por los 5 especialistas). "
            "Retrofit de los 4 especialistas activos (microbiologo/ingeniero_ambiental/agronomo/"
            "biotecnologo): build_input_desde_frente gana documentos_producidos, tool "
            "ver_informe_especialista + dispatch, SYSTEM_PROMPT actualizado. market_agent.py "
            "reconectado completo (build_input_desde_frente, run_agent_desde_frente, "
            "iniciar_sesion/enviar_mensaje, TOOLS_CHAT, run() ahora exige frente_id -- deja de "
            "soportar oportunidad_id, mismo criterio que los otros 4), adaptado alrededor del "
            "cliente nativo de Anthropic (excepcion permanente ya decidida por web_search "
            "server-side). Nueva seccion 'ALCANCE GEOGRAFICO DEL MERCADO' en el SYSTEM_PROMPT + "
            "campos obligatorios nuevos en submit_analysis.cruce_4.accesibilidad_mercado "
            "(densidad_valor_producto, alcance_geografico_recomendado). mercado sumado a "
            "conductor.py, api/main.py, web/lib/api.ts, agents_registry.yaml. Bug real "
            "encontrado y arreglado durante la verificacion: hasattr(b, 'text') no filtra "
            "bloques nativos de Anthropic (server_tool_use, web_search_tool_result) que SI "
            "tienen el atributo .text pero en None -- corregido con getattr(b, 'text', None) en "
            "market_agent.py; el mismo patron existe en 8 modulos mas, flageado aparte via "
            "spawn_task, no corregido en este cambio. Regresion completa: 593 passed, 2 skipped. "
            "Verificado real de punta a punta contra produccion: conversacion de chat real contra "
            "el Frente tecnico de Helios -- el agente leyo los 2 informes reales del "
            "Biotecnologo, identifico 2 productos candidatos distintos (ectoina y un gel SAM "
            "biopolimerico), y recomendo alcance geografico OPUESTO para cada uno con "
            "justificacion real: ectoina (alta densidad de valor) -> exportacion/global citando "
            "el mercado europeo real; gel SAM (baja densidad de valor, mayormente agua) -> "
            "local, radio ~200-300km, el flete como restriccion real -- ninguna conclusion "
            "sesgada de antemano. Citó fuentes argentinas reales verificables (INTA, "
            "relevamiento INTA-Secretaria de Agricultura 2022, serie oficial de biogas)."
        ),
        motivo=(
            "Sebas: 'Vamos con el análisis de mercado... recuerda que no tenga sesgo exportador, "
            "porque los principales clientes serán cercanos por cuestión de flete, salvo que sea "
            "algo de muy grande valor agregado que se pueda exportar.' Y después, corrigiendo el "
            "planteo: 'no quiero que lo de flete sea un sesgo, la cuestión es desde donde hace el "
            "análisis este agente... qué tipo de análisis haga dependerá de los productos que son "
            "viables realizar técnicamente.'"
        ),
        alternativas_consideradas=[
            "Construir el Agente de Mercado de cero en vez de adaptar el existente -- descartada "
            "tras analizar que el problema de specialist_proteins.py (supuestos incorrectos "
            "hardcodeados) no aplica acá (gap ausente, no equivocado); reconstruir tools/"
            "framework hard-won sin ganar nada real.",
            "Mantener soporte a oportunidad_id además de frente_id -- descartada por "
            "consistencia con los otros 4 especialistas, que también lo dejaron de soportar al "
            "conectarse; los 2 flows viejos que lo usaban no están en uso por ningún caso real.",
            "Regla fija 'priorizar mercado local' -- descartada explícitamente por Sebas: "
            "hubiera introducido el sesgo opuesto al exportador. El alcance se deriva caso por "
            "caso de la densidad de valor real del producto, nunca asumido.",
            "Inyectar el contenido completo de todos los documentos producidos en el frente a "
            "cada especialista -- descartada por costo de tokens y por no escalar a medida que "
            "crece el proyecto (preocupación explícita de Sebas); resuelto con lista liviana + "
            "lectura on-demand, mismo patrón ya probado por el Conductor.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
