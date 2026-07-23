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
# ─────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.asyncio
async def test_store_and_search_opportunity():
    """Guarda una oportunidad y la encuentra por búsqueda semántica."""
    from km_tools.store import store_opportunity
    from km_tools.search import search_knowledge

    result = await store_opportunity(
        sector="Ganadería bovina, Córdoba",
        idea="Control de moscas en feedlot con avispas parasitoides de pupa",
        prioridad="alta",
        origen="agente",
        gaps_pendientes="Confirmar con operadores si perciben el dolor",
    )
    assert result["success"], result["error"]
    op_id = result["data"]["id"]

    # Buscar por similaridad semántica
    search = await search_knowledge(
        query="control biológico de moscas en ganadería",
        tipo="oportunidades",
        limit=5,
    )
    assert search["success"]
    ids = [r["id"] for r in search["data"]["results"]]
    assert op_id in ids


@pytest.mark.integration
@pytest.mark.asyncio
async def test_store_learning_reinforcement():
    """Guardar el mismo aprendizaje dos veces refuerza el existente."""
    from km_tools.store import store_learning

    contenido = "COMTRADE actúa como zanahoria hacia sustitución de importación en el agente divergente"

    r1 = await store_learning(contenido=contenido, tipo="patron_error")
    assert r1["success"]

    r2 = await store_learning(contenido=contenido, tipo="patron_error")
    assert r2["success"]
    assert r2["data"]["action"] == "reinforced"
    assert r2["data"]["veces_confirmado"] >= 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_store_corrida_and_link():
    """Guarda una corrida y la asocia a una oportunidad."""
    from km_tools.store import store_corrida, store_opportunity

    corrida_result = await store_corrida(
        sector="Avicultura, Córdoba",
        agente="divergente",
        modo="C",
        fecha="2026-06-08",
        modelo="claude-sonnet-4-6",
        tokens_input=285134,
        tokens_output=9634,
        costo_usd=1.00,
    )
    assert corrida_result["success"]
    corrida_id = corrida_result["data"]["id"]

    op_result = await store_opportunity(
        sector="Avicultura, Córdoba",
        idea="Consorcio microbiano para tratamiento de cama aviar reutilizada",
        prioridad="alta",
        corrida_id=corrida_id,
    )
    assert op_result["success"]


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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_opportunity_history():
    """get_opportunity_history devuelve corridas asociadas."""
    from km_tools.store import store_corrida, store_opportunity
    from km_tools.retrieve import get_opportunity_history

    corrida_r = await store_corrida(
        sector="Porcicultura, Córdoba",
        agente="divergente",
        modo="C",
        fecha="2026-06-08",
        modelo="claude-sonnet-4-6",
    )
    corrida_id = corrida_r["data"]["id"]

    op_r = await store_opportunity(
        sector="Porcicultura, Córdoba",
        idea="Probiótico para reducir diarrea post-destete en lechones",
        prioridad="media",
        corrida_id=corrida_id,
    )
    op_id = op_r["data"]["id"]

    history = await get_opportunity_history(op_id)
    assert history["success"]
    assert len(history["data"]["corridas"]) >= 1
    assert history["data"]["corridas"][0]["corrida_id"] == corrida_id
