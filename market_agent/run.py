"""
Runner del Agente de Mercado — CRIZA (reconectado a casos.yaml en Etapa 20, 2026-09-07).

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

    spec = get_registry()["mercado"]
    contract_input = {"conocimiento": {"frente_id": frente_id}}
    output = await invocar_agente(
        spec=spec,
        contract_input=contract_input,
        tenant=_TENANT,
        frente_id=frente_id,
        verbose=True,
    )
    analisis = output["análisis"]
    informe = analisis.get("informe_completo", "")
    lecciones = output.get("nuevo_conocimiento") or []

    print("\n" + "=" * 60)
    print("  RESULTADO")
    print("=" * 60)
    print(informe[:3000])
    if len(informe) > 3000:
        print(f"\n  ... [{len(informe) - 3000} caracteres más en el KM]")

    cruce_4 = analisis.get("cruce_4", {})
    accesibilidad = cruce_4.get("accesibilidad_mercado", {})
    if accesibilidad:
        print(f"\n  Densidad de valor del producto: {accesibilidad.get('densidad_valor_producto', '?')}")
        print(f"  Alcance geográfico recomendado: {accesibilidad.get('alcance_geografico_recomendado', '?')}")

    sustitucion = analisis.get("sustitucion_importacion", {})
    if sustitucion.get("es_sustitucion"):
        print(f"\n  ⚠️  SUSTITUCIÓN DE IMPORTACIÓN detectada: {sustitucion.get('justificacion', '')}")

    gaps = analisis.get("gaps_prioritarios", [])
    if gaps:
        print(f"\n  Gaps prioritarios ({len(gaps)}):")
        for g in gaps:
            print(f"    • {g}")

    if lecciones:
        print(f"\n  Lecciones ({len(lecciones)}):")
        for l in lecciones:
            print(f"    • {l}")


if __name__ == "__main__":
    asyncio.run(main())
