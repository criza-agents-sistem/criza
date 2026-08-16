"""
Motor Orquestador v2 — CRIZA

Motor dirigido por objetivo que ejecuta flujos declarados en YAML.
Cada step llama a `run(contract_input)` del agente correspondiente (SEB-115).
Pausa en gates humanos y escribe pipeline_status en el KM después de cada paso.

Ver docs/DISEÑO_MOTOR_ORQUESTADOR.md para el diseño completo (SEB-152).
"""

import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Asegurar que criza/ esté en sys.path (para "utils.xxx", "km_tools.xxx", etc. de otros agentes)
_CRIZA_DIR = Path(__file__).parent.parent
if str(_CRIZA_DIR) not in sys.path:
    sys.path.insert(0, str(_CRIZA_DIR))

from knowledge_module.motor import api as motor_api
from orquestador.invocador import invocar_agente

try:
    import yaml as _yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False


# ── Tipos de resultado ────────────────────────────────────────────────────────

@dataclass
class MotorResult:
    status: str                      # "completo" | "gate_humano" | "error" | "stop"
    oportunidad_id: str
    pipeline_status: dict = field(default_factory=dict)
    gate_data: dict | None = None    # presente si status="gate_humano"
    expediente_markdown: str | None = None  # presente si status="completo"
    error: str | None = None


@dataclass
class InspeccionStep:
    step_id: str
    agent: str
    estado: str        # "completo" | "pendiente" | "no_disponible"
    detalle: str


@dataclass
class InspeccionResult:
    """"¿Qué le falta a este caso?" — ver Design Gate §7 (Etapa 2, 2026-08-16)."""
    oportunidad_id: str
    pasos: list[InspeccionStep] = field(default_factory=list)
    completos: list[str] = field(default_factory=list)
    pendientes: list[str] = field(default_factory=list)
    no_disponibles: list[str] = field(default_factory=list)


@dataclass
class EstimacionPaso:
    step_id: str
    agent: str
    tokens_estimados: int | None
    basado_en: int      # cantidad de corridas históricas usadas para el promedio
    detalle: str


@dataclass
class EstimacionCosto:
    oportunidad_id: str
    pasos: list[EstimacionPaso] = field(default_factory=list)
    total_estimado: int | None = None  # None si falta histórico para algún paso pendiente


# ── Template resolution ────────────────────────────────────────────────────────

def _get_nested(d: Any, keys: list[str]) -> Any:
    for k in keys:
        if isinstance(d, dict):
            d = d.get(k, "")
        else:
            return ""
    return d if d is not None else ""


def _resolve(value: Any, ctx: dict) -> Any:
    """Resuelve templates {key.path} en strings. Recursivo para dicts/lists."""
    if isinstance(value, str):
        def _replace(match: re.Match) -> str:
            key = match.group(1)
            resolved = ctx.get(key, "")
            return str(resolved) if resolved != "" else match.group(0)
        return re.sub(r"\{([^}]+)\}", _replace, value)
    if isinstance(value, dict):
        return {k: _resolve(v, ctx) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve(v, ctx) for v in value]
    return value


def _build_context(entry: dict, state: dict, steps_output: dict, gate: dict) -> dict:
    """Construye el contexto plano para template resolution."""
    ctx: dict = {}
    # entry.*
    for k, v in entry.items():
        ctx[f"entry.{k}"] = v
    # state.*
    for k, v in state.items():
        ctx[f"state.{k}"] = v
    # steps.<id>.output.*  (anida recursivo)
    for step_id, out in steps_output.items():
        _flatten(out, f"steps.{step_id}.output", ctx)
    # gate.*
    for k, v in gate.items():
        ctx[f"gate.{k}"] = v
    return ctx


def _flatten(obj: Any, prefix: str, out: dict) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            _flatten(v, f"{prefix}.{k}", out)
    else:
        out[prefix] = obj


# ── Flow loader ───────────────────────────────────────────────────────────────

def load_flow(flow_path: str | Path) -> dict:
    """Carga un flow YAML desde disco."""
    path = Path(flow_path)
    if not path.exists():
        raise FileNotFoundError(f"Flow no encontrado: {path}")
    if not _HAS_YAML:
        raise ImportError("PyYAML no instalado: pip install pyyaml")
    with open(path, encoding="utf-8") as f:
        return _yaml.safe_load(f)


