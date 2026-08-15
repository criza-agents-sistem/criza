"""
Generador de agents.md — CRIZA

Regenera las secciones de agents.md que antes eran prosa a mano y se desactualizaban
(PROPUESTA_CONDUCTOR.md §4.3, decisión 2026-08-15, ver docs/progress/2026-08-15.md):

- "Agentes activos": lee orquestador/agents_registry.yaml (fuente real de qué agentes existen)
  + corre su suite de tests de verdad (no --collect-only: correr los tests es la única forma de
  saber si de verdad pasan) + busca las decisiones vigentes de ese componente en el KM.
- "Estado operativo": todas las decisiones vigentes que NO son de un agente específico (las
  bloqueadores estructurales de antes). Una decisión superada simplemente deja de aparecer acá
  — sigue en el KM para historial, pero no bloatea el archivo.
- "Knowledge Module — estado rápido": decisiones vigentes con componente="knowledge_module".

Reemplaza SOLO el contenido entre marcadores <!-- GENERADO:...:INICIO/FIN --> en agents.md.
Todo lo demás (encabezado, "Qué es CRIZA", convenciones, REGLAS OPERATIVAS) queda intacto —
no es prosa que se desactualice, son reglas/identidad que no cambian con cada decisión técnica.

Uso:
    python scripts/generar_agents_md.py           # regenera agents.md real
    python scripts/generar_agents_md.py --dry-run  # imprime, no escribe
"""

import re
import subprocess
import sys
from pathlib import Path

import yaml

_CRIZA_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(_CRIZA_DIR))

from scripts.km_decisiones import listar_decisiones_vigentes

_AGENTS_MD = _CRIZA_DIR / "agents.md"
_REGISTRY_YAML = _CRIZA_DIR / "orquestador" / "agents_registry.yaml"

_NOMBRE_DISPLAY = {
    "mercado": "Mercado",
    "evidencia": "Evidence Generalista",
    "investigacion_amplia": "Investigación Amplia",
    "armador": "Armador",
    "cientifico_especialista": "Especialista Proteínas",
}

_MODULO_DIR = {
    "mercado": "market_agent",
    "evidencia": "evidence_generalista",
    "investigacion_amplia": "investigacion_amplia",
    "armador": "armador",
    "cientifico_especialista": "scientific_agent",
}


def _correr_tests(carpeta: str) -> str:
    """Corre la suite real (no --collect-only) y devuelve un resumen corto tipo '31/31 ✅'."""
    tests_dir = _CRIZA_DIR / carpeta / "tests"
    if not tests_dir.exists():
        return "sin tests/"
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pytest", str(tests_dir), "-m", "not integration", "-q", "--tb=no"],
            cwd=_CRIZA_DIR, capture_output=True, text=True, timeout=120,
        )
    except subprocess.TimeoutExpired:
        return "timeout corriendo tests"

    m = re.search(r"(\d+) passed(?:, (\d+) failed)?(?:, (\d+) deselected)?", r.stdout)
    if not m:
        m_fail = re.search(r"(\d+) failed", r.stdout)
        if m_fail:
            return f"❌ {m_fail.group(1)} fallando"
        return "sin tests unit (todos integration/deselected)"
    passed, failed, deselected = m.groups()
    passed = int(passed)
    total = passed + int(failed or 0)
    icono = "✅" if not failed else "❌"
    extra = f" (+{deselected} integration)" if deselected else ""
    return f"{passed}/{total} {icono}{extra}"


def _design_gate_estado(carpeta: str) -> str:
    gate = _CRIZA_DIR / carpeta / "docs" / "DESIGN_GATE.md"
    return "DESIGN_GATE.md ✅" if gate.exists() else "sin DESIGN_GATE.md"


def _fmt_decision(d: dict) -> str:
    alt = "; ".join(d.get("alternativas_consideradas") or []) or "—"
    return (
        f"- [ ] **{d.get('titulo', 'sin título')}** ({d.get('fecha', '?')}, {d.get('quien', '?')}). "
        f"{d.get('decision', '')} **Motivo:** {d.get('motivo', '')} "
        f"**Alternativas consideradas:** {alt}"
    )


