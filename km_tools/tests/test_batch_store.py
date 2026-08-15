"""
Tests para batch_store_fuentes_externas.

Unit tests: mock de session + pg_insert (sin DB).
Integration test: requiere DB de Neon con índice uq_documento_fuente_url.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call


def _make_record(fuente_url="https://hdl.handle.net/test/1", titulo="Título test",
                 abstract="Abstract de prueba", año="2023", sector="Biotecnología"):
    return {
        "titulo": titulo,
        "contenido": abstract,
        "fuente_url": fuente_url,
        "sector": sector,
        "fecha": año,
        "tipo": "paper",
        "autores": ["Autor A"],
        "subjects": ["biotecnología"],
    }


def _make_session_mock(fetchall_return):
    """Crea un session mock que devuelve fetchall_return de execute()."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = fetchall_return

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_factory = MagicMock(return_value=mock_session)
    return mock_factory, mock_session


def _make_pg_insert_mock():
    """Crea un mock encadenable para pg_insert(Documento).values().on_conflict_do_nothing().returning()."""
    stmt_mock = MagicMock()
    stmt_mock.values.return_value = stmt_mock
    stmt_mock.on_conflict_do_nothing.return_value = stmt_mock
    stmt_mock.returning.return_value = stmt_mock

    pg_insert_mock = MagicMock(return_value=stmt_mock)
    return pg_insert_mock, stmt_mock


# ─────────────────────────────────────────
# UNIT TESTS
# ─────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_empty_input_returns_zeros():
    """Input vacío → success con 0s sin tocar la DB."""
    from km_tools.store import batch_store_fuentes_externas
    result = await batch_store_fuentes_externas([])
    assert result["success"] is True
    assert result["data"] == {"created": 0, "skipped": 0, "errors": 0}
    assert result["error"] is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_new_records_created_count_matches_returning():
    """3 records nuevos → ON CONFLICT retorna 3 IDs → created=3, skipped=0."""
    records = [
        _make_record("https://hdl.handle.net/test/1"),
        _make_record("https://hdl.handle.net/test/2"),
        _make_record("https://hdl.handle.net/test/3"),
    ]
    # RETURNING devuelve 3 filas (los 3 insertados)
    returned_ids = [MagicMock(), MagicMock(), MagicMock()]
    mock_factory, _ = _make_session_mock(returned_ids)
    pg_insert_mock, _ = _make_pg_insert_mock()

    with patch("km_tools.store.get_session_factory", return_value=mock_factory), \
         patch("sqlalchemy.dialects.postgresql.insert", pg_insert_mock):
        from km_tools.store import batch_store_fuentes_externas
        result = await batch_store_fuentes_externas(records)

    assert result["success"] is True
    assert result["data"]["created"] == 3
    assert result["data"]["skipped"] == 0
    assert result["data"]["errors"] == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_all_conflict_returns_zero_created():
    """Todos los records ya existen → ON CONFLICT skips them → created=0, skipped=3."""
    records = [
        _make_record("https://hdl.handle.net/test/1"),
        _make_record("https://hdl.handle.net/test/2"),
        _make_record("https://hdl.handle.net/test/3"),
    ]
    # RETURNING devuelve 0 filas (todos conflictuaron)
    mock_factory, _ = _make_session_mock([])
    pg_insert_mock, _ = _make_pg_insert_mock()

    with patch("km_tools.store.get_session_factory", return_value=mock_factory), \
         patch("sqlalchemy.dialects.postgresql.insert", pg_insert_mock):
        from km_tools.store import batch_store_fuentes_externas
        result = await batch_store_fuentes_externas(records)

    assert result["success"] is True
    assert result["data"]["created"] == 0
    assert result["data"]["skipped"] == 3
    assert result["data"]["errors"] == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_intra_batch_dedup_inserts_once():
    """El mismo fuente_url aparece dos veces → solo se manda 1 row al INSERT."""
    url = "https://hdl.handle.net/test/1"
    records = [
        _make_record(url, titulo="Título A"),
        _make_record(url, titulo="Título B"),  # mismo URL
    ]
    # RETURNING devuelve 1 fila (se insertó una vez)
    mock_factory, mock_session = _make_session_mock([MagicMock()])
    pg_insert_mock, stmt_mock = _make_pg_insert_mock()

    with patch("km_tools.store.get_session_factory", return_value=mock_factory), \
         patch("sqlalchemy.dialects.postgresql.insert", pg_insert_mock):
        from km_tools.store import batch_store_fuentes_externas
        result = await batch_store_fuentes_externas(records)

    assert result["success"] is True
    # Verificar que values() recibió solo 1 row
    values_call_args = stmt_mock.values.call_args
    rows_passed = values_call_args[0][0]  # primer arg posicional = lista de rows
    assert len(rows_passed) == 1
    assert rows_passed[0]["fuente_url"] == url
    # created=1 porque RETURNING devolvió 1 ID; skipped=1 porque len(records)=2 - created=1 - errors=0
    assert result["data"]["created"] == 1
    assert result["data"]["skipped"] == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_row_with_bad_fecha_counted_as_error():
    """Record con fecha inválida → error en preparación → no va al INSERT, errors=1."""
    records = [
        _make_record("https://hdl.handle.net/test/good", año="2023"),
        _make_record("https://hdl.handle.net/test/bad", año="no-es-fecha"),
    ]
    # RETURNING devuelve 1 fila (solo el record bueno)
    mock_factory, _ = _make_session_mock([MagicMock()])
    pg_insert_mock, stmt_mock = _make_pg_insert_mock()

    with patch("km_tools.store.get_session_factory", return_value=mock_factory), \
         patch("sqlalchemy.dialects.postgresql.insert", pg_insert_mock):
        from km_tools.store import batch_store_fuentes_externas
        result = await batch_store_fuentes_externas(records)

    assert result["success"] is True
    assert result["data"]["errors"] == 1
    # Solo 1 row válido enviado al INSERT
    rows_passed = stmt_mock.values.call_args[0][0]
    assert len(rows_passed) == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_uses_on_conflict_do_nothing_with_partial_index():
    """Verifica que se llama on_conflict_do_nothing con index_elements y index_where."""
    records = [_make_record()]
    mock_factory, _ = _make_session_mock([MagicMock()])
    pg_insert_mock, stmt_mock = _make_pg_insert_mock()

    with patch("km_tools.store.get_session_factory", return_value=mock_factory), \
         patch("sqlalchemy.dialects.postgresql.insert", pg_insert_mock):
        from km_tools.store import batch_store_fuentes_externas
        await batch_store_fuentes_externas(records)

    stmt_mock.on_conflict_do_nothing.assert_called_once()
    kwargs = stmt_mock.on_conflict_do_nothing.call_args[1]
    assert kwargs.get("index_elements") == ["fuente_url"]
    assert kwargs.get("index_where") is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_db_error_returns_success_false():
    """Error de DB → success=False con mensaje de error."""
    records = [_make_record()]

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=Exception("connection refused"))
    mock_session.commit = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_factory = MagicMock(return_value=mock_session)

    pg_insert_mock, _ = _make_pg_insert_mock()

    with patch("km_tools.store.get_session_factory", return_value=mock_factory), \
         patch("sqlalchemy.dialects.postgresql.insert", pg_insert_mock):
        from km_tools.store import batch_store_fuentes_externas
        result = await batch_store_fuentes_externas(records)

    assert result["success"] is False
    assert "connection refused" in result["error"]