def _steps_index(flow: dict) -> dict[str, dict]:
    """Devuelve {step_id: step_config}."""
    return {s["id"]: s for s in flow.get("steps", [])}


def _next_step_id(step: dict, agent_output: dict, steps_index: dict) -> str | None:
    """Determina el id del próximo step según routing o next declarado."""
    # routing basado en campo del output del agente
    routing = step.get("routing")
    if routing:
        field_name = routing.get("field", "próximo_agente")
        value = agent_output.get(field_name)
        routes = routing.get("routes", {})
        if value and value in routes:
            return routes[value]
        return routes.get("_default")

    # next declarado explícito
    next_id = step.get("next")
    if next_id:
        return next_id

    # próximo en la lista del flow
    ids = list(steps_index.keys())
    current_idx = ids.index(step["id"]) if step["id"] in ids else -1
    if current_idx >= 0 and current_idx + 1 < len(ids):
        return ids[current_idx + 1]

    return None


# ── Motor ─────────────────────────────────────────────────────────────────────

async def ejecutar(
    flow: dict,
    entry: dict,
    tenant: str,
    registry: dict,
    state_inicial: dict | None = None,
    verbose: bool = False,
) -> MotorResult:
    """
    Ejecuta el flujo declarado.

    Args:
        flow:          Flow config cargado desde YAML.
        entry:         Entrada del usuario {tipo, descripcion, ...}.
        tenant:        Instancia (ej: "criza").
        registry:      {nombre_agente: AgentSpec} — ver orquestador/registry.py. La invocación
                       y la persistencia al KM las hace `invocar_agente` (orquestador/invocador.py),
                       no este loop directamente.
        state_inicial: Para reanudar desde un estado previo (recovery).
        verbose:       Logging a stdout.

    Returns:
        MotorResult con status: "completo" | "gate_humano" | "error" | "stop"
    """
    state = state_inicial or {
        "oportunidad_id": None,
        "objetivo": "",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "flow": flow.get("name"),
        "flow_version": flow.get("version", "1.0"),
    }
    steps_output: dict = state.get("_steps_output", {})
    gate_response: dict = state.get("_gate_response", {})

    steps_cfg = _steps_index(flow)
    pipeline_status: dict = state.get("_pipeline_status", {
        s: {"status": "pendiente"} for s in steps_cfg
    })

    # Determinar desde qué paso continuar
    start_from = state.get("_resume_from_step")
    skipping = start_from is not None

    step_ids = list(steps_cfg.keys())
    current_id = step_ids[0] if step_ids else None

    while current_id:
        step = steps_cfg[current_id]

        # Skip steps completados si retomamos
        if skipping:
            if current_id == start_from:
                skipping = False
            else:
                current_id = _next_step_id(step, {}, steps_cfg) or _advance(step_ids, current_id)
                continue

        if verbose:
            print(f"\n  [MOTOR] → step '{current_id}' (tipo: {step['type']})")

        # ── KM write step ────────────────────────────────────────────────────
        if step["type"] == "km_write":
            action = step.get("action")
            if action == "crear_oportunidad":
                props = {}
                for prop_key, entry_key in (step.get("props_from_entry") or {}).items():
                    props[prop_key] = entry.get(entry_key, "")

                # Objetivo resuelto con template
                obj_template = flow.get("objective_template", "")
                ctx = _build_context(entry, state, steps_output, gate_response)
                objetivo = _resolve(obj_template, ctx)

                oportunidad = await motor_api.guardar_ficha(
                    area="descubrimiento",
                    tipo="oportunidad",
                    campos={
                        "nombre": props.get("nombre", "Sin nombre"),
                        "descripcion": props.get("descripcion", ""),
                    },
                    tenant=tenant,
                )
                state["oportunidad_id"] = oportunidad["id"]
                state["objetivo"] = objetivo

                if verbose:
                    print(f"  [MOTOR] oportunidad creada: {state['oportunidad_id']}")

            pipeline_status[current_id] = {
                "status": "completo",
                "ended_at": datetime.now(timezone.utc).isoformat(),
            }

        # ── Agent step ───────────────────────────────────────────────────────
        elif step["type"] == "agent":
            agent_name = step["agent"]
            spec = registry.get(agent_name)

            if spec is None or spec.run_fn is None:
                msg = f"Agente '{agent_name}' no disponible (stub o no registrado)"
                if verbose:
                    print(f"  [MOTOR] SKIP: {msg}")
                pipeline_status[current_id] = {"status": "skipped", "reason": msg}
                # Avanzar al next explícito o al default
                current_id = _next_step_id(step, {}, steps_cfg) or _advance(step_ids, current_id)
                continue

            # Resolver contract_input con contexto actual
            ctx = _build_context(entry, state, steps_output, gate_response)
            raw_input = step.get("contract_input", {})
            contract_input = _resolve(raw_input, ctx)

            try:
                pipeline_status[current_id] = {
                    "status": "corriendo",
                    "started_at": datetime.now(timezone.utc).isoformat(),
                }
                await _write_status(state, pipeline_status, tenant)

                # La persistencia al KM ya no es responsabilidad del agente — la costura
                # (invocar_agente) la hace siempre, sin excepción (PROPUESTA_CONDUCTOR.md §4.2).
                agent_output = await invocar_agente(
                    spec=spec,
                    contract_input=contract_input,
                    tenant=tenant,
                    oportunidad_id=state.get("oportunidad_id"),
                    verbose=verbose,
                )
                steps_output[current_id] = agent_output

                pipeline_status[current_id] = {
                    "status": "completo",
                    "ended_at": datetime.now(timezone.utc).isoformat(),
                    "nivel_confianza": agent_output.get("nivel_confianza"),
                    "próximo_agente": agent_output.get("próximo_agente"),
                }

                if verbose:
                    print(
                        f"  [MOTOR] '{current_id}' completado — "
                        f"confianza={agent_output.get('nivel_confianza')} "
                        f"próximo={agent_output.get('próximo_agente')}"
                    )

                # Gate humano post-step
                gate_cfg = step.get("gate_humano")
                if gate_cfg:
                    await _write_status(
                        state,
                        pipeline_status,
                        tenant,
                        current_step=current_id,
                        gate_cfg=gate_cfg,
                        agent_output=agent_output,
                    )
                    return MotorResult(
                        status="gate_humano",
                        oportunidad_id=state["oportunidad_id"],
                        pipeline_status=pipeline_status,
                        gate_data={
                            "step_id": current_id,
                            "mensaje": gate_cfg.get("mensaje", ""),
                            "espera_campo": gate_cfg.get("espera_campo"),
                            "agent_output": agent_output,
                            "_state": {**state, "_steps_output": steps_output, "_pipeline_status": pipeline_status},
                        },
                    )

            except Exception as exc:
                on_error = step.get("on_error", "stop")
                pipeline_status[current_id] = {
                    "status": "error",
                    "error": str(exc),
                    "ended_at": datetime.now(timezone.utc).isoformat(),
                }
                if verbose:
                    print(f"  [MOTOR] ERROR en '{current_id}': {exc}")

                if on_error == "stop":
                    await _write_status(state, pipeline_status, tenant)
                    return MotorResult(
                        status="stop",
                        oportunidad_id=state.get("oportunidad_id", ""),
                        pipeline_status=pipeline_status,
                        error=f"[{current_id}] {exc}",
                    )
                # on_error="continue" → sigue al siguiente paso

        # ── Gate humano standalone ────────────────────────────────────────────
        elif step["type"] == "gate_humano":
            gate_cfg = step
            await _write_status(
                state, pipeline_status, tenant,
                current_step=current_id,
                gate_cfg=gate_cfg,
            )
            return MotorResult(
                status="gate_humano",
                oportunidad_id=state["oportunidad_id"],
                pipeline_status=pipeline_status,
                gate_data={
                    "step_id": current_id,
                    "mensaje": gate_cfg.get("mensaje", ""),
                    "espera_campo": gate_cfg.get("espera_campo"),
                    "_state": {**state, "_steps_output": steps_output, "_pipeline_status": pipeline_status},
                },
            )

        # Escribir estado después de cada paso
        await _write_status(state, pipeline_status, tenant)

        # Avanzar al siguiente step
        agent_out = steps_output.get(current_id, {})
        next_id = _next_step_id(step, agent_out, steps_cfg)
        if next_id and next_id in steps_cfg:
            current_id = next_id
        else:
            break

    # Pipeline completo
    expediente = _extract_expediente(steps_output)
    pipeline_status["__motor__"] = {"status": "completo", "ended_at": datetime.now(timezone.utc).isoformat()}
    await _write_status(state, pipeline_status, tenant, status_global="completo")

    return MotorResult(
        status="completo",
        oportunidad_id=state.get("oportunidad_id", ""),
        pipeline_status=pipeline_status,
        expediente_markdown=expediente,
    )


