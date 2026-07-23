"""
run_sector.py — Runner interactivo para pipeline_sector.yaml (Motor v2).

Dos fases separadas por el gate humano:

    Fase 1: corre investigacion_amplia → muestra mapa de candidatos → guarda gate_data.json
    Fase 2: retoma desde gate_data.json con el candidato elegido → corre hasta el expediente

Uso:
    python criza/orquestador/run_sector.py fase1
    python criza/orquestador/run_sector.py fase2 "nombre del candidato elegido"

Sector hardcodeado: ganadería bovina (SEB-204).
"""

import asyncio
import json
import sys
from pathlib import Path

# ── Path setup (mismo orden que conftest.py del motor) ────────────────────────
_ORCH_DIR = Path(__file__).parent
_CRIZA_DIR = _ORCH_DIR.parent
# Transicional: mientras CRIZA siga en el árbol de EMPRESAS-IA, la conexión al KM (DATABASE_URL)
# vive en knowledge_module/.env — cuando CRIZA salga del árbol tendrá su propio .env.
_KM_ENV = _CRIZA_DIR.parent / "knowledge_module" / ".env"

sys.path.insert(0, str(_CRIZA_DIR))  # criza/ — para orquestador.motor, utils.xxx, km_tools, etc.

from dotenv import load_dotenv
load_dotenv(_KM_ENV)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from knowledge_module.db import reset_engine
from orquestador.motor import ejecutar_flow, reanudar
from orquestador.registry import get_registry

SECTOR = "ganadería bovina"
GATE_DATA_PATH = _ORCH_DIR / "gate_data.json"
TENANT = "criza"


def _print_candidatos(agent_output: dict) -> None:
    recomendaciones = agent_output.get("recomendaciones") or []
    if not recomendaciones:
        análisis = agent_output.get("análisis", {})
        recomendaciones = análisis.get("resultado", {}).get("mapa_candidatos", [])

    if not recomendaciones:
        print("(sin mapa de candidatos en el output)")
        return

    print(f"\n{'─'*60}")
    print(f"  CANDIDATOS — {len(recomendaciones)} identificados (orden por prioridad)")
    print(f"{'─'*60}")
    for i, c in enumerate(recomendaciones, 1):
        nombre = c.get("candidato", "?")
        prioridad = c.get("prioridad", "?").upper()
        demanda = c.get("señal_demanda", "")
        competencia = c.get("intensidad_competencia", "?")
        estado = c.get("estado", "?")

        print(f"\n  {i}. [{prioridad}] {nombre}")
        if demanda:
            print(f"     Demanda : {demanda[:150]}")
        print(f"     Competencia: {competencia} | Estado: {estado}")

    print(f"\n{'─'*60}")


async def fase1() -> None:
    print(f"\n{'='*60}")
    print(f"  SEB-204 — PIPELINE SECTOR: {SECTOR.upper()}")
    print(f"  Fase 1: Investigación Amplia")
    print(f"{'='*60}")

    registry = get_registry()
    result = await ejecutar_flow(
        flow_name="pipeline_sector",
        entry={"sector": SECTOR},
        tenant=TENANT,
        registry=registry,
        verbose=True,
    )

    if result.status in ("error", "stop"):
        print(f"\n❌ Pipeline detenido: {result.error}")
        return

    if result.status == "completo":
        print("\n(pipeline completado sin gate — inesperado)")
        if result.expediente_markdown:
            print(result.expediente_markdown)
        return

    # status == "gate_humano"
    with open(GATE_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(result.gate_data, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n✅  Gate alcanzado.")
    print(f"    oportunidad_id : {result.oportunidad_id}")
    print(f"    gate_data      : {GATE_DATA_PATH}")

    _print_candidatos(result.gate_data.get("agent_output", {}))

    print("\nPróximo paso:")
    print(f'    python criza/orquestador/run_sector.py fase2 "nombre del candidato"')


async def fase2(candidato: str) -> None:
    if not GATE_DATA_PATH.exists():
        print(f"❌ No hay gate_data.json en {GATE_DATA_PATH}")
        print("   Corré primero: python criza/orquestador/run_sector.py fase1")
        return

    with open(GATE_DATA_PATH, encoding="utf-8") as f:
        gate_data = json.load(f)

    print(f"\n{'='*60}")
    print(f"  SEB-204 — PIPELINE SECTOR: {SECTOR.upper()}")
    print(f"  Fase 2: Market → Evidence → Armador")
    print(f"  Candidato elegido: {candidato}")
    print(f"{'='*60}")

    registry = get_registry()
    result = await reanudar(
        gate_data=gate_data,
        gate_response={"candidato_elegido": candidato},
        tenant=TENANT,
        registry=registry,
        verbose=True,
    )

    if result.status == "completo":
        print(f"\n{'='*60}")
        print("  EXPEDIENTE DE DECISIÓN")
        print(f"{'='*60}\n")
        if result.expediente_markdown:
            print(result.expediente_markdown)
            expediente_path = _ORCH_DIR / "expediente_ganaderia.md"
            expediente_path.write_text(result.expediente_markdown, encoding="utf-8")
            print(f"\n✅  Expediente guardado: {expediente_path}")
        else:
            print("(expediente no disponible — ver KM)")
        print(f"\noportunidad_id: {result.oportunidad_id}")
    else:
        print(f"\nEstado final: {result.status}")
        if result.error:
            print(f"Error: {result.error}")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    reset_engine()

    args = sys.argv[1:]
    if not args or args[0] not in ("fase1", "fase2"):
        print("Uso:")
        print(f"  python criza/orquestador/run_sector.py fase1")
        print(f"  python criza/orquestador/run_sector.py fase2 \"candidato elegido\"")
        sys.exit(1)

    if args[0] == "fase1":
        asyncio.run(fase1())
    else:
        if len(args) < 2:
            print("Falta el candidato. Uso:")
            print(f'  python criza/orquestador/run_sector.py fase2 "candidato elegido"')
            sys.exit(1)
        asyncio.run(fase2(args[1]))
