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
sys.path.insert(0, str(_AGENT_DIR))

from evidence_generalista import run_agent


async def main() -> None:
    if len(sys.argv) > 1:
        oportunidad_id = sys.argv[1].strip()
    else:
        oportunidad_id = input("Oportunidad ID: ").strip()

    if not oportunidad_id:
        print("ERROR: se requiere un oportunidad_id.")
        sys.exit(1)

    informe, evidencia, lecciones = await run_agent(oportunidad_id, verbose=True)

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
