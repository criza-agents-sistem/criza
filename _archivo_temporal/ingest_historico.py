"""
Ingesta masiva de outputs históricos y aprendizajes al Knowledge Module.

Corre desde: criza/
    python ingest_historico.py

Ingesta:
1. Corridas con metodología del 2026-06-08 (outputs del agente divergente)
2. Aprendizajes de knowledge_base_ligera.md
"""

import asyncio
import sys
from pathlib import Path

# Fix encoding en Windows (cp1252 no soporta caracteres Unicode)
if sys.stdout.encoding != "utf-8":
    sys.stdout = open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1)

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env", override=True)

from ingest_corrida import km_ingest
from km_tools.store import store_learning


# ── 1. Corridas históricas ───────────────────────────────────────────────────

# Mapa: filename_fragment → sector legible
CORRIDAS_HISTORICAS = [
    {
        "file": "test_metodologia_ganaderia_2026-06-08.md",
        "sector": "ganadería de Córdoba, Argentina",
        "notas": "corrida test metodología v1 — ganadería (run 1)",
    },
    {
        "file": "test_metodologia_ganadería_bovina__feedlot_y_ta_2026-06-08.md",
        "sector": "ganadería bovina — feedlot y tambos, Córdoba, Argentina",
        "notas": "corrida test metodología v1 — ganadería bovina feedlot (run 1)",
    },
    {
        "file": "test_metodologia_ganadería_bovina__feedlot_y_ta_2026-06-08_1.md",
        "sector": "ganadería bovina — feedlot y tambos, Córdoba, Argentina",
        "notas": "corrida test metodología v1 — ganadería bovina feedlot (run 2)",
    },
    {
        "file": "test_metodologia_avicultura__producción_de_poll_2026-06-08.md",
        "sector": "avicultura — producción de pollos parrilleros, Argentina",
        "notas": "corrida test metodología v1 — avicultura (run 1)",
    },
    {
        "file": "test_metodologia_avicultura__producción_de_poll_2026-06-08_1.md",
        "sector": "avicultura — producción de pollos parrilleros, Argentina",
        "notas": "corrida test metodología v1 — avicultura (run 2)",
    },
    {
        "file": "test_metodologia_avicultura__producción_de_poll_2026-06-08_2.md",
        "sector": "avicultura — producción de pollos parrilleros, Argentina",
        "notas": "corrida test metodología v1 — avicultura (run 3)",
    },
    {
        "file": "test_metodologia_porcicultura__producción_de_ce_2026-06-08.md",
        "sector": "porcicultura — producción de cerdos, Argentina",
        "notas": "corrida test metodología v1 — porcicultura (run 1)",
    },
    {
        "file": "test_metodologia_porcicultura__producción_de_ce_2026-06-08_1.md",
        "sector": "porcicultura — producción de cerdos, Argentina",
        "notas": "corrida test metodología v1 — porcicultura (run 2)",
    },
    {
        "file": "test_metodologia_porcicultura__producción_de_ce_2026-06-08_2.md",
        "sector": "porcicultura — producción de cerdos, Argentina",
        "notas": "corrida test metodología v1 — porcicultura (run 3)",
    },
]

OUTPUTS_DIR = Path(__file__).parent / "divergent_agent" / "outputs"


# ── 2. Aprendizajes de knowledge_base_ligera.md ──────────────────────────────