# ─────────────────────────────────────────
# INTEGRATION TEST — requiere DB Neon
# ─────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.asyncio
async def test_integration_batch_idempotente():
    """Insertar los mismos records dos veces → segunda vez created=0."""
    from uuid import uuid4

    from knowledge_module.db import reset_engine
    from km_tools.store import batch_store_fuentes_externas

    reset_engine()  # engine queda pegado al loop del asyncio.run() anterior si corre otro test antes

    # UUID por corrida — urls fijas hacían que la 1ra aserción (created==2) fallara en
    # corridas posteriores contra el Neon real, porque las filas ya existían de antes.
    suffix = uuid4()
    records = [
        {
            "titulo": "Test batch idempotente A",
            "contenido": "Abstract A",
            "fuente_url": f"https://hdl.handle.net/test-batch-idem/{suffix}/001",
            "sector": "Test",
            "fecha": "2024",
            "tipo": "paper",
            "autores": [],
            "subjects": [],
        },
        {
            "titulo": "Test batch idempotente B",
            "contenido": "Abstract B",
            "fuente_url": f"https://hdl.handle.net/test-batch-idem/{suffix}/002",
            "sector": "Test",
            "fecha": "2024",
        },
    ]

    r1 = await batch_store_fuentes_externas(records, tenant_id="criza")
    assert r1["success"], r1["error"]
    assert r1["data"]["created"] == 2

    # Segunda inserción: ON CONFLICT DO NOTHING → 0 creados
    r2 = await batch_store_fuentes_externas(records, tenant_id="criza")
    assert r2["success"], r2["error"]
    assert r2["data"]["created"] == 0
    assert r2["data"]["skipped"] == 2
