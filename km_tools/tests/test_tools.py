"""
Tests del Knowledge Module.
Markers: unit (sin DB), integration (con DB real de Neon).

Correr solo unit:       pytest -m unit
Correr todo:            pytest
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch


# ─────────────────────────────────────────
# UNIT TESTS — sin DB, sin embeddings reales
# ─────────────────────────────────────────

@pytest.mark.unit
def test_embedding_provider_local():
    """El embedder local devuelve un vector del tamaño configurado."""
    from knowledge_module.embeddings import LocalEmbedder
    embedder = LocalEmbedder()
    vec = embedder.embed("control de moscas en feedlot")
    assert isinstance(vec, list)
    assert len(vec) == embedder.dim
    assert all(isinstance(v, float) for v in vec)


@pytest.mark.unit
def test_embedding_batch():
    """El embedder procesa un batch correctamente."""
    from knowledge_module.embeddings import LocalEmbedder
    embedder = LocalEmbedder()
    texts = ["garrapata resistente", "hongos entomopatógenos", "biocontrol"]
    vecs = embedder.embed_batch(texts)
    assert len(vecs) == 3
    assert all(len(v) == embedder.dim for v in vecs)


@pytest.mark.unit
def test_embedding_singleton():
    """get_embedder() devuelve siempre la misma instancia."""
    from knowledge_module.embeddings import get_embedder
    a = get_embedder()
    b = get_embedder()
    assert a is b


# ─────────────────────────────────────────
# INTEGRATION TESTS — requieren DB de Neon
#
# test_store_and_search_opportunity / test_store_learning_reinforcement /
# test_store_corrida_and_link / test_get_opportunity_history (pipeline scout/agente
# divergente/convergente) se sacaron el 2026-08-15 al archivar ese subsistema — ver
# _archivo_temporal/ y docs/progress/2026-08-15.md.
# ─────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.asyncio
async def test_store_fuente_externa_create_and_dedup():
    """store_fuente_externa: primera llamada crea; segunda devuelve skipped (idempotente)."""
    from km_tools.store import store_fuente_externa

    url = "https://hdl.handle.net/TEST-store_fuente_externa-integration"

    r1 = await store_fuente_externa(
        titulo="Paper de prueba integration test",
        contenido="Abstract de prueba para verificar store_fuente_externa.",
        fuente_url=url,
        sector="Biotecnología agrícola",
        fecha="2024",
        tipo="paper",
        autores=["Autor Uno", "Autor Dos"],
        subjects=["biotecnología", "test"],
    )
    assert r1["success"], r1["error"]
    assert r1["data"]["action"] == "created"
    doc_id = r1["data"]["id"]

    # Segunda llamada — misma URL → skipped, mismo id
    r2 = await store_fuente_externa(
        titulo="Cualquier otro título",
        contenido="Cualquier otro contenido",
        fuente_url=url,
        sector="Biotecnología agrícola",
        fecha="2024",
    )
    assert r2["success"]
    assert r2["data"]["action"] == "skipped"
    assert r2["data"]["id"] == doc_id