APRENDIZAJES = [
    # Sesgos documentados
    {
        "contenido": "El agente tiende a proponer candidatos donde la solución es un producto importado ligeramente modificado (sesgo data-first). Trigger: buscar en mercados de importación sin ancla demand-first. Fix: obligar a partir del dolor del productor, no del dato de comercio exterior.",
        "tipo": "sesgo",
        "nivel_confianza": 0.9,
        "origen_nombre": "knowledge_base_ligera.md",
    },
    {
        "contenido": "El agente repite tecnologías que conoce bien (probióticos, EM, enzimas) aunque el pain del productor no las justifique (sesgo tecnología-push). Fix: agregar criterio explícito de demand-pull antes de proponer tecnología.",
        "tipo": "sesgo",
        "nivel_confianza": 0.85,
        "origen_nombre": "knowledge_base_ligera.md",
    },
    {
        "contenido": "El agente le da más peso a mercados con datos ricos en OpenAlex que a dolores reales del productor (sesgo data-first). Fix: priorizar entrevistas y observaciones de campo sobre datos bibliométricos en la fase divergente.",
        "tipo": "sesgo",
        "nivel_confianza": 0.85,
        "origen_nombre": "knowledge_base_ligera.md",
    },
    {
        "contenido": "El agente tiende a proponer candidatos que sustituyen importaciones (sesgo sustitución-importación). Estos tienen mercado obvio pero no crean océano azul. Fix: must #12 — exigir valor diferencial más allá de la sustitución.",
        "tipo": "sesgo",
        "nivel_confianza": 0.9,
        "origen_nombre": "knowledge_base_ligera.md",
    },
    {
        "contenido": "El agente sobre-califica candidatos con mucha literatura científica aunque el contexto productivo argentino no los soporte (sesgo literature-rich). Fix: separar validación científica de validación de mercado local; exigir ambas.",
        "tipo": "sesgo",
        "nivel_confianza": 0.8,
        "origen_nombre": "knowledge_base_ligera.md",
    },
    # Decisiones metodológicas
    {
        "contenido": "La búsqueda de oportunidades debe ser demand-first (pain del productor → tecnología), no supply-first (qué podemos producir → a quién vendemos). El orden importa: partir del dolor evita el sesgo tecnología-push.",
        "tipo": "decision_metodologica",
        "nivel_confianza": 0.95,
        "origen_nombre": "knowledge_base_ligera.md",
    },
    {
        "contenido": "Los 12 musts del Blue Ocean son filtros de corte, no puntajes. Un candidato que no cumple un must se descarta, no se penaliza. Must #12: cepa/solución local con valor diferencial más allá de sustitución de importación.",
        "tipo": "decision_metodologica",
        "nivel_confianza": 0.95,
        "origen_nombre": "knowledge_base_ligera.md",
    },
    {
        "contenido": "El análisis de riesgos debe incluir una categoría explícita de riesgo ecológico para candidatos que involucren organismos vivos (bacteria, hongo, insecto u otro) que se liberen al ambiente, se apliquen en superficies expuestas, o puedan persistir y reproducirse fuera de un sistema controlado. Si el organismo está contenido (ingerido, encerrado en sustrato), esta categoría no aplica.",
        "tipo": "decision_metodologica",
        "nivel_confianza": 0.9,
        "origen_nombre": "knowledge_base_ligera.md",
    },
    {
        "contenido": "COMTRADE no debe usarse en la fase divergente (búsqueda de oportunidades). Su uso introduce sesgo data-first. Sí puede usarse en la fase convergente (validación de tamaño de mercado, una vez identificada la oportunidad).",
        "tipo": "decision_metodologica",
        "nivel_confianza": 0.9,
        "origen_nombre": "knowledge_base_ligera.md",
    },
    {
        "contenido": "El agente divergente trabaja por sector (ganadería, avicultura, porcicultura), no por tecnología. Esto evita el sesgo tecnología-push y permite mapear el espacio completo de dolores antes de proponer soluciones.",
        "tipo": "decision_metodologica",
        "nivel_confianza": 0.9,
        "origen_nombre": "knowledge_base_ligera.md",
    },
    {
        "contenido": "Correr múltiples veces el agente divergente sobre el mismo sector y hacer unión de candidatos antes de pasar al convergente. La repetición revela señales robustas (candidatos que aparecen en múltiples corridas) y reduce el ruido de una corrida individual.",
        "tipo": "decision_metodologica",
        "nivel_confianza": 0.85,
        "origen_nombre": "knowledge_base_ligera.md",
    },
]


# ── Runner ───────────────────────────────────────────────────────────────────

def ingest_corridas():
    print("\n" + "="*60)
    print("INGESTA MASIVA — Corridas históricas")
    print("="*60)

    total_ok = 0
    total_err = 0

    for entry in CORRIDAS_HISTORICAS:
        fp = OUTPUTS_DIR / entry["file"]
        if not fp.exists():
            print(f"\n  ⚠ Archivo no encontrado: {fp.name} — salteando")
            total_err += 1
            continue

        print(f"\n📄 {fp.name}")
        output_text = fp.read_text(encoding="utf-8")

        try:
            result = km_ingest(
                sector=entry["sector"],
                agente="divergente",
                modo="A",
                fecha="2026-06-08",
                modelo="claude-sonnet-4-6",
                output_text=output_text,
                notas=entry.get("notas"),
                verbose=True,
            )
            print(f"  ✅ Corrida: {result.get('corrida_id', '?')} | "
                  f"Oportunidades: {result.get('oportunidades_guardadas', 0)}/"
                  f"{result.get('oportunidades_total', 0)}")
            total_ok += 1
        except Exception as e:
            print(f"  ❌ Error: {e}")
            total_err += 1

    print(f"\n{'='*60}")
    print(f"Corridas: {total_ok} ok / {total_err} errores")


async def _ingest_learnings_async():
    print("\n" + "="*60)
    print("INGESTA MASIVA — Aprendizajes de knowledge_base_ligera.md")
    print("="*60)

    ok = 0
    for ap in APRENDIZAJES:
        # Mapeo de tipos al enum del schema:
        # sesgo → patron_error | decision_metodologica → senal_decision
        tipo_mapped = {
            "sesgo": "patron_error",
            "decision_metodologica": "senal_decision",
        }.get(ap["tipo"], ap["tipo"])

        result = await store_learning(
            contenido=ap["contenido"],
            tipo=tipo_mapped,
            fuente="agente_destilacion",   # destilación del equipo; origen real en origen_nombre
            nivel_confianza=ap["nivel_confianza"],
            origen_nombre=ap.get("origen_nombre"),
        )
        if result["success"]:
            action = result["data"].get("action", "?")
            snippet = ap["contenido"][:70]
            print(f"  [{action}] {snippet}...")
            ok += 1
        else:
            snippet = ap["contenido"][:60]
            print(f"  [ERROR] {snippet}... -> {result.get('error', '?')}")

    print(f"\nAprendizajes: {ok}/{len(APRENDIZAJES)} guardados")


def ingest_learnings():
    asyncio.run(_ingest_learnings_async())


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    if mode in ("corridas", "all"):
        ingest_corridas()

    if mode in ("learnings", "all"):
        ingest_learnings()

    print("\n✅ Ingesta histórica completada.")