async def reanudar(
    gate_data: dict,
    gate_response: dict,
    tenant: str,
    registry: dict,
    verbose: bool = False,
) -> MotorResult:
    """
    Reanuda un pipeline que estaba esperando en un gate humano.

    Args:
        gate_data:     El campo `gate_data` del MotorResult anterior (contiene _state).
        gate_response: Respuesta del humano {campo: valor}.
        tenant:        Instancia.
        registry:      Agent registry.
        verbose:       Logging.
    """
    inner_state = gate_data.get("_state", {})
    steps_output = inner_state.pop("_steps_output", {})
    pipeline_status = inner_state.pop("_pipeline_status", {})

    # El step del gate ya está completo — avanzar al siguiente
    gate_step_id = gate_data.get("step_id", "")

    # Reconstruir el flow desde el KM (pipeline_status tiene el nombre)
    flow_name = inner_state.get("flow", "")
    flows_dir = Path(__file__).parent / "flows"
    flow_path = flows_dir / f"{flow_name}.yaml"
    if not flow_path.exists():
        # Buscar por nombre sin instancia
        candidates = list(flows_dir.glob("*.yaml"))
        matched = [f for f in candidates if flow_name in f.stem]
        if matched:
            flow_path = matched[0]

    flow = load_flow(flow_path)
    steps_cfg = _steps_index(flow)

    # Marcar el paso del gate como completo
    pipeline_status[gate_step_id] = {
        "status": "completo",
        "ended_at": datetime.now(None).isoformat(),
        "gate_response": gate_response,
    }

    # Avanzar al siguiente
    gate_step = steps_cfg.get(gate_step_id, {})
    step_ids = list(steps_cfg.keys())
    next_id = _next_step_id(gate_step, {}, steps_cfg) or _advance(step_ids, gate_step_id)

    inner_state["_resume_from_step"] = next_id
    inner_state["_steps_output"] = steps_output
    inner_state["_pipeline_status"] = pipeline_status
    inner_state["_gate_response"] = gate_response  # para que {gate.*} resuelva en el next step

    # Reconstruir entry desde el estado
    entry = inner_state.pop("_entry", {})

    return await ejecutar(
        flow=flow,
        entry=entry,
        tenant=tenant,
        registry=registry,
        state_inicial=inner_state,
        verbose=verbose,
    )


