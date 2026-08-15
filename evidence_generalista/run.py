"""
Runner del Evidence Generalista CRIZA.

Uso:
  python run.py <oportunidad_id>
  python run.py             # pide el ID interactivamente
"""

import asyncio
import sys
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout = open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1)
if sys.stderr.encoding != "utf-8":
    sys.stderr = open(sys.stderr.fileno(), mode="w", encoding="utf-8", buffering=1)

_AGENT_DIR = Path(__file__).parent
_CRIZA_DIR = _AGENT_DIR.parent
sys.path.insert(0, str(_AGENT_DIR))
if str(_CRIZA_DIR) not in sys.path:
    sys.path.insert(0, str(_CRIZA_DIR))

from orquestador.registry import get_registry
from orquestador.invocador import invocar_agente

_TENANT = "criza"


async def main() -> None:
    if len(sys.argv) > 1:
        oportunidad_id = sys.argv[1].strip()
    else:
        oportunidad_id = input("Oportunidad ID: ").strip()

    if not oportunidad_id:
        print("ERROR: se requiere un oportunidad_id.")
        sys.exit(1)

    # Vía la costura (invocar_agente) — mismo camino que usa el Motor, para que el
    # write-back al KM ocurra siempre.
    spec = get_registry()["evidencia"]
    contract_input = {"conocimiento": {"oportunidad_id": oportunidad_id}}
    output = await invocar_agente(
        spec=spec,
        contract_input=contract_input,
        tenant=_TENANT,
        oportunidad_id=oportunidad_id,
        verbose=True,
    )
    evidencia = output["análisis"]
    informe = evidencia.get("informe_completo", "")
    lecciones = output.get("nuevo_conocimiento") or []

    print("\n" + "=" * 60)
    print("  RESULTADO")
    print("=" * 60)
    print(informe[:3000])
    if len(informe) > 3000:
        print(f"\n  ... [{len(informe) - 3000} caracteres más en el KM]")

    cruce_2 = evidencia.get("cruce_2", {})
    estado = cruce_2.get("estado_cientifico", {}).get("valor", "—")
    print(f"\n  Estado científico: {estado}")

    especialista = evidencia.get("especialista_recomendado", {})
    if especialista.get("si_no"):
        print(f"  Especialista recomendado: {especialista.get('descripcion', '')}")
    else:
        print("  Sin especialista recomendado.")

    if lecciones:
        print(f"\n  Lecciones ({len(lecciones)}):")
        for l in lecciones:
            print(f"    • {l}")


if __name__ == "__main__":
    asyncio.run(main())
