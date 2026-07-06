"""
Agent Registry — CRIZA (Capa 2)

Conecta nombres de agentes (usados en los flows YAML) con sus funciones `run()`.
Lazy imports — no carga ningún agente hasta que se necesita.
"""

import sys
from pathlib import Path

_CRIZA_DIR = Path(__file__).parent.parent
_KM_PATH = _CRIZA_DIR.parent / "knowledge_module"

_REGISTRY: dict | None = None


def _build_registry() -> dict:
    for p in [str(_KM_PATH), str(_CRIZA_DIR)]:
        if p not in sys.path:
            sys.path.insert(0, p)

    # Cada agente tiene su propio tools.py / tools/ local con el mismo nombre.
    # Limpiar sys.modules["tools"] antes de cada import evita que el tools/ del
    # agente anterior sea re-usado por el siguiente (colisión de caché).
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
