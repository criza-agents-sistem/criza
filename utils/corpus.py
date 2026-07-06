"""
Búsqueda semántica en el corpus científico local (CONICET + INTA vía el motor nuevo).
Capa 2 — CRIZA, compartido entre agentes. Wraps motor_api.buscar(area='corpus_cientifico').
Requiere que el área corpus_cientifico esté cargada en el KM (SEB-150).

Antes vivía en market_agent/tools/corpus.py — movido acá porque evidence_generalista
también lo necesita (ver gap: cero tools tocaban CONICET, 2026-07-02) y un agente
importando del paquete privado de tools/ de otro agente rompe la separación entre agentes.
"""

import sys
from pathlib import Path

_KM_PATH = Path(__file__).parent.parent.parent / "knowledge_module"
sys.path.insert(0, str(_KM_PATH))

from motor import api as motor_api


async def buscar_corpus_cientifico(consulta: str, limit: int = 100) -> dict:
    """
    Busca en el corpus científico local (CONICET + INTA).

    Args:
        consulta: Términos a buscar — problema, solución o sector.
        limit: Máximo de papers (default 100 — mismo techo que investigacion_amplia usa para
               el mismo corpus vía search_corpus_cientifico; limit=5 anterior era una muestra
               demasiado chica sin justificación, ver orchestration-layer.md Decisión 6).

    Returns:
        dict con success, papers [{titulo, abstract, autores, anio, url, repositorio, similitud}],
        total, source.
    """
    resultados = await motor_api.buscar(
        area="corpus_cientifico",
        consulta=consulta,
        tipo="fuente",
        limit=limit,
        tenant="criza",
    )

    papers = []
    for r in resultados:
        props = r.get("props", {})
        papers.append({
            "titulo": props.get("titulo", ""),
            "abstract": (props.get("abstract", "") or "")[:500],
            "autores": props.get("autores", ""),
            "anio": props.get("anio", ""),
            "url": props.get("url", ""),
            "repositorio": props.get("repositorio", ""),
            "similitud": r.get("similitud", 0),
        })

    return {
        "success": True,
        "consulta": consulta,
        "total": len(papers),
        "papers": papers,
        "source": "corpus_cientifico local (CONICET/INTA)",
    }
