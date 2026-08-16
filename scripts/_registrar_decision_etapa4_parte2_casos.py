import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="microbiologo",
        titulo="Etapa 4 (parte 2) del plan — Microbiólogo conectado al modelo de casos.yaml",
        decision=(
            "microbiologo_agent.py ahora soporta dos modelos de invocación mutuamente "
            "excluyentes: oportunidad_id (viejo, sin cambios de comportamiento) o frente_id "
            "(nuevo, casos.yaml). Nuevo utils/casos.py (genérico, reusable por futuros "
            "especialistas): obtener_frente_con_caso, obtener_pendientes_de_caso, "
            "guardar_documento_de_frente. orquestador/invocador.py::invocar_agente() extendido "
            "con parámetro frente_id — persiste documento_caso conectado vía "
            "frente_produce_documento en vez de props[prop_key], mismo principio de siempre (el "
            "agente no persiste, la costura sí). Loop agéntico refactorizado a _run_loop "
            "compartido entre run_agent()/run_agent_desde_frente() para no duplicar código. "
            "25 tests nuevos, 340/340 activos en verde, auditor sin cambios (68). Verificado en "
            "vivo de punta a punta CONTRA STAGING (no producción): documento_caso real (11.370 "
            "chars) creado y conectado al 'Frente técnico' real de Helios, confirmado leyendo "
            "el KM directamente; producción confirmada intacta (0 documentos) después de la "
            "corrida — la separación staging/producción de la parte 1 funciona como se diseñó."
        ),
        motivo=(
            "Continuación directa de la Etapa 4 (parte 1, staging) — el propósito de crear el "
            "branch de staging era justamente habilitar este trabajo (agentes escribiendo "
            "contra el modelo de casos reales) sin riesgo. Sebas: 'sigamos con la parte 2'."
        ),
        alternativas_consideradas=[
            "Reemplazar el modelo oportunidad_id en vez de sumarlo como camino alternativo — "
            "descartado: los 4 agentes viejos (mercado/evidencia/investigacion_amplia/armador) "
            "siguen sin tocarse por decisión explícita de PROPUESTA_DESTINO.md §6 — romper su "
            "contrato para forzar el modelo nuevo hubiera violado esa decisión ya tomada.",
            "Duplicar el loop agéntico completo en una función run_agent_desde_frente "
            "independiente — descartado: ~250 líneas de lógica de tools idéntica duplicada es "
            "exactamente el tipo de deuda que un cambio futuro (ej. sumar una tool nueva) "
            "hubiera tenido que replicar dos veces sin garantía de que no diverjan.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
