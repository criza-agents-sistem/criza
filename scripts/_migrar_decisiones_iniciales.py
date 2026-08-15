"""
Migración única — carga las decisiones abiertas que hoy viven como prosa en agents.md
(sección "Estado operativo") al área decisiones_sistema del KM, antes de regenerar agents.md.

Los pendientes ya CERRADOS ([x] en agents.md: Fases D-G, reestructuración del KM) NO se migran
— ya cumplieron su función de avisar que algo estaba incierto, y su detalle completo sigue
íntegro en docs/progress/*.md. Migrarlos como "vigente" solo bloatearía la sección generada de
nuevo, exactamente lo que se está resolviendo hoy.

Correr una sola vez. No es parte del flujo normal (eso es scripts/km_decisiones.py).
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision

DECISIONES = [
    dict(
        componente="destino",
        titulo="Redefinición del objetivo de CRIZA: de blue-ocean-discovery a equipo asesor",
        decision=(
            "CRIZA deja de tener como propósito central 'encontrar blue oceans' — pasa a ser "
            "un equipo de agentes de IA asesores, con blue-ocean-discovery como capacidad "
            "invocable cuando el caso la amerita. Ver docs/PROPUESTA_DESTINO.md — borrador "
            "todavía sin cerrar, no reemplaza el Norte global de CLAUDE.md hasta que cierre."
        ),
        motivo=(
            "El objetivo original ya cumplió su función — de ahí salieron proyectos reales "
            "(biogás vía Andrés, MicroBigs vía Pablo) que ahora necesitan acompañamiento "
            "continuo, no un expediente de inversión único."
        ),
        alternativas_consideradas=[
            "Mantener el objetivo original y tratar estos casos como excepción",
            "Redefinir el propósito central del sistema",
        ],
        quien="Sebas",
        fecha="2026-08-14",
    ),
    dict(
        componente="orquestador",
        titulo="Registry data-driven + la costura de persistencia al KM",
        decision=(
            "orquestador/agents_registry.yaml (nuevo) reemplaza los imports hardcodeados de "
            "registry.py. orquestador/invocador.py (nuevo, 'la costura') persiste el resultado "
            "de cualquier agente al KM de forma genérica, sin que el agente tenga que "
            "acordarse. Los 4 agentes actuales se normalizaron a este contrato. Cerró dos gaps "
            "reales: Armador nunca había persistido su propio expediente, e Investigación "
            "Amplia duplicaba su informe en dos props."
        ),
        motivo=(
            "Persistir el resultado dependía de que cada agente se acordara — causa exacta del "
            "bug real del 22/07 (Mercado corrió, costó plata, y su escritura era invisible para "
            "el Motor). Sin garantía estructural, cualquier especialista nuevo podía repetir el "
            "mismo error."
        ),
        alternativas_consideradas=[
            "Seguir con imports hardcodeados y persistencia por agente",
            "Solo agregar tests que detecten el bug de nuevo, sin cambiar la arquitectura",
        ],
        quien="Sebas + Claude",
        fecha="2026-08-15",
    ),
    dict(
        componente="orquestador",
        titulo="objetivo del Motor sigue decorativo — depende del diseño del Conductor",
        decision=(
            "El campo `objetivo` que arma el Motor al crear una oportunidad se guarda como "
            "texto pero no influye en ninguna decisión de ruteo — todo el ruteo real está "
            "pre-declarado en el YAML del flow. No se resuelve todavía."
        ),
        motivo=(
            "Es la pregunta de fondo del diseño del Conductor (PROPUESTA_CONDUCTOR.md) — "
            "resolverla aislada, sin el Conductor definido, sería adivinar la forma final."
        ),
        alternativas_consideradas=[
            "Resolverlo ahora de forma aislada",
            "Esperar a diseñar el Conductor completo",
        ],
        quien="Sebas + Claude",
        fecha="2026-07-22",
    ),
    dict(
        componente="auditor",
        titulo="Auditor determinístico — 9 checks contra datos reales del KM y código fuente",
        decision=(
            "knowledge_module/auditor/ (Capa 1) + criza/auditor_registry.yaml (Capa 2, config). "
            "Verifica población de campos, cobertura de fuentes entre agentes hermanos, "
            "sampling no declarado, decisiones diferidas, contrato fuentes_y_cobertura, "
            "km_write_ausente, instancias no registradas, contrato_input_no_leido, "
            "km_conexion. 32/32 unit tests."
        ),
        motivo=(
            "Verificación determinística, no LLM, contra el código y el KM reales — para no "
            "depender de que un humano se acuerde de revisar cada conexión a mano."
        ),
        alternativas_consideradas=["Revisión manual periódica", "Verificador determinístico"],
        quien="Sebas + Claude",
        fecha="2026-07-22",
    ),
    dict(
        componente="deuda_tests",
        titulo="Deuda de tests encontrada al independizar CRIZA — sesión dedicada aparte",
        decision=(
            "km_tools/tests 6/28 verde (22 fallos) + utils/tests cuelga. Causa exacta sin "
            "confirmar (podrían ser bugs reales, tests desactualizados, o dependencia del "
            "estado real del Neon). Detalle: docs/progress/2026-08-13.md §4."
        ),
        motivo=(
            "No forzarlo al costado de otra tarea — mismo criterio que la auditoría de "
            "cumplimiento: ya se corrigió mal una vez por apurar la lectura."
        ),
        alternativas_consideradas=[
            "Arreglarlo ahora, al costado de otra tarea",
            "Sesión dedicada aparte",
        ],
        quien="Sebas",
        fecha="2026-08-13",
    ),
    dict(
        componente="infra",
        titulo="Rotar password de Neon",
        decision="Acción manual pendiente de Sebas — no es una tarea de desarrollo.",
        motivo="Buena práctica de seguridad tras la independización del repo.",
        alternativas_consideradas=[],
        quien="Sebas",
        fecha="2026-08-13",
    ),
    dict(
        componente="infra",
        titulo="Renombrar carpeta EMPRESAS-IA/ (hoy KRIZA/ en disco)",
        decision="Pendiente — requiere migración de memoria de Claude antes de renombrar.",
        motivo="El nombre de carpeta quedó desactualizado tras sucesivos cambios de naming de la plataforma.",
        alternativas_consideradas=[],
        quien="Sebas",
        fecha="2026-07-01",
    ),
    dict(
        componente="auditoria_cumplimiento",
        titulo="Auditoría de cumplimiento de plataforma — 51 hallazgos, revisión activa",
        decision=(
            "Revisión hallazgo por hallazgo en curso con Sebas. Temas 1-2 (git, docs "
            "desactualizados) y parte del Tema 3 (tenant hardcodeado) ya resueltos. Hallazgo "
            "central: el KM comparte una sola base entre instancias sin RLS (P11) — decidido "
            "volver a base separada por instancia. Detalle: "
            "EMPRESAS-IA/docs/AUDITORIA_CUMPLIMIENTO_2026-07-05.md."
        ),
        motivo=(
            "No resolver nada de esto sin Sebas — varios ítems ya se corrigieron mal una vez "
            "por apurar la lectura."
        ),
        alternativas_consideradas=[
            "Resolver todo de una vez",
            "Revisión hallazgo por hallazgo con Sebas",
        ],
        quien="Sebas",
        fecha="2026-07-05",
    ),
]


async def main():
    for d in DECISIONES:
        r = await registrar_decision(**d)
        estado = "OK" if r.get("success") else f"ERROR: {r.get('error')}"
        print(f"[{estado}] {d['componente']} — {d['titulo']}")


if __name__ == "__main__":
    asyncio.run(main())
