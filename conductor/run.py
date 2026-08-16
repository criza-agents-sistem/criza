"""
Runner del Conductor — CRIZA.

Uso:
  python run.py

REPL interactivo — a diferencia de los demás agentes (una corrida, un resultado), el Conductor
es conversacional: mantiene el historial entre mensajes hasta que escribís "salir".
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

from conductor import enviar_mensaje, cerrar_sesion, DEFAULT_MODEL
from utils.token_tracker import TokenTracker

_SALIR = {"salir", "exit", "quit", "chau"}


async def main() -> None:
    print("=" * 60)
    print("  CONDUCTOR — CRIZA")
    print(f"  Modelo: {DEFAULT_MODEL}")
    print("  Escribí 'salir' para terminar.")
    print("=" * 60)

    messages: list[dict] = []
    tracker = TokenTracker(agent="conductor", oportunidad_id="", model=DEFAULT_MODEL)

    while True:
        try:
            texto = input("\nVos: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not texto:
            continue
        if texto.lower() in _SALIR:
            break

        respuesta, messages = await enviar_mensaje(
            messages, texto, model=DEFAULT_MODEL, verbose=True, tracker=tracker
        )
        print(f"\nConductor: {respuesta}")

    tracker.log(verbose=True)

    leccion = await cerrar_sesion(messages, verbose=True)
    if leccion:
        print(f"\n[Lección nueva guardada en el KM: {leccion['id']}]")

    print("\nChau.")


if __name__ == "__main__":
    asyncio.run(main())
