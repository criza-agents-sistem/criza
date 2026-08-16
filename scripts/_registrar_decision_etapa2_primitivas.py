import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="orquestador",
        titulo="Etapa 2 del plan de construcción del nuevo sistema — primitivas de invocación del Motor",
        decision=(
            "Sumadas 3 primitivas nuevas a orquestador/motor.py: inspeccionar_caso() ('qué le "
            "falta a un caso' como consulta explícita, generaliza armador._validar_cobertura_"
            "upstream a cualquier step de cualquier flow), estimar_costo() (promedia "
            "props.token_usage real de otras oportunidades, nunca inventa un número — sin "
            "histórico queda None, no un cero encubierto), y reanudar_desde() (generaliza "
            "reanudar(): reconstruye estado solo desde el KM persistido, sin depender del "
            "gate_data en memoria de un MotorResult anterior — funciona aunque la sesión que "
            "pausó el flow ya no exista, la primitiva real detrás de 'otra puerta de entrada' "
            "de PROPUESTA_CONDUCTOR.md §3.1). 21 tests nuevos (18 unit + 1 integration real "
            "contra el KM que verifica que reanudar_desde no re-invoca un step ya completo). "
            "orquestador/docs/DESIGN_GATE.md actualizado — se agregó §7 para las 3 primitivas "
            "nuevas y se documentó explícitamente que §1-6 describen el Orquestador v1 "
            "(LLM-driven, reemplazado) y no el Motor v2 real — deuda de reescritura completa "
            "anotada, no resuelta hoy. 319/319 tests activos, auditor 68 hallazgos (66 antes + "
            "2 bajo esperados por texto de deuda en el Design Gate, mismo patrón que el resto "
            "de la sesión, sin ALTO/MEDIO nuevos)."
        ),
        motivo=(
            "Sebas: 'El Conductor es clave, no opcional' y sospecha que su ausencia fue parte "
            "de problemas previos. PROPUESTA_CONDUCTOR.md §5 exige estas 3 primitivas antes de "
            "construir el Conductor (Etapa 5) — construirlo sin ellas significaría adivinar su "
            "protocolo de invocación en vez de tenerlo resuelto de antemano."
        ),
        alternativas_consideradas=[
            "Construir el Conductor directamente y resolver estas primitivas sobre la marcha — "
            "descartado: el plan aprobado ya identificó estas 3 como prerrequisito explícito, "
            "resolverlas dentro del Conductor mezclaría diseño de infraestructura con diseño "
            "conversacional.",
            "estimar_costo() con una tabla de precios fija por agente en vez de histórico real "
            "— descartado: viola 'veracidad por dato' (CLAUDE.md) — un número fijo no reflejaría "
            "que cada corrida real varía según cuántas tools use el agente.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
