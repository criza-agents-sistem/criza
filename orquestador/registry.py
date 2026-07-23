"""
Agent Registry — CRIZA (Capa 2)

Conecta nombres de agentes (usados en los flows YAML) con sus funciones `run()`.
Lazy imports — no carga ningún agente hasta que se necesita.
"""

import sys
from pathlib import Path

_CRIZA_DIR = Path(__file__).parent.parent

_REGISTRY: dict | None = None


def _build_registry() -> dict:
    if str(_CRIZA_DIR) not in sys.path:
        sys.path.insert(0, str(_CRIZA_DIR))

    # Solo market_agent/ tiene su propio tools/ local (los demás agentes usan km_tools, el
    # tools genérico del KM, ya renombrado — no colisiona con el paquete propio de market_agent).
    # Limpiar sys.modules["tools"] antes de importarlo evita que quede cacheado el de una corrida
    # anterior en el mismo proceso.
    sys.path.insert(0, str(_CRIZA_DIR / "market_agent"))
    sys.modules.pop("tools", None)
    import market_agent as _market_mod
    _market_run = _market_mod.run

    sys.path.insert(0, str(_CRIZA_DIR / "evidence_generalista"))
    sys.modules.pop("tools", None)
    import evidence_generalista as _ev_mod
    _evidence_run = _ev_mod.run

    sys.path.insert(0, str(_CRIZA_DIR / "investigacion_amplia"))
    sys.modules.pop("tools", None)
    import investigacion_amplia as _ia_mod
    _ia_run = _ia_mod.run

    sys.path.insert(0, str(_CRIZA_DIR / "armador"))
    sys.modules.pop("tools", None)
    import armador as _arm_mod
    _armador_run = _arm_mod.run

    return {
        "mercado":               _market_run,
        "evidencia":             _evidence_run,
        "investigacion_amplia":  _ia_run,
        "armador":               _armador_run,
        "cientifico_especialista": None,  # stub — SEB-149
    }


def get_registry() -> dict:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _build_registry()
    return _REGISTRY
