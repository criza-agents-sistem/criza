"""
Runner del Agente Financiero — CRIZA (Etapa 21, 2026-09-07).

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

    spec = get_registry()["financiero"]
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

    van = analisis.get("van", {})
    tir = analisis.get("tir", {})
    payback = analisis.get("payback", {})
    tasa = analisis.get("tasa_descuento", {})
    if van:
        print(f"\n  VAN: {van.get('valor', '?')} {van.get('moneda', '')} ({van.get('estado', '?')})")
    if tir:
        print(f"  TIR: {tir.get('valor_pct', '?')}% ({tir.get('estado', '?')})")
    if payback:
        print(f"  Payback: {payback.get('años', '?')} años ({payback.get('estado', '?')})")
    if tasa:
        print(f"  Tasa de descuento: {tasa.get('valor_pct', '?')}% — fuente: {tasa.get('fuente_bcra', '?')}")

    riesgo_cambiario = analisis.get("riesgo_cambiario", {})
    if riesgo_cambiario.get("aplica"):
        print(f"\n  ⚠️  RIESGO CAMBIARIO: {riesgo_cambiario.get('descripcion', '')}")

    pedidos = analisis.get("informacion_faltante_pedida", [])
    if pedidos:
        print(f"\n  Información pedida ({len(pedidos)}):")
        for p in pedidos:
            print(f"    • {p.get('descripcion', '')}")

    if lecciones:
        print(f"\n  Lecciones ({len(lecciones)}):")
        for l in lecciones:
            print(f"    • {l}")


if __name__ == "__main__":
    asyncio.run(main())