# ── Primitivas de invocación (Etapa 2, 2026-08-16 — ver Design Gate §7) ────────

async def inspeccionar_caso(
    flow: dict,
    oportunidad_id: str,
    tenant: str,
    registry: dict,
) -> InspeccionResult:
    """
    "¿Qué le falta a este caso?" como consulta explícita — no ejecuta nada, solo lee el KM.

    Generaliza `armador.py::_validar_cobertura_upstream` (hardcodeado a mercado/evidencia) a
    cualquier step `type: agent` de cualquier flow: por cada uno, ¿ya existe `props[prop_key]`?
    """
    oportunidad = await motor_api.obtener(oportunidad_id, tenant=tenant)
    if not oportunidad:
        raise ValueError(f"Oportunidad {oportunidad_id} no encontrada en el KM")
    props = oportunidad.get("props") or {}

    pasos: list[InspeccionStep] = []
    for step in flow.get("steps", []):
        if step["type"] != "agent":
            continue
        agent_name = step["agent"]
        spec = registry.get(agent_name)

        if spec is None:
            pasos.append(InspeccionStep(step["id"], agent_name, "no_disponible", "agente no registrado"))
        elif spec.run_fn is None:
            pasos.append(InspeccionStep(step["id"], agent_name, "no_disponible", "agente inactivo (sin run_fn)"))
        elif props.get(spec.prop_key):
            pasos.append(InspeccionStep(step["id"], agent_name, "completo", f"props.{spec.prop_key} ya presente"))
        else:
            pasos.append(InspeccionStep(step["id"], agent_name, "pendiente", f"props.{spec.prop_key} ausente — no corrió todavía"))

    return InspeccionResult(
        oportunidad_id=oportunidad_id,
        pasos=pasos,
        completos=[p.step_id for p in pasos if p.estado == "completo"],
        pendientes=[p.step_id for p in pasos if p.estado == "pendiente"],
        no_disponibles=[p.step_id for p in pasos if p.estado == "no_disponible"],
    )


