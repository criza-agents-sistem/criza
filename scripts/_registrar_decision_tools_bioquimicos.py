import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="microbiologo",
        titulo="Tools bioquímicas (KEGG, Rhea, UniProt, BacDive) sumadas al Especialista Microbiólogo — BRENDA diferida a Etapa 8",
        decision=(
            "Sumadas 4 tools nuevas al microbiólogo (search_kegg, search_rhea, search_uniprot, "
            "search_bacdive) — utils/kegg.py, utils/rhea.py, utils/uniprot.py, utils/bacdive.py, "
            "todas verificadas en vivo (curl real) antes de codear. Las 3 primeras son REST sin "
            "auth, verificadas funcionando en una corrida real completa contra Anthropic (5 "
            "turnos de tool-use, las 4 tools dispatcheadas correctamente por el LLM real). "
            "search_bacdive requiere cuenta gratis DSMZ (BACDIVE_EMAIL/BACDIVE_PASSWORD en "
            ".env) — sin credenciales configuradas, devuelve error explícito (verificado en la "
            "misma corrida real: el agente lo toleró sin romper el flujo). TOOLS pasó de 5 a 9 "
            "entradas, 36 tests nuevos (25 en microbiologo_agent + ~16 en utils/tests para los "
            "4 clientes), 274/274 tests activos en verde, auditor sin hallazgos nuevos (66, "
            "mismo total que antes). BRENDA (cinética de enzimas) quedó deliberadamente afuera "
            "de esta ronda — confirmado en vivo que su API es SOAP-only (WSDL real, sin "
            "equivalente REST) — se agregó como Etapa 8 explícita al plan de construcción "
            "(C:\\Users\\sebab\\.claude\\plans\\greedy-cooking-llama.md) para que no se pierda "
            "como ítem."
        ),
        motivo=(
            "Sebas confirmó necesidad real y concreta del caso que trae (Helios): 'sé que este "
            "caso real que tengo las va a pedir, así que las sumemos ahora y lo dejemos "
            "completo'. Pidió rigor en la selección ('quiero que estemos seguro que son las "
            "mejores opciones') — resuelto verificando cada API candidata en vivo antes de "
            "elegir, no por conocimiento de entrenamiento. Para BRENDA, confirmó 'opción 1, "
            "pero agregá una etapa al final donde sumamos a BRENDA' — no se descarta, se "
            "posterga con seguimiento explícito."
        ),
        alternativas_consideradas=[
            "Esperar a que una corrida real contra Helios muestre el hueco (decisión C original "
            "del Design Gate) — descartado por instrucción explícita de Sebas: su conocimiento "
            "de dominio sobre el caso real pesa más que la heurística general de 'esperar señal'.",
            "Sumar las 5 (incluyendo BRENDA) de una — descartado: BRENDA es SOAP-only, fricción "
            "de integración genuinamente distinta (cliente SOAP vs REST), ameritaba su propia "
            "etapa en vez de bloquear las 4 REST ya listas.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
