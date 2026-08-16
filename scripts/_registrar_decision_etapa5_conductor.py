import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="conductor",
        titulo="Etapa 5 del plan — Conductor conversacional construido",
        decision=(
            "Construido conductor/ — arquitectónicamente distinto a los 5 agentes existentes "
            "(todos de un solo turno, contrato SEB-115): es conversacional, multi-turno, sin "
            "submit_* que marque el final. No se registra en agents_registry.yaml (no es un "
            "step de flow). 4 tools, todas mapeadas 1:1 a mecanismo ya construido: listar_casos/ "
            "ver_caso (el briefing de docs/PROTOCOLO_LECTURA_CONDUCTOR.md, Etapa 3, adaptado al "
            "modelo real de casos.yaml en vez del modelo oportunidad+flow que las primitivas de "
            "Etapa 2 asumían) y correr_microbiologo/ver_documento (invoca al especialista vía la "
            "costura, nunca directo). Sumadas 2 funciones chicas a utils/casos.py "
            "(obtener_frentes_de_caso/obtener_documentos_de_frente) para completar el paralelo "
            "de inspeccionar_caso en el modelo de casos.yaml. Resolución de identificadores por "
            "nombre/fragmento, no solo UUID. 14 unit + 1 integration test, 354/354 activos en "
            "verde, auditor sin ALTO/MEDIO nuevos. Verificado con sesión conversacional real de "
            "3 turnos sobre Helios (no mock): listó los 2 casos reales correctamente, al "
            "preguntarle por Helios llamó ver_caso (no inventó el estado), reportó los "
            "pendientes reales del caso (reunión con Mateo, supuesto del flete sin confirmar) y "
            "recomendó no correr ningún análisis hasta resolver ese bloqueo — comportamiento "
            "equivalente al que Sebas ejerció a mano el 22/07."
        ),
        motivo=(
            "Primer pedido explícito de Sebas al arrancar el plan de esta sesión: 'el Conductor "
            "es clave, no opcional'. Ya tenía sus dos prerrequisitos de diseño/mecanismo "
            "resueltos (Etapa 2: primitivas de invocación; Etapa 3: protocolo de lectura) y, tras "
            "la Etapa 4 de hoy mismo, un camino real de escritura contra casos.yaml para operar "
            "sobre el caso real."
        ),
        alternativas_consideradas=[
            "Forzar el Conductor al contrato SEB-115 (run(contract_input) -> dict de una sola "
            "llamada) — descartado: el contrato asume un resultado final estructurado tras un "
            "loop que termina; el Conductor es multi-turno por diseño, forzarlo hubiera roto "
            "exactamente lo que lo hace útil (memoria de la conversación).",
            "Construir el Conductor contra el modelo oportunidad+flow (para reusar "
            "inspeccionar_caso/estimar_costo de Etapa 2 tal cual, sin funciones nuevas) — "
            "descartado: ningún caso real (Helios/MicroBigs) usa ese modelo hoy — hubiera sido "
            "diseño especulativo contra datos que no existen, en vez de construir contra el "
            "caso real disponible.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