async def estimar_costo(
    flow: dict,
    oportunidad_id: str,
    tenant: str,
    registry: dict,
    muestra: int = 20,
) -> EstimacionCosto:
    """
    Estima el costo en tokens de los steps pendientes de un caso — promedia el histórico REAL
    de `props.token_usage.<agente>` de otras oportunidades (nunca un número inventado). Sin
    histórico para un agente, ese paso queda `tokens_estimados=None` (a-confirmar, no un cero
    encubierto) y el total agregado también queda `None` en vez de sumar parcial y aparentar
    una certeza que no hay.
    """
    inspeccion = await inspeccionar_caso(flow, oportunidad_id, tenant, registry)
    pendientes = {p.step_id: p.agent for p in inspeccion.pasos if p.estado == "pendiente"}

    if not pendientes:
        return EstimacionCosto(oportunidad_id=oportunidad_id, pasos=[], total_estimado=0)

    historicas = await motor_api.listar(area="descubrimiento", tipo="oportunidad", limit=muestra, tenant=tenant)

    pasos: list[EstimacionPaso] = []
    total = 0
    total_conocido = True
    for step_id, agent_name in pendientes.items():
        muestras = [
            dato["total_tokens"]
            for h in historicas
            if (dato := ((h.get("props") or {}).get("token_usage") or {}).get(agent_name)) and dato.get("total_tokens")
        ]
        if muestras:
            promedio = round(sum(muestras) / len(muestras))
            pasos.append(EstimacionPaso(step_id, agent_name, promedio, len(muestras), f"promedio de {len(muestras)} corridas históricas"))
            total += promedio
        else:
            pasos.append(EstimacionPaso(step_id, agent_name, None, 0, "sin histórico — no se puede estimar"))
            total_conocido = False

    return EstimacionCosto(
        oportunidad_id=oportunidad_id,
        pasos=pasos,
        total_estimado=total if total_conocido else None,
    )


