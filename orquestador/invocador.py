"""
La costura — invocación de agentes con persistencia garantizada al KM.

Principio (PROPUESTA_CONDUCTOR.md §4.2): persistir el resultado es responsabilidad de quien
invoca, no del agente invocado. Todo lo que llama a un agente — el Motor orquestado hoy,
cualquier acceso directo a un especialista en el futuro (PROPUESTA_CONDUCTOR.md §3.1, "otra
puerta de entrada a la misma costura, nunca un bypass") — pasa por acá. Un agente nuevo no
puede "olvidarse" de escribir al KM porque ya no es su responsabilidad.

Contrato que un agente debe cumplir para que esto funcione (ver agents.md § Convención para
agregar un nuevo agente): el `análisis` que devuelve `run()` es exactamente lo que se guarda en
`props[prop_key]` — incluye una clave `informe_completo` con la narrativa completa, además de
los campos estructurados propios del agente. La costura no conoce ni le importa qué hay adentro
de `análisis` más allá de eso — lo persiste tal cual, sin casos especiales por agente.
"""

import logging

from knowledge_module.motor import api as motor_api

from orquestador.registry import AgentSpec

logger = logging.getLogger(__name__)


async def invocar_agente(
    spec: AgentSpec,
    contract_input: dict,
    tenant: str,
    oportunidad_id: str | None,
    verbose: bool = False,
) -> dict:
    """
    Corre un agente y persiste su resultado al KM — siempre, sin que el agente tenga que
    acordarse.

    No decide qué hacer si el agente no está disponible (eso es control de flujo, responsabilidad
    de quien llama — ver motor.py, que lo saltea con gracia). Acá se levanta ValueError si se
    invoca con un spec sin `run_fn`: sería un bug del llamador, no un caso a manejar en silencio.
    """
    if spec.run_fn is None:
        raise ValueError(f"Agente '{spec.nombre}' no disponible (inactivo o sin cargar)")

    output = await spec.run_fn(contract_input=contract_input, verbose=verbose)

    if oportunidad_id:
        analisis = output.get("análisis")
        if analisis is not None:
            await motor_api.actualizar_props(
                oportunidad_id, {spec.prop_key: analisis}, tenant=tenant,
            )
            if verbose:
                logger.info(
                    "[costura] props.%s persistido (oportunidad %s)",
                    spec.prop_key, oportunidad_id,
                )
        await _registrar_evento(spec.nombre, oportunidad_id, tenant, contract_input, output)

    return output


async def _registrar_evento(
    agente: str, oportunidad_id: str, tenant: str, contract_input: dict, output: dict,
) -> None:
    """
    Placeholder — se conecta con la captura de decisiones como eventos
    (PROPUESTA_CONDUCTOR.md §4.3, PROPUESTA_DESTINO.md §11). Diseño pendiente, próximo punto
    de la conversación — no implementar acá sin haberlo diseñado primero.
    """
    return None
