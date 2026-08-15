"""
Tests para search_fuentes_externas.

Unit tests: mock de DB session.
Integration tests: requieren DB de Neon con documentos harvest.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import date


# ─────────────────────────────────────────
# UNIT TESTS
# ─────────────────────────────────────────

def _make_row(titulo="Test paper", contenido="Abstract de prueba", fuente_url="https://hdl.handle.net/test/1",
              autores=None, subjects=None, fecha=date(2023, 1, 1), tipo="paper", rank=0.1):
    row = MagicMock()
    row.id = "test-id-1"
    row.titulo = titulo
    row.contenido = contenido
    row.fuente_url = fuente_url
    row.autores = json.dumps(autores or ["Autor Uno"])
    row.subjects = json.dumps(subjects or ["biotecnología"])
    row.fecha = fecha
    row.tipo = tipo
    row.rank = rank
    return row


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retorna_resultados_con_estructura_correcta():
    """search_fuentes_externas retorna estructura estándar."""
    mock_row = _make_row()

    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_factory = MagicMock(return_value=mock_session)

    with patch("km_tools.search.get_session_factory", return_value=mock_factory):
        from km_tools.search import search_fuentes_externas
        result = await search_fuentes_externas("garrapata biocontrol")

    assert result["success"] is True
    assert result["data"]["total"] == 1
    r = result["data"]["results"][0]
    assert r["titulo"] == "Test paper"
    assert r["fuente_url"] == "https://hdl.handle.net/test/1"
    assert r["autores"] == ["Autor Uno"]
    assert r["subjects"] == ["biotecnología"]
    assert r["año"] == 2023
    assert "rank" in r


@pytest.mark.unit
@pytest.mark.asyncio
async def test_maneja_autores_json_malformado():
    """Si autores/subjects es JSON inválido, retorna lista vacía sin romper."""
    mock_row = _make_row()
    mock_row.autores = "no-es-json"
    mock_row.subjects = None

    mock_result = MagicMock()
    mock_result.fetchall.return_value = [mock_row]
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("km_tools.search.get_session_factory", return_value=MagicMock(return_value=mock_session)):
        from km_tools.search import search_fuentes_externas
        result = await search_fuentes_externas("garrapata")

    assert result["success"] is True
    r = result["data"]["results"][0]
    assert r["autores"] == []
    assert r["subjects"] == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sin_resultados_retorna_lista_vacia():
    """Query sin matches retorna total=0 y lista vacía."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("km_tools.search.get_session_factory", return_value=MagicMock(return_value=mock_session)):
        from km_tools.search import search_fuentes_externas
        result = await search_fuentes_externas("xyzzy_no_existe")

    assert result["success"] is True
    assert result["data"]["total"] == 0
    assert result["data"]["results"] == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_error_de_db_retorna_success_false():
    """Si la DB falla, retorna success=False con mensaje de error."""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=RuntimeError("DB connection error"))
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("km_tools.search.get_session_factory", return_value=MagicMock(return_value=mock_session)):
        from km_tools.search import search_fuentes_externas
        result = await search_fuentes_externas("garrapata")

    assert result["success"] is False
    assert "DB connection error" in result["error"]


# ─────────────────────────────────────────
# UNIT TESTS — get_ficha_full_text
# ─────────────────────────────────────────

