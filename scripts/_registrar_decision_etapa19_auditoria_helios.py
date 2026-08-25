import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="conductor",
        titulo="Etapa 19 (cont.) -- el Conductor ganó ver_herramientas_especialista + auditoría real de Helios",
        decision=(
            "Sebas pidió al Conductor un documento para una reunión con Helios sobre 'qué "
            "potencial tiene cada agente usando las herramientas a su disposición'. El Conductor "
            "respondió que los 4 especialistas 'corren sobre Claude, sin herramientas externas "
            "adicionales' -- FALSO: cada uno tiene bases de datos reales conectadas (OpenAlex, "
            "CONICET, INTA Digital, AGROVOC, y según el especialista KEGG/Rhea/UniProt/BacDive/"
            "PubChem/ChEBI), verificado leyendo TOOLS de cada módulo real. Causa raíz: el "
            "Conductor no tenía NINGUNA tool para introspectar qué herramientas tiene un "
            "especialista -- su SYSTEM_PROMPT solo describe roles a mano, terminó inventando una "
            "respuesta plausible. Doc corregido armado a mano (Artifact) para la reunión, con "
            "datos reales y links verificables. Fix estructural: orquestador/registry.py "
            "(AgentSpec.modulo_obj, el módulo completo además de run_fn -- ya se importaba para "
            "resolver run(), ahora también se guarda) + conductor/conductor.py (tool nueva "
            "ver_herramientas_especialista, lee TOOLS directo del módulo real vía el registry, "
            "nunca desactualizado a mano; excluye submit_evaluacion_tecnica, es el output del "
            "agente no una fuente de datos). SYSTEM_PROMPT del Conductor actualizado para usarla "
            "siempre que Sebas pregunte por capacidades del equipo. Verificado real contra el "
            "registry real (sin mocks): devolvió las 8 tools reales del Biotecnólogo. 10 tests "
            "nuevos, 301 passed en la regresión completa. Desplegado en Railway. "
            "Segunda parte, a pedido de Sebas ('chequeá qué hicieron los agentes'): auditoría "
            "real de los 13 documentos de Helios (no lo que dicen en general, las búsquedas "
            "concretas). Microbiólogo/Agrónomo/Biotecnólogo: trabajo sólido y transparente en "
            "las 10 corridas -- citas reales y verificables (Popovich et al. 2025 CONICET, Beily "
            "et al. INTA, etc.), y honestidad real cuando una fuente no devolvió nada (Biotecnólogo "
            "reportó 'KEGG: sin resultados' y 'Rhea: sin resultados' dos veces en vez de omitirlo). "
            "Ningún caso de acceso fallido sin avisar. Ingeniero Ambiental (3 corridas): ninguna "
            "tenía la sección narrativa 'Búsquedas realizadas' que sí tienen los otros 3 -- "
            "verificado contra el KM real (motor_api.obtener, no el informe) que el campo "
            "estructurado fuentes_y_cobertura SÍ estaba completo (7 búsquedas reales documentadas), "
            "así que NO fue un gap de investigación -- fue que ese trabajo real nunca se sintetizó "
            "a la narrativa que efectivamente se lee (ni /documentos/{id} ni ver_documento del "
            "Conductor exponen fuentes_y_cobertura directo). Sebas preguntó además si el "
            "Ingeniero Ambiental tiene acceso a los documentos que él sube -- confirmado en el "
            "código (build_input_desde_frente inyecta documentos_aportados completos al input de "
            "cada especialista, no solo al Conductor): sí, sí tiene acceso, la razón de los datos "
            "de composición específicos en sus informes son los documentos de Sebas, no un gap. "
            "Fix: los 4 SYSTEM_PROMPT (idénticos en ese punto) ya pedían completar "
            "fuentes_y_cobertura como campo estructurado -- se agregó la instrucción explícita de "
            "que no alcanza, informe_completo tiene que incluir la misma información en una "
            "sección visible 'Búsquedas realizadas'. Antes era comportamiento espontáneo de 3 de "
            "4 especialistas, ahora es un requisito escrito en los 4. Cambio de prompt únicamente, "
            "sin lógica nueva -- regresión completa de los 4 agentes (127 passed) sin romper nada, "
            "pero no se corrió un especialista real de punta a punta para este cambio puntual "
            "(gasta tokens reales) -- a verificar en la próxima corrida real de cualquiera de los 4."
        ),
        motivo=(
            "Sebas: 'te hago una consulta sobre el conductor, sabe las herramientas que tienen "
            "conectada los agentes...' -> tras confirmar el error, 'resolvelo ahora, hay tiempo... "
            "podés chequear qué hicieron los agentes para ver si usaron bien las herramientas'."
        ),
        alternativas_consideradas=[
            "Agregar la instrucción de documentar búsquedas solo al Ingeniero Ambiental (el único "
            "con el gap encontrado) -- descartada explícitamente por Sebas al presentarle el "
            "tradeoff: los otros 3 lo hacían espontáneamente, no por regla escrita, así que "
            "podían dejar de hacerlo en cualquier corrida futura sin que nadie lo note.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
