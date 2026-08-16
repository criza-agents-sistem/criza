"""
Runner del Especialista Ingeniero Agrónomo — CRIZA.

Uso:
  python run.py <frente_id>
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
        frente_id = sys.argv[1].strip()
    else:
        frente_id = input("Frente ID: ").strip()

    if not frente_id:
        print("ERROR: se requiere un frente_id.")
        sys.exit(1)

    spec = get_registry()["agronomo"]
    contract_input = {"conocimiento": {"frente_id": frente_id}}
    output = await invocar_agente(
        spec=spec,
        contract_input=contract_input,
        tenant=_TENANT,
        frente_id=frente_id,
        verbose=True,
    )
    evaluacion = output["análisis"]
    informe = evaluacion.get("informe_completo", "")
    lecciones = output.get("nuevo_conocimiento") or []

    print("\n" + "=" * 60)
    print("  RESULTADO")
    print("=" * 60)
    print(informe[:3000])
    if len(informe) > 3000:
        print(f"\n  ... [{len(informe) - 3000} caracteres más en el KM]")

    evaluacion_tecnica = evaluacion.get("evaluacion_tecnica", {})
    enfoques = evaluacion_tecnica.get("enfoques_tecnicos_identificados", [])
    print(f"\n  Enfoques identificados: {len(enfoques)}")
    for e in enfoques[:5]:
        print(f"    • [{e.get('madurez', '?')}] {e.get('enfoque', '')[:90]}")

    especialista = evaluacion.get("especialista_adicional_recomendado", {})
    if especialista.get("si_no"):
        print(f"\n  Especialista adicional recomendado: {especialista.get('descripcion', '')}")
    else:
        print("\n  Sin especialista adicional recomendado.")

    if lecciones:
        print(f"\n  Lecciones ({len(lecciones)}):")
        for l in lecciones:
            print(f"    • {l}")


if __name__ == "__main__":
    asyncio.run(main())
