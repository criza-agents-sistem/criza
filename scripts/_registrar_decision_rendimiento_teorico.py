import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="biotecnologo",
        titulo="Etapa 22 (cont.) — calcular_rendimiento_teorico: balance de masa real para el Biotecnólogo",
        decision=(
            "utils/bioproceso.py::calcular_rendimiento_teorico (nuevo) — balance de masa vía "
            "pesos moleculares: moles de sustrato disponible (masa real / PM sustrato) -> moles "
            "de producto (según relación estequiométrica mol:mol de la reacción real, NUNCA "
            "inventada por el módulo) -> masa de producto, ajustada por una eficiencia de "
            "conversión asumida (default 100% = techo puro). Deliberadamente NO es un "
            "balanceador de ecuaciones químicas de propósito general -- toma la relación "
            "estequiométrica como un dato que el propio especialista trae, derivado de una "
            "reacción real que ya encontró con search_kegg/search_rhea o de un paper de "
            "search_literature. fuente_relacion_estequiometrica es un campo obligatorio, se "
            "propaga al resultado para auditoría. Sumada como tool nueva SOLO a "
            "biotecnologo_agent.py (18 tools) -- no a los otros 4 agentes que ya tienen "
            "utils/estadistica.py/utils/archivos.py, por ser específica del balance de masa de "
            "un bioproceso, no una necesidad mostrada en los demás dominios."
        ),
        motivo=(
            "Identificada en la conversación estratégica sobre qué le falta a CRIZA frente a "
            "Claude Science (2026-09-15): la brecha real entre 'este producto es biológicamente "
            "posible según la literatura' (lo que ya hacía search_literature) y 'vale la pena con "
            "el sustrato real que Helios tiene' (lo que faltaba) -- identificada como la función "
            "de mayor impacto real para el proyecto, no en abstracto, apoyada en que la "
            "composición real ya estaba disponible desde la tool de lectura de Excel de hoy "
            "mismo."
        ),
        alternativas_consideradas=[
            "Balanceador de ecuaciones químicas de propósito general (inferir la reacción real a "
            "partir de nombres de compuestos) -- descartado: proyecto mucho más grande y frágil, "
            "inferir estequiometría de bioprocesos en general no es un problema resuelto.",
            "Coeficiente de rendimiento empírico (Yp/s de un paper) en vez de balance de masa vía "
            "pesos moleculares -- descartado: el balance de masa reutiliza tools que el "
            "Biotecnólogo ya tiene (search_pubchem para pesos moleculares) y es más riguroso "
            "(conservación de masa real, no solo una razón reportada).",
            "Sumarla también a los otros 4 agentes con estadística/lectura de Excel -- "
            "descartado: es específica de bioprocesos, ningún otro especialista mostró necesidad "
            "real de un balance de masa.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
