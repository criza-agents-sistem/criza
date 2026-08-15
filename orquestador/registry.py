"""
Agent Registry — CRIZA (Capa 2)

Data-driven: lee `orquestador/agents_registry.yaml` y hace lazy import de cada módulo listado
ahí. Sumar un agente nuevo es agregar una entrada al YAML, no editar este archivo.

Cada agente vive en su propio paquete (`market_agent/`, `armador/`, etc. — todos con
`__init__.py`), importado por su path calificado (`market_agent.market_agent`). Esto reemplaza
el mecanismo viejo (agregar cada carpeta de agente a `sys.path` e importar `tools` a secas,
con `sys.modules.pop("tools", None)` para evitar que un agente pisara el `tools/` de otro) —
ya no hace falta: no hay ningún import top-level ambiguo.
"""

import importlib
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

_CRIZA_DIR = Path(__file__).parent.parent
_REGISTRY_PATH = Path(__file__).parent / "agents_registry.yaml"


@dataclass
class AgentSpec:
    nombre: str
    modulo: str
    descripcion: str
    prop_key: str
    activo: bool
    run_fn: object | None = None  # se resuelve en _cargar_agente()


_REGISTRY: dict[str, AgentSpec] | None = None


def _cargar_agente(spec: AgentSpec) -> AgentSpec:
    """Importa el módulo del agente y resuelve su función `run()`. No falla el registro
    completo si un agente individual no se puede importar — lo deja sin run_fn (igual que un
    stub) y lo reporta, para que un import roto en un agente no tumbe a los demás."""
    if not spec.activo:
        return spec
    try:
        mod = importlib.import_module(spec.modulo)
        spec.run_fn = mod.run
    except Exception as exc:
        print(f"[registry] AVISO: no se pudo cargar '{spec.nombre}' ({spec.modulo}): {exc}")
        spec.run_fn = None
    return spec


def _build_registry() -> dict[str, AgentSpec]:
    if str(_CRIZA_DIR) not in sys.path:
        sys.path.insert(0, str(_CRIZA_DIR))

    cfg = yaml.safe_load(_REGISTRY_PATH.read_text(encoding="utf-8"))
    registry: dict[str, AgentSpec] = {}
    for entrada in cfg["agentes"]:
        spec = AgentSpec(
            nombre=entrada["nombre"],
            modulo=entrada["modulo"],
            descripcion=entrada.get("descripcion", "").strip(),
            prop_key=entrada["km"]["prop_key"],
            activo=entrada.get("activo", True),
        )
        registry[spec.nombre] = _cargar_agente(spec)
    return registry


def get_registry() -> dict[str, AgentSpec]:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _build_registry()
    return _REGISTRY


def get_run_functions() -> dict[str, object]:
    """Compatibilidad con el shape viejo ({nombre: run_fn}) para quien todavía lo espere así."""
    return {nombre: spec.run_fn for nombre, spec in get_registry().items()}
