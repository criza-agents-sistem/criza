"""
run_dolor.py — Runner para pipeline_dolor.yaml (Motor v2).

Una sola fase (el flow no tiene gate humano):

    crear_oportunidad → mercado → evidencia → (especialista) → armador

Uso:
    python criza/orquestador/run_dolor.py "descripción del dolor"
    python criza/orquestador/run_dolor.py "descripción del dolor" --contexto "contexto del caso"
    python criza/orquestador/run_dolor.py --caso metano

El dolor se pasa technology-agnostic: describe el problema a resolver, nunca la
tecnología que lo resolvería (CLAUDE.md principio 7b — los ejemplos anclan).
"""

import argparse
import asyncio
import re
import sys
from pathlib import Path

# ── Path setup (mismo orden que run_sector.py) ────────────────────────────────
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
from orquestador.motor import ejecutar_flow
from orquestador.registry import get_registry

TENANT = "criza"

# Casos preconfigurados — el dolor va SIN tecnología sugerida.
CASOS = {
    "metano": {
        "descripcion": (
            "Reducción de las emisiones de metano entérico en ganado bovino "
            "de carne."
        ),
        "contexto": (
            "Demanda observada en el circuito CREA (consulta de un asesor a "
            "Andrés): el tema aparece de forma recurrente en conversaciones de "
            "asesores y productores de ganado bovino para carne. Hay asesores y "
            "productores CREA interesados, algunos con conocimiento previo del "
            "tema y algunos ya probando alternativas, con disposición a "
            "vincularse a un desarrollo. Contexto productivo argentino."
        ),
    },
}


def _slug(texto: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", texto.lower())
    return s.strip("_")[:50] or "dolor"


async def correr(descripcion: str, contexto: str, nombre_salida: str) -> None:
    print(f"\n{'='*70}")
    print(f"  PIPELINE DOLOR — Motor v2")
    print(f"{'='*70}")
    print(f"  Dolor    : {descripcion}")
    if contexto:
        print(f"  Contexto : {contexto[:200]}")
    print(f"{'='*70}")

    registry = get_registry()
    result = await ejecutar_flow(
        flow_name="pipeline_dolor",
        entry={"descripcion": descripcion, "contexto": contexto},
        tenant=TENANT,
        registry=registry,
        verbose=True,
    )

    print(f"\n{'='*70}")
    print(f"  Estado final: {result.status}")
    print(f"  oportunidad_id: {result.oportunidad_id}")
    print(f"{'='*70}")

    # Resumen paso a paso — sirve igual si el pipeline se detuvo a mitad.
    for step_id, st in (result.pipeline_status or {}).items():
        estado = st.get("status", "?")
        extra = ""
        if st.get("nivel_confianza"):
            extra = f" — confianza: {st['nivel_confianza']}"
        if st.get("reason"):
            extra = f" — {st['reason']}"
        if st.get("error"):
            extra = f" — ERROR: {st['error'][:200]}"
        print(f"    {step_id:22} {estado}{extra}")

    if result.error:
        print(f"\n❌ {result.error}")

    if result.expediente_markdown:
        salida = _ORCH_DIR / f"expediente_{nombre_salida}.md"
        salida.write_text(result.expediente_markdown, encoding="utf-8")
        print(f"\n{'='*70}")
        print("  EXPEDIENTE DE DECISIÓN")
        print(f"{'='*70}\n")
        print(result.expediente_markdown)
        print(f"\n✅  Expediente guardado: {salida}")
    elif result.status == "completo":
        print("\n(pipeline completo pero sin expediente en el output — ver KM)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Runner de pipeline_dolor (Motor v2)")
    parser.add_argument("descripcion", nargs="?", help="El dolor a analizar")
    parser.add_argument("--contexto", default="", help="Contexto del caso")
    parser.add_argument("--caso", choices=sorted(CASOS), help="Caso preconfigurado")
    args = parser.parse_args()

    if args.caso:
        caso = CASOS[args.caso]
        descripcion, contexto, nombre = caso["descripcion"], caso["contexto"], args.caso
    elif args.descripcion:
        descripcion, contexto, nombre = args.descripcion, args.contexto, _slug(args.descripcion)
    else:
        parser.error("Pasá una descripción del dolor o --caso <nombre>")

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    reset_engine()
    asyncio.run(correr(descripcion, contexto, nombre))


if __name__ == "__main__":
    main()