async def generar_secciones() -> dict[str, str]:
    registry_cfg = yaml.safe_load(_REGISTRY_YAML.read_text(encoding="utf-8"))
    agentes = registry_cfg["agentes"]

    # ── Agentes activos ─────────────────────────────────────────────────
    filas = ["| Agente | Módulo | Tests | Registrado | Última decisión |", "|---|---|---|---|---|"]
    for a in agentes:
        nombre = a["nombre"]
        carpeta = _MODULO_DIR.get(nombre, nombre)
        display = _NOMBRE_DISPLAY.get(nombre, nombre)
        tests = _correr_tests(carpeta)
        gate = _design_gate_estado(carpeta)
        activo = "✅ activo" if a.get("activo") else "🟡 registrado, inactivo"
        decisiones = await listar_decisiones_vigentes(componente=carpeta)
        if not decisiones:
            decisiones = await listar_decisiones_vigentes(componente=nombre)
        ultima = decisiones[0] if decisiones else None
        ultima_txt = f"[{ultima['fecha']}] {ultima['titulo']}" if ultima else "—"
        filas.append(
            f"| {display} | `{carpeta}/` | {tests} | {activo}, {gate} | {ultima_txt} |"
        )
    seccion_agentes = "\n".join(filas)

    # ── Estado operativo (decisiones vigentes que no son de un agente) ──
    componentes_agentes = {_MODULO_DIR.get(a["nombre"], a["nombre"]) for a in agentes} | {
        a["nombre"] for a in agentes
    }
    todas = await listar_decisiones_vigentes()
    generales = [d for d in todas if d.get("componente") not in componentes_agentes
                 and d.get("componente") != "knowledge_module"]
    seccion_estado = "\n".join(_fmt_decision(d) for d in generales) if generales else (
        "*(sin decisiones vigentes fuera de agentes/KM — ver Linear para tareas operativas)*"
    )

    # ── Knowledge Module — estado rápido ────────────────────────────────
    km_decisiones = await listar_decisiones_vigentes(componente="knowledge_module")
    seccion_km = "\n".join(_fmt_decision(d) for d in km_decisiones) if km_decisiones else (
        "*(sin decisiones vigentes registradas para knowledge_module todavía)*"
    )

    return {
        "AGENTES_ACTIVOS": seccion_agentes,
        "ESTADO_OPERATIVO": seccion_estado,
        "KM_ESTADO": seccion_km,
    }


def _reemplazar_marcador(contenido: str, clave: str, nuevo_texto: str) -> str:
    patron = re.compile(
        rf"(<!-- GENERADO:{clave}:INICIO -->\n).*?(\n<!-- GENERADO:{clave}:FIN -->)",
        re.DOTALL,
    )
    if not patron.search(contenido):
        raise ValueError(f"No se encontró el marcador GENERADO:{clave} en agents.md")
    return patron.sub(lambda m: m.group(1) + nuevo_texto + m.group(2), contenido)


_MARCADORES_ACTIVOS = {"AGENTES_ACTIVOS", "ESTADO_OPERATIVO"}
# KM_ESTADO se calcula (generar_secciones ya lo arma) pero agents.md todavía no tiene su marcador
# — la tabla "Knowledge Module - estado rápido" es un inventario de capacidades estables, no
# decisiones pendientes, y forzar sus ~14 filas históricas al formato de decisión sería
# fuerza-encajar el contenido en la forma equivocada (decisión 2026-08-15). Queda listo para
# cuando haga falta: agregar el marcador a agents.md y sumar "KM_ESTADO" acá.


async def main(dry_run: bool = False) -> None:
    secciones = await generar_secciones()
    contenido = _AGENTS_MD.read_text(encoding="utf-8")
    for clave, texto in secciones.items():
        if clave not in _MARCADORES_ACTIVOS:
            continue
        contenido = _reemplazar_marcador(contenido, clave, texto)

    if dry_run:
        print(contenido)
        return

    _AGENTS_MD.write_text(contenido, encoding="utf-8")
    print(f"agents.md regenerado — {sum(len(s.splitlines()) for s in secciones.values())} líneas generadas.")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main(dry_run="--dry-run" in sys.argv))
