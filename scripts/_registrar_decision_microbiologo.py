import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="microbiologo",
        titulo="Etapa 1 del plan de construcción del nuevo sistema — Especialista Microbiólogo",
        decision=(
            "Construido microbiologo_agent/ (primer especialista de la biblioteca, "
            "docs/PROPUESTA_DESTINO.md §5), clonando el patrón de evidence_generalista.py — "
            "contrato SEB-115, 4 tools de corpus (search_literature, buscar_corpus_cientifico, "
            "search_corpus_inta, expand_agrovoc) + submit_evaluacion_tecnica (schema genérico, "
            "reusable para el próximo especialista), utils/ai_client.py, "
            "knowledge_module.preflight. SYSTEM_PROMPT sin ningún caso mencionado — verificado "
            "con test explícito (cero menciones de Helios/biogás/biodigestor/Mateo/Andrés). "
            "Registrado en orquestador/agents_registry.yaml, activo:true. No conecta con "
            "casos.yaml todavía (Etapa 4 del plan, deliberado)."
        ),
        motivo=(
            "Plan aprobado el 2026-08-16 (ver C:\\Users\\sebab\\.claude\\plans\\"
            "greedy-cooking-llama.md): construir genérico, validar con Helios primero, sin "
            "repetir el sesgo de scientific_agent/specialist_proteins.py (SYSTEM_PROMPT "
            "clavado a un caso cancelado)."
        ),
        alternativas_consideradas=[
            "Reciclar specialist_proteins.py — descartado: sus tools (ESMFold/ProteinMPNN/"
            "FoldX/UniProt) son de ingeniería de proteínas, no calzan con biología ambiental "
            "de biodigestores, y su SYSTEM_PROMPT está contaminado con el caso cancelado.",
            "Construir los 3 especialistas candidatos de una (microbiólogo + ingeniero "
            "ambiental + agrónomo) — descartado: el patrón nunca se probó fuera de 2 agentes, "
            "clonarlo 3 veces antes de validarlo una vez multiplica el riesgo.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
