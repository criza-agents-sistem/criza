import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r1 = await registrar_decision(
        componente="infra",
        titulo="Mejoras del motor del KM (docs/MEJORAS_KM.md) — evaluadas, diferidas",
        decision=(
            "Los 2 hallazgos de docs/MEJORAS_KM.md (conexiones tipadas no cruzan áreas; "
            "dedup_por debe coincidir con vectorizar) no bloquean nada hoy — ambos ya tienen "
            "un workaround funcionando en producción (participantes embebidos en props del "
            "caso; dedup_por: null donde hacía falta). No se arranca a tocar knowledge_module "
            "(Capa 1, compartido con DPN/Conflur/Biodarg) sin una necesidad real que lo "
            "justifique."
        ),
        motivo=(
            "Pedido explícito de Sebas: evaluar si hace falta ahora antes de arrancar, no "
            "asumir que todo hallazgo hay que resolverlo en la misma sesión que se encuentra. "
            "Cambiar código de plataforma compartido con otras instancias necesita una razón "
            "real, no solo 'ya que estamos'."
        ),
        alternativas_consideradas=[
            "Arrancar a evaluar/construir el fix de knowledge_module hoy — descartado: sin "
            "necesidad real hoy, y es código compartido con otras instancias.",
        ],
        quien="Sebas + Claude",
    )
    print("KM diferido:", r1)

    r2 = await registrar_decision(
        componente="deuda_tests",
        titulo="utils/tests resuelto — no colgaba de verdad, eran llamadas reales no mockeadas",
        decision=(
            "El 'cuelga' documentado el 13/08 era utils/tests/test_agrovoc.py haciendo "
            "llamadas reales a la API de AGROVOC en 10 tests que debían estar mockeados — "
            "parcheaban 'criza.utils.agrovoc._get' (prefijo 'criza.' de antes de la "
            "independización del 13/08, cuando el repo vivía anidado en EMPRESAS-IA/criza/), "
            "así que el mock no pegaba en el módulo real y corría la función de verdad. Sed "
            "reemplazando 'criza.utils.agrovoc.' por 'utils.agrovoc.' — de 16.88s (llamadas "
            "reales) a 0.17s. De paso, test_inta.py::test_harvest_con_fecha_filtra asumía que "
            "el parámetro from_date (mapea al 'from' de OAI-PMH, filtra por datestamp del "
            "repositorio) también filtraba el año de publicación del contenido — no es lo que "
            "el protocolo garantiza. Suavizada la aserción a lo que sí es cierto (la corrida "
            "no rompe y trae resultados)."
        ),
        motivo=(
            "utils/tests pasó de 'cuelga, sin investigar' a 30/30 passed (21 unit + 9 "
            "integration reales) en 22.94s, sin colgarse."
        ),
        alternativas_consideradas=[],
        quien="Sebas + Claude",
    )
    print("utils/tests resuelto:", r2)


if __name__ == "__main__":
    asyncio.run(main())