async def reanudar_desde(
    flow: dict,
    oportunidad_id: str,
    desde_step: str,
    tenant: str,
    registry: dict,
    entry: dict | None = None,
    verbose: bool = False,
) -> MotorResult:
    """
    Reanuda un flow desde cualquier step, reconstruyendo el estado ÚNICAMENTE desde lo que ya
    está persistido en el KM (`props.pipeline_status.steps` + `props[prop_key]` por step) — a
    diferencia de `reanudar()` (que requiere el `gate_data` en memoria de un `MotorResult`
    anterior), esto funciona aunque la sesión que disparó la pausa ya no exista. Es la primitiva
    real detrás de "otra puerta de entrada, nunca un bypass" (`PROPUESTA_CONDUCTOR.md` §3.1).

    `entry` no se reconstruye del KM (no se persiste hoy — ver Design Gate §7) — si algún step
    posterior a `desde_step` necesita `{entry.*}` y no se pasa, el template queda sin resolver
    (comportamiento ya existente de `_resolve()`, no un crash).
    """
    oportunidad = await motor_api.obtener(oportunidad_id, tenant=tenant)
    if not oportunidad:
        raise ValueError(f"Oportunidad {oportunidad_id} no encontrada en el KM")
    props = oportunidad.get("props") or {}

    steps_cfg = _steps_index(flow)
    if desde_step not in steps_cfg:
        raise ValueError(f"Step '{desde_step}' no existe en el flow '{flow.get('name')}'")

    km_pipeline_status = props.get("pipeline_status") or {}
    km_steps = km_pipeline_status.get("steps") or {}

    steps_output: dict = {}
    pipeline_status: dict = {}
    for step_id, step_cfg in steps_cfg.items():
        km_step = km_steps.get(step_id)
        if not km_step or km_step.get("status") != "completo":
            continue
        pipeline_status[step_id] = km_step
        if step_cfg["type"] == "agent":
            spec = registry.get(step_cfg["agent"])
            if spec is not None:
                analisis = props.get(spec.prop_key)
                if analisis is not None:
                    steps_output[step_id] = {
                        "análisis": analisis,
                        "nivel_confianza": km_step.get("nivel_confianza"),
                        "próximo_agente": km_step.get("próximo_agente"),
                    }

    state = {
        "oportunidad_id": oportunidad_id,
        "objetivo": km_pipeline_status.get("objetivo", ""),
        "started_at": km_pipeline_status.get("started_at") or datetime.now(timezone.utc).isoformat(),
        "flow": flow.get("name"),
        "flow_version": flow.get("version", "1.0"),
        "_resume_from_step": desde_step,
        "_steps_output": steps_output,
        "_pipeline_status": pipeline_status,
    }

    return await ejecutar(
        flow=flow,
        entry=entry or {},
        tenant=tenant,
        registry=registry,
        state_inicial=state,
        verbose=verbose,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _advance(step_ids: list[str], current: str) -> str | None:
    try:
        idx = step_ids.index(current)
        return step_ids[idx + 1] if idx + 1 < len(step_ids) else None
    except ValueError:
        return None


def _extract_expediente(steps_output: dict) -> str | None:
    """Extrae el markdown del expediente del output del Armador. `informe_completo` es la
    clave estándar (ver invocador.py); `expediente`/`informe` quedan por compatibilidad con
    el shape viejo."""
    armador_out = steps_output.get("armador", {})
    análisis = armador_out.get("análisis", {})
    return (
        análisis.get("informe_completo")
        or análisis.get("expediente")
        or análisis.get("informe")
        or None
    )


async def _write_status(
    state: dict,
    pipeline_status: dict,
    tenant: str,
    current_step: str | None = None,
    gate_cfg: dict | None = None,
    agent_output: dict | None = None,
    status_global: str = "en_curso",
) -> None:
    """Escribe pipeline_status en el KM. No-throw — loguea si falla."""
    oportunidad_id = state.get("oportunidad_id")
    if not oportunidad_id:
        return
    try:
        km_status = {
            "flow": state.get("flow"),
            "flow_version": state.get("flow_version"),
            "objetivo": state.get("objetivo"),
            "started_at": state.get("started_at"),
            "status": status_global,
            "steps": pipeline_status,
        }
        if current_step:
            km_status["current_step"] = current_step
        if gate_cfg:
            km_status["gate"] = {
                "step_id": current_step,
                "mensaje": gate_cfg.get("mensaje", ""),
                "espera_campo": gate_cfg.get("espera_campo"),
            }
        await motor_api.actualizar_props(
            oportunidad_id,
            {"pipeline_status": km_status},
            tenant=tenant,
        )
    except Exception:
        pass  # No romper el pipeline por un fallo de KM write


# ── Convenience: ejecutar desde flow name ─────────────────────────────────────

async def ejecutar_flow(
    flow_name: str,
    entry: dict,
    tenant: str,
    registry: dict,
    flows_dir: str | Path | None = None,
    verbose: bool = False,
) -> MotorResult:
    """
    Carga el flow por nombre y ejecuta el pipeline.

    Args:
        flow_name: Nombre del archivo YAML sin extensión (ej: "pipeline_dolor").
        entry:     Entrada del usuario.
    """
    base = Path(flows_dir) if flows_dir else Path(__file__).parent / "flows"
    flow = load_flow(base / f"{flow_name}.yaml")
    # Guardar entry en state para que reanudar pueda recuperarla
    state = {"_entry": entry}
    return await ejecutar(
        flow=flow,
        entry=entry,
        tenant=tenant,
        registry=registry,
        state_inicial=state,
        verbose=verbose,
    )
