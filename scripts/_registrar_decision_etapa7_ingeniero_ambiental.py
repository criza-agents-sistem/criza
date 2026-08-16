import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="ingeniero_ambiental",
        titulo="Etapa 7 del plan — segundo especialista, Ingeniero Ambiental",
        decision=(
            "Construido ingeniero_ambiental_agent/, clonado de microbiologo_agent.py (patrón "
            "probado dos veces ahora), con una simplificación real: solo soporta frente_id, no "
            "oportunidad_id (ningún caller real necesitaría el modelo viejo para un especialista "
            "construido hoy). Mismas 4 tools genéricas de corpus, mismo schema exacto de "
            "submit_evaluacion_tecnica que microbiologo_agent (ya anticipado en su decisión E). "
            "El Conductor (conductor.py) se generalizó: correr_microbiologo -> "
            "correr_especialista(nombre, caso, frente, ...), validado contra una lista explícita "
            "_ESPECIALISTAS_CASOS (no inferida del registry completo, para que los 4 agentes "
            "viejos oportunidad_id-only no sean invocables desde ahí). 19 tests nuevos + 3 en "
            "conductor/tests, 383/383 activos en verde, auditor sin ALTO/MEDIO nuevos. Corregido "
            "en el camino: la primera versión del integration test llamaba al agente directo sin "
            "pasar por la costura, y 'pasaba' sin haber probado la persistencia real — corregido "
            "para pasar por invocar_agente(). Verificado de punta a punta contra staging: "
            "documento_caso real (10.885 chars) creado y conectado al 'Frente técnico' real de "
            "Helios — ahora hay 2 documentos reales de 2 especialistas distintos sobre el mismo "
            "frente, primer caso real de la conexión 1-a-N frente_produce_documento en uso."
        ),
        motivo=(
            "No una elección abstracta entre los 3 candidatos de PROPUESTA_DESTINO.md §5 — el "
            "Microbiólogo (Etapa 4) ya había recomendado en una corrida real contra Helios "
            "'balance de masa y energía de las rutas de concentración' y 'diseño de biorreactor' "
            "— exactamente el dominio de un ingeniero ambiental/de procesos. Se construyó el "
            "especialista que un especialista real ya pidió, no uno elegido en el papel."
        ),
        alternativas_consideradas=[
            "Construir el agrónomo (tercer candidato de §5) en vez del ingeniero ambiental — "
            "descartado: no hay señal real de un caso que lo necesite hoy, mientras que el "
            "ingeniero ambiental es literalmente lo que el Microbiólogo ya pidió.",
            "Sumar el camino oportunidad_id al nuevo especialista, por consistencia con el "
            "Microbiólogo — descartado: ningún flow YAML ni caller real lo invocaría así, "
            "hubiera sido diseñar para un caller hipotético.",
            "Sumar un tool nuevo (correr_ingeniero_ambiental) al Conductor en vez de "
            "generalizar — descartado: con 2 especialistas ya era visible que no escala, cada "
            "especialista nuevo futuro hubiera exigido tocar TOOLS + dispatch + SYSTEM_PROMPT "
            "de nuevo.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
