import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="web",
        titulo="Etapa 13 — crear casos nuevos desde la web y el Conductor",
        decision=(
            "utils/casos.py::crear_caso(nombre, descripcion, tenant, estadio=None, "
            "fecha_inicio=None, participantes=None, notas=None) -- función base compartida, "
            "computa texto_busqueda (campo vectorizado de casos.yaml) a partir de "
            "nombre+descripción. Un caso puede crearse sin frentes (ya permitido explícitamente "
            "por casos.yaml). POST /casos en api/main.py -- nombre/descripcion obligatorios (400 "
            "si faltan), resto opcional, escribe directo a producción (primera excepción "
            "deliberada a '/casos es solo lectura', mismo criterio que /conductor/* y "
            "/especialistas/*). web/app/casos/nuevo/page.tsx -- formulario, redirige a "
            "/casos/{id} al crear; link '+ Nuevo caso' en /. Tool crear_caso del Conductor llama "
            "la misma utils/casos.py::crear_caso -- SYSTEM_PROMPT instruye confirmar (resumir "
            "nombre+descripción) antes de llamarla, mismo criterio que correr_especialista, más "
            "importante acá porque no hay forma de corregir un caso mal armado todavía (Etapa "
            "14, sin resolver). 10 tests nuevos (2 utils, 4 api, 4 conductor), 451/451 unit en "
            "verde, auditor sin hallazgos nuevos. Verificación real con decisión explícita de "
            "Sebas sobre cómo hacerla (el endpoint no tiene staging intermedio): contra staging, "
            "no producción -- crear_caso() real, campos correctos, aparece en listar_casos. "
            "Contra el server de producción, sin escribir nada de prueba: página /casos/nuevo "
            "renderiza y valida bien, conversación real con el Conductor describiendo un caso "
            "nuevo pidió confirmación y no llamó la tool -- confirmado que /casos seguía "
            "teniendo los mismos 2 casos reales de siempre."
        ),
        motivo=(
            "Sebas, el 16/08: '¿cómo abro un caso nuevo? ¿solo con el Conductor?' -- se le "
            "respondió con honestidad que no había ningún camino, ni web ni Conductor. Agendado "
            "para retomar ('dejemos agendado para mañana') y resuelto al continuar la sesión, "
            "primero de 3 ítems en el orden acordado."
        ),
        alternativas_consideradas=[
            "Solo formulario web o solo tool del Conductor -- descartado: Sebas eligió "
            "explícitamente los dos (pregunta directa antes de codear), reusando la misma "
            "función base para no duplicar la lógica de creación entre las dos superficies.",
            "Verificar contra producción con un caso de prueba y borrarlo después -- descartado: "
            "Sebas eligió explícitamente verificar solo contra staging para no tocar producción "
            "en absoluto, ni siquiera de forma reversible.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