def _make_ficha_row(titulo="Paper CONICET", url="https://ri.conicet.gov.ar/handle/11336/1",
                    repositorio="CONICET", texto_completo="Texto completo del paper...",
                    requiere_solicitud=False, solicitud_url=None):
    row = MagicMock()
    row.id = "ficha-uuid-1"
    row.titulo = titulo
    row.url = url
    row.repositorio = repositorio
    row.texto_completo = texto_completo
    row.requiere_solicitud = requiere_solicitud
    row.solicitud_url = solicitud_url
    return row


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_ficha_full_text_encontrada_con_texto():
    mock_result = MagicMock()
    mock_result.fetchone.return_value = _make_ficha_row()
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("km_tools.search.get_session_factory", return_value=MagicMock(return_value=mock_session)):
        from km_tools.search import get_ficha_full_text
        result = await get_ficha_full_text("ficha-uuid-1")

    assert result["success"] is True
    assert result["data"]["texto_completo"] == "Texto completo del paper..."
    assert result["data"]["repositorio"] == "CONICET"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_ficha_full_text_no_encontrada():
    mock_result = MagicMock()
    mock_result.fetchone.return_value = None
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("km_tools.search.get_session_factory", return_value=MagicMock(return_value=mock_session)):
        from km_tools.search import get_ficha_full_text
        result = await get_ficha_full_text("no-existe")

    assert result["success"] is False
    assert "no encontrada" in result["error"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_ficha_full_text_sin_texto_completo_aun():
    """Ficha existe pero el backfill de download_corpus_pdfs.py todavía no la procesó."""
    mock_result = MagicMock()
    mock_result.fetchone.return_value = _make_ficha_row(texto_completo=None)
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("km_tools.search.get_session_factory", return_value=MagicMock(return_value=mock_session)):
        from km_tools.search import get_ficha_full_text
        result = await get_ficha_full_text("ficha-uuid-1")

    assert result["success"] is False
    assert "no disponible" in result["error"].lower()
    assert result["data"]["titulo"] == "Paper CONICET"  # metadata igual disponible aunque falte el texto


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_ficha_full_text_requiere_solicitud_con_autoservicio():
    """Dataset restringido con formulario de 'Consultar' — el error debe declarar
    dónde pedirlo, no un 'no disponible' genérico (veracidad por dato)."""
    mock_result = MagicMock()
    mock_result.fetchone.return_value = _make_ficha_row(
        texto_completo=None, requiere_solicitud=True,
        solicitud_url="https://ri.conicet.gov.ar/handle/11336/269341/restricted-resource",
    )
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("km_tools.search.get_session_factory", return_value=MagicMock(return_value=mock_session)):
        from km_tools.search import get_ficha_full_text
        result = await get_ficha_full_text("ficha-uuid-1")

    assert result["success"] is False
    assert result["data"]["requiere_solicitud"] is True
    assert "restricted-resource" in result["error"]
    assert result["data"]["solicitud_url"] == "https://ri.conicet.gov.ar/handle/11336/269341/restricted-resource"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_ficha_full_text_requiere_solicitud_sin_autoservicio():
    """PDF restringido (isAllowed=n) sin link de autoservicio en la página — el error
    debe decir que hace falta pedirlo por otra vía, no confundirlo con 'no disponible'."""
    mock_result = MagicMock()
    mock_result.fetchone.return_value = _make_ficha_row(
        texto_completo=None, requiere_solicitud=True, solicitud_url=None,
    )
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("km_tools.search.get_session_factory", return_value=MagicMock(return_value=mock_session)):
        from km_tools.search import get_ficha_full_text
        result = await get_ficha_full_text("ficha-uuid-1")

    assert result["success"] is False
    assert result["data"]["requiere_solicitud"] is True
    assert result["data"]["solicitud_url"] is None
    assert "otra vía" in result["error"] or "contacto" in result["error"].lower()


# ─────────────────────────────────────────
# INTEGRATION TESTS — requieren DB con harvest
# ─────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.asyncio
async def test_integration_busqueda_garrapata():
    """Busca 'garrapata' en los documentos INTA cosechados."""
    from knowledge_module.db import reset_engine
    from km_tools.search import search_fuentes_externas

    reset_engine()  # engine queda pegado al loop del asyncio.run() anterior si corre otro test antes

    result = await search_fuentes_externas("garrapata tick")
    assert result["success"], result["error"]
    # Al menos algún resultado esperado con el corpus INTA
    print(f"\nResultados 'garrapata': {result['data']['total']}")
    for r in result["data"]["results"][:3]:
        print(f"  [{r['rank']:.4f}] {r['titulo'][:70]}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_integration_busqueda_con_filtro_tipo():
    """Busca con filtro tipo=paper."""
    from knowledge_module.db import reset_engine
    from km_tools.search import search_fuentes_externas

    reset_engine()

    result = await search_fuentes_externas("virus influenza equina", tipo="paper", limit=5)
    assert result["success"], result["error"]
    for r in result["data"]["results"]:
        assert r["tipo"] == "paper"
    print(f"\nResultados 'virus influenza equina' (paper): {result['data']['total']}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_integration_query_vacio_o_sin_match():
    """Query que no matchea nada retorna lista vacía sin error."""
    from knowledge_module.db import reset_engine
    from km_tools.search import search_fuentes_externas

    reset_engine()

    result = await search_fuentes_externas("xyzzy_inexistente_12345")
    assert result["success"] is True
    assert result["data"]["total"] == 0
