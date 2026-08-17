"""
Tests de la API de solo lectura — CRIZA.

Unit: TestClient (in-process, sin servidor real) con mocks del KM.
Integration: TestClient contra el KM real.

Correr unit: pytest tests/ -m "not integration"
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

_CRIZA = Path(__file__).parent.parent.parent
_MODULE = Path(__file__).parent.parent
sys.path.insert(0, str(_CRIZA))
sys.path.insert(0, str(_MODULE))

import main as api_main

client = TestClient(api_main.app)

CASO_HELIOS = {
    "id": "caso-helios",
    "tipo": "caso",
    "props": {"nombre": "Efluentes biogás (Helios)", "descripcion": "desc", "estadio": "desde_cero"},
}
FRENTE_TECNICO = {"id": "frente-tecnico", "tipo": "frente", "props": {"nombre": "Frente técnico", "estado": "activo"}}


@pytest.mark.unit
def test_listar_casos():
    casos_mock = [CASO_HELIOS]
    with patch("main._listar_casos_fn", new=AsyncMock(return_value=casos_mock)):
        resp = client.get("/casos")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["nombre"] == "Efluentes biogás (Helios)"


# ── Crear caso (Etapa 13, 2026-08-17) ────────────────────────────────────────

@pytest.mark.unit
def test_crear_caso_exito():
    with patch("main._crear_caso_fn", new=AsyncMock(return_value={"success": True, "caso_id": "caso-nuevo-1", "error": None})) as mock_crear:
        resp = client.post("/casos", json={"nombre": "Compostaje Norte", "descripcion": "Planta de compostaje busca valorizar residuo.", "estadio": "desde_cero"})

    assert resp.status_code == 200
    assert resp.json() == {"caso_id": "caso-nuevo-1"}
    _, kwargs = mock_crear.call_args
    assert kwargs["nombre"] == "Compostaje Norte"
    assert kwargs["estadio"] == "desde_cero"


@pytest.mark.unit
def test_crear_caso_nombre_vacio_es_400():
    resp = client.post("/casos", json={"nombre": "   ", "descripcion": "algo"})
    assert resp.status_code == 400


@pytest.mark.unit
def test_crear_caso_descripcion_vacia_es_400():
    resp = client.post("/casos", json={"nombre": "algo", "descripcion": ""})
    assert resp.status_code == 400


@pytest.mark.unit
def test_crear_caso_falla_en_km_es_500():
    with patch("main._crear_caso_fn", new=AsyncMock(return_value={"success": False, "caso_id": None, "error": "boom"})):
        resp = client.post("/casos", json={"nombre": "X", "descripcion": "Y"})
    assert resp.status_code == 500


@pytest.mark.unit
def test_obtener_caso_no_encontrado():
    with patch("main.motor_api.obtener", new=AsyncMock(return_value=None)):
        resp = client.get("/casos/no-existe")
    assert resp.status_code == 404


@pytest.mark.unit
def test_obtener_caso_completo():
    with (
        patch("main.motor_api.obtener", new=AsyncMock(return_value=CASO_HELIOS)),
        patch("main._obtener_frentes_fn", new=AsyncMock(return_value=[FRENTE_TECNICO])),
        patch("main._obtener_documentos_fn", new=AsyncMock(return_value=[
            {"id": "doc-1", "props": {"titulo": "Evaluación", "modo": "chat", "estado": "borrador"}},
        ])),
        patch("main.motor_api.conexiones_de", new=AsyncMock(return_value=[])),
        patch("main._obtener_pendientes_fn", new=AsyncMock(return_value=[
            {"id": "p1", "props": {"descripcion": "Confirmar flete", "estado": "abierto"}},
        ])),
    ):
        resp = client.get("/casos/caso-helios")

    assert resp.status_code == 200
    data = resp.json()
    assert data["nombre"] == "Efluentes biogás (Helios)"
    assert len(data["frentes"]) == 1
    assert data["frentes"][0]["documentos"][0]["titulo"] == "Evaluación"
    assert data["pendientes"][0]["descripcion"] == "Confirmar flete"


@pytest.mark.unit
def test_obtener_documento_no_encontrado():
    with patch("main.motor_api.obtener", new=AsyncMock(return_value=None)):
        resp = client.get("/documentos/no-existe")
    assert resp.status_code == 404


@pytest.mark.unit
def test_obtener_documento_encontrado():
    doc = {"id": "doc-1", "tipo": "documento_caso", "props": {"titulo": "t", "contenido": "c", "modo": "chat", "estado": "borrador", "agente": "microbiologo"}}
    with patch("main.motor_api.obtener", new=AsyncMock(return_value=doc)):
        resp = client.get("/documentos/doc-1")
    assert resp.status_code == 200
    assert resp.json()["contenido"] == "c"


@pytest.mark.unit
def test_obtener_documento_id_de_otro_tipo_es_404():
    """Pasar el id de un caso (no un documento) no debe devolver datos de otro tipo."""
    with patch("main.motor_api.obtener", new=AsyncMock(return_value=CASO_HELIOS)):
        resp = client.get("/documentos/caso-helios")
    assert resp.status_code == 404


# ── Descargar documento (Etapa 14, 2026-08-17) ───────────────────────────────

@pytest.mark.unit
def test_slug_archivo_normaliza_acentos_y_simbolos():
    assert api_main._slug_archivo("Evaluación — microbiologo") == "evaluacion-microbiologo"


@pytest.mark.unit
def test_slug_archivo_vacio_usa_fallback():
    assert api_main._slug_archivo("") == "documento"


@pytest.mark.unit
def test_descargar_documento_ok():
    doc = {"id": "doc-1", "tipo": "documento_caso", "props": {"titulo": "Evaluación — microbiologo", "contenido": "# Informe\n\ncontenido real"}}
    with patch("main.motor_api.obtener", new=AsyncMock(return_value=doc)):
        resp = client.get("/documentos/doc-1/descargar")
    assert resp.status_code == 200
    assert resp.text == "# Informe\n\ncontenido real"
    assert resp.headers["content-type"].startswith("text/markdown")
    assert 'filename="evaluacion-microbiologo.md"' in resp.headers["content-disposition"]
    assert "attachment" in resp.headers["content-disposition"]


@pytest.mark.unit
def test_descargar_documento_no_encontrado():
    with patch("main.motor_api.obtener", new=AsyncMock(return_value=None)):
        resp = client.get("/documentos/no-existe/descargar")
    assert resp.status_code == 404


@pytest.mark.unit
def test_descargar_documento_otro_tipo_es_404():
    with patch("main.motor_api.obtener", new=AsyncMock(return_value=CASO_HELIOS)):
        resp = client.get("/documentos/caso-helios/descargar")
    assert resp.status_code == 404


# ── Adjuntar un archivo al chat (Etapa 17, 2026-08-17) ──────────────────────────

@pytest.mark.unit
def test_extraer_texto_pdf_real():
    """PDF real (no mockeado) construido en memoria con PyMuPDF — confirma la extracción de
    punta a punta contra `knowledge_module.document_store.store.extract_text`, no solo que la
    ruta HTTP existe."""
    import fitz

    doc = fitz.open()
    pagina = doc.new_page()
    pagina.insert_text((72, 72), "Composicion del efluente: N amonio 500-5000 mg/L")
    contenido = doc.tobytes()
    doc.close()

    resp = client.post("/archivos/extraer", files={"archivo": ("informe.pdf", contenido, "application/pdf")})

    assert resp.status_code == 200
    data = resp.json()
    assert data["nombre_archivo"] == "informe.pdf"
    assert "500-5000 mg/L" in data["texto"]
    assert data["truncado"] is False


@pytest.mark.unit
def test_extraer_texto_pdf_sin_capa_de_texto_es_422():
    import fitz

    doc = fitz.open()
    doc.new_page()  # página en blanco, sin texto
    contenido = doc.tobytes()
    doc.close()

    resp = client.post("/archivos/extraer", files={"archivo": ("escaneo.pdf", contenido, "application/pdf")})
    assert resp.status_code == 422


@pytest.mark.unit
def test_extraer_texto_docx_real():
    import io as _io

    import docx as _docx

    documento = _docx.Document()
    documento.add_paragraph("Composicion quimica del digestato liquido de Helios.")
    buffer = _io.BytesIO()
    documento.save(buffer)

    resp = client.post(
        "/archivos/extraer",
        files={"archivo": ("Helios_Informe_Tecnico_Digerido.docx", buffer.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert "digestato liquido de Helios" in data["texto"]


@pytest.mark.unit
def test_extraer_texto_txt():
    resp = client.post("/archivos/extraer", files={"archivo": ("notas.txt", b"pH 7,5-8,5, alcalino", "text/plain")})
    assert resp.status_code == 200
    assert resp.json()["texto"] == "pH 7,5-8,5, alcalino"


@pytest.mark.unit
def test_extraer_texto_md():
    resp = client.post("/archivos/extraer", files={"archivo": ("notas.md", b"# Composicion\n\nN: 500 mg/L", "text/markdown")})
    assert resp.status_code == 200
    assert "# Composicion" in resp.json()["texto"]


@pytest.mark.unit
def test_extraer_extension_no_soportada_es_400():
    resp = client.post("/archivos/extraer", files={"archivo": ("planilla.xlsx", b"lo que sea", "application/octet-stream")})
    assert resp.status_code == 400


@pytest.mark.unit
def test_extraer_trunca_archivo_largo():
    texto_largo = "x" * 70_000
    resp = client.post("/archivos/extraer", files={"archivo": ("largo.txt", texto_largo.encode(), "text/plain")})
    assert resp.status_code == 200
    data = resp.json()
    assert data["truncado"] is True
    assert len(data["texto"]) == 60_000


# ── Elegir modelo por sesión (Etapa 15, 2026-08-17) ─────────────────────────────

@pytest.mark.unit
def test_listar_modelos():
    resp = client.get("/modelos")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 4
    ids = {m["id"] for m in data}
    assert "claude-sonnet-4-6" in ids
    assert all({"id", "nombre", "nota"} <= m.keys() for m in data)


# ── Chat del Conductor — sesiones persistidas en el KM, no en memoria ──────────

@pytest.mark.unit
def test_crear_sesion_conductor():
    with (
        patch("main.load_plantilla", new=AsyncMock(return_value={})),
        patch("main.motor_api.guardar_ficha", new=AsyncMock(return_value={"success": True, "id": "sesion-1"})) as mock_guardar,
    ):
        resp = client.post("/conductor/sesiones")

    assert resp.status_code == 200
    assert resp.json()["session_id"] == "sesion-1"
    _, kwargs = mock_guardar.call_args
    assert kwargs["area"] == "conductor_sesiones"
    assert kwargs["campos"]["mensajes"] == []


@pytest.mark.unit
def test_crear_sesion_conductor_con_modelo_elegido():
    with (
        patch("main.load_plantilla", new=AsyncMock(return_value={})),
        patch("main.motor_api.guardar_ficha", new=AsyncMock(return_value={"success": True, "id": "sesion-1"})) as mock_guardar,
    ):
        resp = client.post("/conductor/sesiones", json={"modelo": "claude-opus-5"})

    assert resp.status_code == 200
    _, kwargs = mock_guardar.call_args
    assert kwargs["campos"]["modelo"] == "claude-opus-5"


@pytest.mark.unit
def test_crear_sesion_conductor_sin_body_queda_modelo_none():
    """El body es opcional (test_crear_sesion_conductor de arriba ya lo cubre sin json=) — acá
    se confirma explícitamente que el campo persistido es None, no que falte la clave."""
    with (
        patch("main.load_plantilla", new=AsyncMock(return_value={})),
        patch("main.motor_api.guardar_ficha", new=AsyncMock(return_value={"success": True, "id": "sesion-1"})) as mock_guardar,
    ):
        resp = client.post("/conductor/sesiones")

    assert resp.status_code == 200
    _, kwargs = mock_guardar.call_args
    assert kwargs["campos"]["modelo"] is None


# ── Historial de sesiones (Etapa 16, 2026-08-17 — fix del bug "se perdió la respuesta") ────────

_MENSAJES_CRUDOS_CON_TOOL_USE = [
    {"role": "user", "content": "¿Qué casos tenemos activos?"},
    {"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "listar_casos", "input": {}}]},
    {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "[]"}]},
    {"role": "assistant", "content": [{"type": "text", "text": "Tenemos 2 casos activos: Helios y MicroBigs."}]},
]


@pytest.mark.unit
def test_mensajes_a_turnos_filtra_pasos_intermedios_de_tools():
    turnos = api_main._mensajes_a_turnos(_MENSAJES_CRUDOS_CON_TOOL_USE, "conductor")
    assert turnos == [
        {"rol": "vos", "texto": "¿Qué casos tenemos activos?"},
        {"rol": "conductor", "texto": "Tenemos 2 casos activos: Helios y MicroBigs."},
    ]


@pytest.mark.unit
def test_mensajes_a_turnos_vacio_si_no_hay_mensajes():
    assert api_main._mensajes_a_turnos([], "conductor") == []


@pytest.mark.unit
def test_listar_sesiones_conductor_excluye_sesiones_sin_turnos():
    """Sesiones creadas pero abandonadas antes de mandar el primer mensaje (recarga de página,
    el bug que motivó esta etapa) no deben aparecer en el historial."""
    vacia = {"id": "s-vacia", "tipo": "sesion", "props": {"mensajes": [], "iniciada_en": "2026-08-17T10:00:00Z", "actualizada_en": "2026-08-17T10:00:00Z"}}
    con_contenido = {"id": "s-real", "tipo": "sesion", "props": {"mensajes": _MENSAJES_CRUDOS_CON_TOOL_USE, "iniciada_en": "2026-08-17T09:00:00Z", "actualizada_en": "2026-08-17T09:05:00Z", "modelo": "claude-opus-5"}}
    with patch("main.motor_api.listar", new=AsyncMock(return_value=[vacia, con_contenido])):
        resp = client.get("/conductor/sesiones")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == "s-real"
    assert data[0]["primer_mensaje"] == "¿Qué casos tenemos activos?"
    assert data[0]["modelo"] == "claude-opus-5"


@pytest.mark.unit
def test_listar_sesiones_conductor_trunca_primer_mensaje_largo():
    largo = "x" * 200
    sesion = {"id": "s-larga", "tipo": "sesion", "props": {"mensajes": [{"role": "user", "content": largo}], "actualizada_en": "2026-08-17T09:00:00Z"}}
    with patch("main.motor_api.listar", new=AsyncMock(return_value=[sesion])):
        resp = client.get("/conductor/sesiones")
    data = resp.json()
    assert len(data[0]["primer_mensaje"]) == 141  # 140 + "…"
    assert data[0]["primer_mensaje"].endswith("…")


@pytest.mark.unit
def test_obtener_sesion_conductor_ok():
    sesion = {"id": "s-real", "tipo": "sesion", "props": {"mensajes": _MENSAJES_CRUDOS_CON_TOOL_USE, "modelo": "claude-haiku-4-5-20251001"}}
    with patch("main.motor_api.obtener", new=AsyncMock(return_value=sesion)):
        resp = client.get("/conductor/sesiones/s-real")
    assert resp.status_code == 200
    data = resp.json()
    assert data["modelo"] == "claude-haiku-4-5-20251001"
    assert len(data["turnos"]) == 2
    assert data["turnos"][1]["texto"] == "Tenemos 2 casos activos: Helios y MicroBigs."


@pytest.mark.unit
def test_obtener_sesion_conductor_no_encontrada():
    with patch("main.motor_api.obtener", new=AsyncMock(return_value=None)):
        resp = client.get("/conductor/sesiones/no-existe")
    assert resp.status_code == 404


@pytest.mark.unit
def test_listar_sesiones_especialista_nombre_invalido():
    resp = client.get("/especialistas/sesiones", params={"especialista": "no-existe"})
    assert resp.status_code == 404


@pytest.mark.unit
def test_listar_sesiones_especialista_incluye_frente_id():
    con_frente = {"id": "s-1", "tipo": "sesion_especialista", "props": {"mensajes": _MENSAJES_CRUDOS_CON_TOOL_USE, "especialista": "microbiologo", "frente_id": "frente-1", "actualizada_en": "2026-08-17T09:00:00Z"}}
    with patch("main.motor_api.listar", new=AsyncMock(return_value=[con_frente])):
        resp = client.get("/especialistas/sesiones", params={"especialista": "microbiologo"})
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["frente_id"] == "frente-1"


@pytest.mark.unit
def test_obtener_sesion_especialista_ok():
    sesion = {"id": "s-1", "tipo": "sesion_especialista", "props": {"mensajes": _MENSAJES_CRUDOS_CON_TOOL_USE, "especialista": "microbiologo", "frente_id": None, "modelo": None}}
    with patch("main.motor_api.obtener", new=AsyncMock(return_value=sesion)):
        resp = client.get("/especialistas/sesiones/s-1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["especialista"] == "microbiologo"
    assert len(data["turnos"]) == 2
    assert data["turnos"][1]["rol"] == "especialista"


@pytest.mark.unit
def test_obtener_sesion_especialista_no_encontrada():
    with patch("main.motor_api.obtener", new=AsyncMock(return_value=None)):
        resp = client.get("/especialistas/sesiones/no-existe")
    assert resp.status_code == 404


@pytest.mark.unit
def test_crear_sesion_conductor_falla_al_guardar_es_500():
    with (
        patch("main.load_plantilla", new=AsyncMock(return_value={})),
        patch("main.motor_api.guardar_ficha", new=AsyncMock(return_value={"success": False, "error": "boom"})),
    ):
        resp = client.post("/conductor/sesiones")
    assert resp.status_code == 500


@pytest.mark.unit
def test_enviar_mensaje_sesion_inexistente():
    with patch("main.motor_api.obtener", new=AsyncMock(return_value=None)):
        resp = client.post("/conductor/sesiones/no-existe/mensajes", json={"texto": "hola"})
    assert resp.status_code == 404


@pytest.mark.unit
def test_enviar_mensaje_session_id_invalido_es_404_no_500():
    """Un session_id que no es un UUID válido rompe la query SQL — se captura y se trata igual
    que 'no encontrada', no como un error de servidor."""
    with patch("main.motor_api.obtener", new=AsyncMock(side_effect=Exception("invalid input syntax for type uuid"))):
        resp = client.post("/conductor/sesiones/no-es-un-uuid/mensajes", json={"texto": "hola"})
    assert resp.status_code == 404


@pytest.mark.unit
def test_enviar_mensaje_vacio_es_400():
    resp = client.post("/conductor/sesiones/cualquier-id/mensajes", json={"texto": "   "})
    assert resp.status_code == 400


@pytest.mark.unit
def test_enviar_mensaje_conductor_devuelve_respuesta():
    sesion = {"id": "sesion-1", "tipo": "sesion", "props": {"mensajes": []}}

    async def fake_enviar_mensaje(messages, texto, model=None, verbose=False, tracker=None):
        messages.append({"role": "user", "content": texto})
        messages.append({"role": "assistant", "content": "Hola, ¿en qué te ayudo?"})
        return "Hola, ¿en qué te ayudo?", messages

    with (
        patch("main.motor_api.obtener", new=AsyncMock(return_value=sesion)),
        patch("main.motor_api.actualizar_props", new=AsyncMock(return_value={"success": True})) as mock_actualizar,
        patch("main._enviar_mensaje_conductor", new=fake_enviar_mensaje),
    ):
        resp = client.post("/conductor/sesiones/sesion-1/mensajes", json={"texto": "Hola"})

    assert resp.status_code == 200
    assert resp.json()["respuesta"] == "Hola, ¿en qué te ayudo?"
    args, _ = mock_actualizar.call_args
    assert args[0] == "sesion-1"
    assert len(args[1]["mensajes"]) == 2  # persistió el historial actualizado


@pytest.mark.unit
def test_enviar_mensaje_conductor_mantiene_historial_entre_turnos():
    """El segundo mensaje del mismo session_id debe arrancar con los mensajes que el primer
    turno persistió — la memoria conversacional viene de leer el KM, no de un dict en memoria."""
    km_fake: dict[str, list] = {"sesion-1": []}
    historiales_vistos = []

    async def fake_obtener(ficha_id, *, tenant):
        return {"id": ficha_id, "tipo": "sesion", "props": {"mensajes": km_fake[ficha_id]}}

    async def fake_actualizar_props(ficha_id, cambios, *, tenant):
        km_fake[ficha_id] = cambios["mensajes"]
        return {"success": True}

    async def fake_enviar_mensaje(messages, texto, model=None, verbose=False, tracker=None):
        historiales_vistos.append(len(messages))
        messages.append({"role": "user", "content": texto})
        messages.append({"role": "assistant", "content": "ok"})
        return "ok", messages

    with (
        patch("main.motor_api.obtener", new=fake_obtener),
        patch("main.motor_api.actualizar_props", new=fake_actualizar_props),
        patch("main._enviar_mensaje_conductor", new=fake_enviar_mensaje),
    ):
        client.post("/conductor/sesiones/sesion-1/mensajes", json={"texto": "primero"})
        client.post("/conductor/sesiones/sesion-1/mensajes", json={"texto": "segundo"})

    assert historiales_vistos == [0, 2]  # el segundo turno arrancó con los 2 mensajes que quedaron del primero


@pytest.mark.unit
def test_enviar_mensaje_conductor_pasa_modelo_elegido_a_la_sesion():
    sesion = {"id": "sesion-1", "tipo": "sesion", "props": {"mensajes": [], "modelo": "claude-haiku-4-5-20251001"}}
    kwargs_vistos = {}

    async def fake_enviar_mensaje(messages, texto, model=None, verbose=False, tracker=None):
        kwargs_vistos["model"] = model
        messages.append({"role": "user", "content": texto})
        messages.append({"role": "assistant", "content": "ok"})
        return "ok", messages

    with (
        patch("main.motor_api.obtener", new=AsyncMock(return_value=sesion)),
        patch("main.motor_api.actualizar_props", new=AsyncMock(return_value={"success": True})),
        patch("main._enviar_mensaje_conductor", new=fake_enviar_mensaje),
    ):
        resp = client.post("/conductor/sesiones/sesion-1/mensajes", json={"texto": "hola"})

    assert resp.status_code == 200
    assert kwargs_vistos["model"] == "claude-haiku-4-5-20251001"


@pytest.mark.unit
def test_enviar_mensaje_conductor_sin_modelo_no_fuerza_override():
    """Sesión sin `modelo` (creada antes de la Etapa 15, o sin elegir uno) — no debe pasarse
    `model=` al agente, para que siga usando su default (env var del agente)."""
    sesion = {"id": "sesion-1", "tipo": "sesion", "props": {"mensajes": []}}
    kwargs_vistos = {}

    async def fake_enviar_mensaje(messages, texto, model=None, verbose=False, tracker=None):
        kwargs_vistos["model"] = model
        messages.append({"role": "user", "content": texto})
        messages.append({"role": "assistant", "content": "ok"})
        return "ok", messages

    with (
        patch("main.motor_api.obtener", new=AsyncMock(return_value=sesion)),
        patch("main.motor_api.actualizar_props", new=AsyncMock(return_value={"success": True})),
        patch("main._enviar_mensaje_conductor", new=fake_enviar_mensaje),
    ):
        resp = client.post("/conductor/sesiones/sesion-1/mensajes", json={"texto": "hola"})

    assert resp.status_code == 200
    assert kwargs_vistos["model"] is None


@pytest.mark.unit
def test_cerrar_sesion_conductor_no_encontrada():
    with patch("main.motor_api.obtener", new=AsyncMock(return_value=None)):
        resp = client.post("/conductor/sesiones/no-existe/cerrar")
    assert resp.status_code == 404


@pytest.mark.unit
def test_cerrar_sesion_conductor_con_leccion():
    sesion = {"id": "sesion-1", "tipo": "sesion", "props": {"mensajes": [{"role": "user", "content": "hola"}]}}
    with (
        patch("main.motor_api.obtener", new=AsyncMock(return_value=sesion)),
        patch("main._cerrar_sesion_conductor", new=AsyncMock(return_value={"success": True, "id": "leccion-1"})),
    ):
        resp = client.post("/conductor/sesiones/sesion-1/cerrar")
    assert resp.status_code == 200
    assert resp.json() == {"leccion_guardada": True, "id": "leccion-1"}


@pytest.mark.unit
def test_cerrar_sesion_conductor_sin_leccion():
    sesion = {"id": "sesion-1", "tipo": "sesion", "props": {"mensajes": []}}
    with (
        patch("main.motor_api.obtener", new=AsyncMock(return_value=sesion)),
        patch("main._cerrar_sesion_conductor", new=AsyncMock(return_value=None)),
    ):
        resp = client.post("/conductor/sesiones/sesion-1/cerrar")
    assert resp.status_code == 200
    assert resp.json() == {"leccion_guardada": False, "id": None}


# ── Chat con un especialista puntual (Etapa 10, 2026-08-16) ────────────────────

@pytest.mark.unit
def test_crear_sesion_especialista_nombre_invalido():
    resp = client.post("/especialistas/no-existe/sesiones", json={"frente_id": "f1"})
    assert resp.status_code == 404


@pytest.mark.unit
def test_crear_sesion_especialista_ok():
    with (
        patch("main._mod_microbiologo.iniciar_sesion", new=AsyncMock(return_value=[{"role": "user", "content": "contexto inicial"}])),
        patch("main.load_plantilla", new=AsyncMock(return_value={})),
        patch("main.motor_api.guardar_ficha", new=AsyncMock(return_value={"success": True, "id": "sesion-esp-1"})) as mock_guardar,
    ):
        resp = client.post("/especialistas/microbiologo/sesiones", json={"frente_id": "frente-1"})

    assert resp.status_code == 200
    assert resp.json() == {"session_id": "sesion-esp-1"}
    _, kwargs = mock_guardar.call_args
    assert kwargs["area"] == "especialista_sesiones"
    assert kwargs["campos"]["especialista"] == "microbiologo"
    assert kwargs["campos"]["frente_id"] == "frente-1"


@pytest.mark.unit
def test_crear_sesion_especialista_con_modelo_elegido():
    with (
        patch("main._mod_microbiologo.iniciar_sesion", new=AsyncMock(return_value=[{"role": "user", "content": "contexto inicial"}])),
        patch("main.load_plantilla", new=AsyncMock(return_value={})),
        patch("main.motor_api.guardar_ficha", new=AsyncMock(return_value={"success": True, "id": "sesion-esp-1"})) as mock_guardar,
    ):
        resp = client.post("/especialistas/microbiologo/sesiones", json={"frente_id": "frente-1", "modelo": "claude-sonnet-5"})

    assert resp.status_code == 200
    _, kwargs = mock_guardar.call_args
    assert kwargs["campos"]["modelo"] == "claude-sonnet-5"


@pytest.mark.unit
def test_crear_sesion_especialista_frente_no_encontrado_es_404():
    with patch("main._mod_microbiologo.iniciar_sesion", new=AsyncMock(side_effect=ValueError("Frente no encontrado en el KM"))):
        resp = client.post("/especialistas/microbiologo/sesiones", json={"frente_id": "no-existe"})
    assert resp.status_code == 404


@pytest.mark.unit
def test_crear_sesion_especialista_consulta_libre_sin_frente_id():
    """Etapa 12 — sin frente_id en el body, no debe llamar iniciar_sesion (no hay contexto de
    caso que armar) y la ficha se crea con frente_id=None."""
    with (
        patch("main._mod_microbiologo.iniciar_sesion", new=AsyncMock()) as mock_iniciar,
        patch("main.load_plantilla", new=AsyncMock(return_value={})),
        patch("main.motor_api.guardar_ficha", new=AsyncMock(return_value={"success": True, "id": "sesion-libre-1"})) as mock_guardar,
    ):
        resp = client.post("/especialistas/microbiologo/sesiones", json={})

    assert resp.status_code == 200
    assert resp.json() == {"session_id": "sesion-libre-1"}
    mock_iniciar.assert_not_awaited()
    _, kwargs = mock_guardar.call_args
    assert kwargs["campos"]["frente_id"] is None
    assert kwargs["campos"]["mensajes"] == []


@pytest.mark.unit
def test_enviar_mensaje_especialista_sesion_inexistente():
    with patch("main.motor_api.obtener", new=AsyncMock(return_value=None)):
        resp = client.post("/especialistas/sesiones/no-existe/mensajes", json={"texto": "hola"})
    assert resp.status_code == 404


@pytest.mark.unit
def test_enviar_mensaje_especialista_vacio_es_400():
    resp = client.post("/especialistas/sesiones/cualquier-id/mensajes", json={"texto": "   "})
    assert resp.status_code == 400


@pytest.mark.unit
def test_enviar_mensaje_especialista_devuelve_respuesta():
    sesion = {"id": "sesion-esp-1", "tipo": "sesion_especialista", "props": {"especialista": "microbiologo", "frente_id": "frente-1", "mensajes": []}}

    async def fake_enviar_mensaje(messages, texto, frente_id):
        messages.append({"role": "user", "content": texto})
        messages.append({"role": "assistant", "content": "Respuesta del microbiólogo"})
        return "Respuesta del microbiólogo", messages

    with (
        patch("main.motor_api.obtener", new=AsyncMock(return_value=sesion)),
        patch("main.motor_api.actualizar_props", new=AsyncMock(return_value={"success": True})),
        patch("main._mod_microbiologo.enviar_mensaje", new=fake_enviar_mensaje),
    ):
        resp = client.post("/especialistas/sesiones/sesion-esp-1/mensajes", json={"texto": "¿Qué opinás?"})

    assert resp.status_code == 200
    assert resp.json()["respuesta"] == "Respuesta del microbiólogo"


@pytest.mark.unit
def test_enviar_mensaje_especialista_pasa_modelo_elegido():
    sesion = {"id": "sesion-esp-1", "tipo": "sesion_especialista", "props": {"especialista": "microbiologo", "frente_id": "frente-1", "mensajes": [], "modelo": "claude-haiku-4-5-20251001"}}
    kwargs_vistos = {}

    async def fake_enviar_mensaje(messages, texto, frente_id, model=None):
        kwargs_vistos["model"] = model
        messages.append({"role": "user", "content": texto})
        messages.append({"role": "assistant", "content": "ok"})
        return "ok", messages

    with (
        patch("main.motor_api.obtener", new=AsyncMock(return_value=sesion)),
        patch("main.motor_api.actualizar_props", new=AsyncMock(return_value={"success": True})),
        patch("main._mod_microbiologo.enviar_mensaje", new=fake_enviar_mensaje),
    ):
        resp = client.post("/especialistas/sesiones/sesion-esp-1/mensajes", json={"texto": "hola"})

    assert resp.status_code == 200
    assert kwargs_vistos["model"] == "claude-haiku-4-5-20251001"


@pytest.mark.unit
def test_enviar_mensaje_especialista_sin_modelo_no_fuerza_override():
    sesion = {"id": "sesion-esp-1", "tipo": "sesion_especialista", "props": {"especialista": "microbiologo", "frente_id": "frente-1", "mensajes": []}}
    kwargs_vistos = {}

    async def fake_enviar_mensaje(messages, texto, frente_id, model=None):
        kwargs_vistos["model"] = model
        messages.append({"role": "user", "content": texto})
        messages.append({"role": "assistant", "content": "ok"})
        return "ok", messages

    with (
        patch("main.motor_api.obtener", new=AsyncMock(return_value=sesion)),
        patch("main.motor_api.actualizar_props", new=AsyncMock(return_value={"success": True})),
        patch("main._mod_microbiologo.enviar_mensaje", new=fake_enviar_mensaje),
    ):
        resp = client.post("/especialistas/sesiones/sesion-esp-1/mensajes", json={"texto": "hola"})

    assert resp.status_code == 200
    assert kwargs_vistos["model"] is None


# ── Características de un agente (Etapa 11, 2026-08-16) ─────────────────────────

@pytest.mark.unit
def test_obtener_info_agente_nombre_invalido():
    resp = client.get("/agentes/no-existe")
    assert resp.status_code == 404


@pytest.mark.unit
def test_obtener_info_agente_conductor():
    resp = client.get("/agentes/conductor")
    assert resp.status_code == 200
    data = resp.json()
    assert data["nombre"] == "conductor"
    assert data["system_prompt"]
    nombres = {t["name"] for t in data["tools"]}
    assert "ver_caso" in nombres
    # el Conductor no distingue chat de corrida formal — todas sus tools están disponibles en chat
    assert all(t["disponible_en_chat"] for t in data["tools"])


@pytest.mark.unit
def test_obtener_info_agente_especialista_marca_submit_fuera_del_chat():
    resp = client.get("/agentes/microbiologo")
    assert resp.status_code == 200
    data = resp.json()
    tools_por_nombre = {t["name"]: t for t in data["tools"]}
    assert tools_por_nombre["submit_evaluacion_tecnica"]["disponible_en_chat"] is False
    assert tools_por_nombre["search_kegg"]["disponible_en_chat"] is True


@pytest.mark.unit
def test_cors_permite_localhost_3000():
    resp = client.options(
        "/casos",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"


# ── Integration: contra el KM real ──────────────────────────────────────────
#
# httpx.AsyncClient (no el TestClient síncrono) — el TestClient síncrono crea un event loop
# nuevo por request, y el engine async de knowledge_module cachea un pool de conexiones atado
# al loop de la PRIMERA request; en la segunda request, con un loop distinto, revienta con
# "Event loop is closed" al cerrar conexiones huérfanas. AsyncClient corre dentro del mismo
# loop que el test (pytest-asyncio), igual que un server real (uvicorn) sirve todo un mismo loop.

@pytest.mark.integration
@pytest.mark.asyncio
async def test_listar_y_obtener_caso_real():
    """Corrida real contra el KM — Helios/MicroBigs ya cargados."""
    from knowledge_module.db import reset_engine
    reset_engine()

    transport = httpx.ASGITransport(app=api_main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/casos")
        assert resp.status_code == 200
        casos = resp.json()
        assert len(casos) >= 2
        helios = next(c for c in casos if "Helios" in c["nombre"])

        resp2 = await ac.get(f"/casos/{helios['id']}")
        assert resp2.status_code == 200
        detalle = resp2.json()
        assert len(detalle["frentes"]) >= 2
        assert isinstance(detalle["pendientes"], list)
