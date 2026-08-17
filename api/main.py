"""
API — CRIZA (Etapa 6 del plan de construcción, 2026-08-16; chat del Conductor sumado el mismo
día, v1.2 adelantada a pedido de Sebas)

Backend delgado para la app Next.js (`web/`) — reusa `knowledge_module`/`utils/casos.py` y
`conductor/conductor.py` directo, sin lógica duplicada.

Dos superficies distintas, cada una con su propia relación con producción/staging:
- `GET /casos`, `/casos/{id}`, `/documentos/{id}` — solo lectura, leen `DATABASE_URL`
  (producción) sin riesgo de escritura. `POST /casos` (Etapa 13, 2026-08-17) es la excepción
  deliberada — crea un caso nuevo, escribe directo a producción (mismo criterio que el resto de
  la costura: Sebas es dueño de decidir qué se crea, no hay staging intermedio para esto).
- `/conductor/*` — el Conductor SÍ puede escribir al KM cuando invoca un especialista
  (`correr_especialista`, vía la costura) o crea un caso (`crear_caso`, Etapa 13) — usa la misma
  `DATABASE_URL` que el resto del proceso (producción por default). Sebas es dueño de decidir qué
  corridas promueve, igual que con cualquier otro cliente de la costura.

Sesiones de chat del Conductor persistidas en el KM (área `conductor_sesiones`, plantilla
`config/plantillas/conductor_sesiones.yaml`) — no en memoria del proceso. Sebas preguntó
explícitamente cómo resolver que se perdían al reiniciar `api/run.py`; la respuesta es la misma
que ya usa todo lo demás en este proyecto (`pipeline_status`, `token_usage`): el KM, no un
archivo local nuevo (CLAUDE.md: "si el output de un agente no está en el KM, no existe para el
sistema"). `session_id` que ve el browser es directamente el id de la ficha — no hay un id
separado que mantener sincronizado.

Ver docs/DESIGN_GATE.md — decisiones A-E (2026-08-16).
"""

import io
import re
import sys
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import docx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

_API_DIR = Path(__file__).parent
_CRIZA_DIR = _API_DIR.parent
sys.path.insert(0, str(_CRIZA_DIR))
# conductor/ al frente del sys.path — mismo truco que conductor/run.py: hace que "import
# conductor" (bare) resuelva a conductor/conductor.py (el archivo), no al paquete
# conductor/__init__.py. Importarlo como "from conductor.conductor import ..." en cambio
# cachea el PAQUETE en sys.modules["conductor"], lo que rompe el "import conductor as cond"
# de conductor/tests/test_conductor.py cuando ambas suites corren en el mismo proceso pytest
# (encontrado corriendo la regresión completa, no antes).
sys.path.insert(0, str(_CRIZA_DIR / "conductor"))

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from knowledge_module.document_store.store import extract_text as _extraer_texto_pdf_de_path
from knowledge_module.motor import api as motor_api
from knowledge_module.motor.loader import load_plantilla
from utils.ai_client import MODELOS_DISPONIBLES
from utils.casos import (
    listar_casos as _listar_casos_fn,
    obtener_frentes_de_caso as _obtener_frentes_fn,
    obtener_documentos_de_frente as _obtener_documentos_fn,
    obtener_pendientes_de_caso as _obtener_pendientes_fn,
    crear_caso as _crear_caso_fn,
)
from conductor import (
    enviar_mensaje as _enviar_mensaje_conductor,
    # serializar_mensajes no es en realidad específico del Conductor — solo convierte
    # ContentBlock (utils/ai_client.py) a dict plano — se reusa tal cual para las sesiones de
    # chat de cada especialista, sin duplicar la misma función 3 veces más.
    serializar_mensajes as _serializar_mensajes,
    cerrar_sesion as _cerrar_sesion_conductor,
)
import conductor as _mod_conductor  # el módulo en sí, para leer TOOLS/SYSTEM_PROMPT en vivo (Etapa 11)
import importlib.util


def _cargar_modulo_agente(nombre: str, archivo: Path):
    """
    Carga `archivo` como módulo standalone bajo una clave PROPIA de `sys.modules`
    (`_api_<nombre>`, nunca `<nombre>`) — ninguno de los dos estilos de import ya en uso en el
    proyecto para estos 3 agentes sirve acá: bare (`import microbiologo_agent`, el que usan
    `microbiologo_agent/tests/` y su propio `run.py`) y package-qualificado
    (`microbiologo_agent.microbiologo_agent`, el que usa `orquestador/registry.py::get_registry()`
    de forma perezosa) son MUTUAMENTE EXCLUYENTES en el mismo proceso — cualquiera de los dos que
    toque primero `sys.modules["microbiologo_agent"]` (archivo o paquete) rompe al otro apenas se
    ejecuta (confirmado corriendo la regresión combinada: `agronomo_agent/tests` colecciona antes
    que `api/tests` alfabéticamente, cachea el archivo, y el import package-qualificado de acá
    fallaba con "'agronomo_agent' is not a package"). Cargar bajo una clave separada no colisiona
    con ninguno de los dos — es un objeto de módulo aparte, no comparte `sys.modules[nombre]`.

    El propio archivo del agente inserta SU carpeta al frente de `sys.path` como efecto de lado
    (mismo truco de siempre, para que sus propios imports internos resuelvan) — eso por sí solo
    ya alcanza para romper una resolución package-qualificada de `<nombre>.<nombre>` DESPUÉS de
    esta función, aunque nunca toquemos `sys.modules[nombre]` (confirmado con una prueba real:
    alcanza con que la carpeta quede al frente de `sys.path` para que Python encuentre el ARCHIVO
    antes que el paquete la próxima vez que alguien resuelva `agronomo_agent` desde cero). Por
    eso se restaura `sys.path` al estado previo al salir — la carga ya completó lo que necesitaba
    resolver con la carpeta al frente, no hace falta dejarla ahí después.
    """
    snapshot = list(sys.path)
    try:
        spec = importlib.util.spec_from_file_location(f"_api_{nombre}", archivo)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        return modulo
    finally:
        sys.path[:] = snapshot


_mod_microbiologo = _cargar_modulo_agente("microbiologo_agent", _CRIZA_DIR / "microbiologo_agent" / "microbiologo_agent.py")
_mod_ingeniero_ambiental = _cargar_modulo_agente("ingeniero_ambiental_agent", _CRIZA_DIR / "ingeniero_ambiental_agent" / "ingeniero_ambiental_agent.py")
_mod_agronomo = _cargar_modulo_agente("agronomo_agent", _CRIZA_DIR / "agronomo_agent" / "agronomo_agent.py")

# Mapea a los MÓDULOS, no a (iniciar_sesion, enviar_mensaje) ya extraídas — así un test puede
# patchear "main._mod_microbiologo.iniciar_sesion" y que el endpoint lo vea (busca el atributo
# en el módulo en cada llamada, no una referencia a función capturada una sola vez acá arriba).
_ESPECIALISTAS_CHAT = {
    "microbiologo": _mod_microbiologo,
    "ingeniero_ambiental": _mod_ingeniero_ambiental,
    "agronomo": _mod_agronomo,
}

# Todos los agentes con superficie de chat, incluido el Conductor — para el panel de
# características (Etapa 11). Reusa los mismos objetos de módulo que _ESPECIALISTAS_CHAT.
_AGENTES_INFO = {"conductor": _mod_conductor, **_ESPECIALISTAS_CHAT}

_TENANT = "criza"
_PLANTILLA_SESIONES = _CRIZA_DIR / "config" / "plantillas" / "conductor_sesiones.yaml"
_PLANTILLA_SESIONES_ESPECIALISTA = _CRIZA_DIR / "config" / "plantillas" / "especialista_sesiones.yaml"

app = FastAPI(title="CRIZA API", description="API para la app web (Etapa 6) — casos de solo lectura + chat del Conductor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/casos")
async def listar_casos() -> list[dict]:
    casos = await _listar_casos_fn(tenant=_TENANT)
    return [
        {
            "id": c["id"],
            "nombre": (c.get("props") or {}).get("nombre"),
            "descripcion": (c.get("props") or {}).get("descripcion"),
            "estadio": (c.get("props") or {}).get("estadio"),
        }
        for c in casos
    ]


class _CrearCasoIn(BaseModel):
    nombre: str
    descripcion: str
    estadio: str | None = None
    fecha_inicio: str | None = None
    notas: str | None = None


@app.post("/casos")
async def crear_caso(body: _CrearCasoIn) -> dict:
    """
    Etapa 13 (2026-08-17) — hasta acá, los 2 casos reales del sistema se habían cargado por
    script directo al KM; Sebas preguntó cómo abrir uno nuevo y la respuesta era "no se puede,
    ni con el Conductor". `nombre`/`descripcion` son los únicos campos realmente obligatorios
    (son los que arman `texto_busqueda`, el campo vectorizado) — el resto es opcional a
    propósito, un caso puede arrancar con lo mínimo y completarse después.
    """
    nombre = body.nombre.strip()
    descripcion = body.descripcion.strip()
    if not nombre or not descripcion:
        raise HTTPException(status_code=400, detail="nombre y descripción son obligatorios")

    resultado = await _crear_caso_fn(
        nombre=nombre, descripcion=descripcion, tenant=_TENANT,
        estadio=body.estadio, fecha_inicio=body.fecha_inicio, notas=body.notas,
    )
    if not resultado["success"]:
        raise HTTPException(status_code=500, detail=f"No se pudo crear el caso: {resultado['error']}")
    return {"caso_id": resultado["caso_id"]}


@app.get("/modelos")
async def listar_modelos() -> list[dict]:
    """
    Lista curada de modelos elegibles por sesión de chat (Etapa 15, 2026-08-17) — no texto libre,
    para que la UI nunca ofrezca un ID inválido. Fuente única: `utils/ai_client.py::
    MODELOS_DISPONIBLES` — sumar un modelo nuevo (o un proveedor nuevo cuando haya credenciales)
    es tocar ese único lugar, esta ruta y la UI lo leen de ahí, no lo duplican.
    """
    return MODELOS_DISPONIBLES


@app.get("/casos/{caso_id}")
async def obtener_caso(caso_id: str) -> dict:
    caso = await motor_api.obtener(caso_id, tenant=_TENANT)
    if not caso or caso.get("tipo") != "caso":
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    caso_props = caso.get("props") or {}
    frentes = await _obtener_frentes_fn(caso_id, tenant=_TENANT)
    frentes_out = []
    for f in frentes:
        documentos = await _obtener_documentos_fn(f["id"], tenant=_TENANT)
        artefactos = await motor_api.conexiones_de(
            f["id"], tipo_conexion="frente_tiene_artefacto_externo", tenant=_TENANT
        )
        frentes_out.append({
            "id": f["id"],
            "nombre": (f.get("props") or {}).get("nombre"),
            "estado": (f.get("props") or {}).get("estado"),
            "documentos": [
                {"id": d["id"], "titulo": (d.get("props") or {}).get("titulo"), "modo": (d.get("props") or {}).get("modo"), "estado": (d.get("props") or {}).get("estado")}
                for d in documentos
            ],
            "artefactos_externos": [
                {"id": a["id"], "titulo": (a.get("props") or {}).get("titulo"), "tipo": (a.get("props") or {}).get("tipo"), "url": (a.get("props") or {}).get("url")}
                for a in artefactos
            ],
        })

    pendientes = await _obtener_pendientes_fn(caso_id, tenant=_TENANT, solo_abiertos=False)

    return {
        "id": caso_id,
        "nombre": caso_props.get("nombre"),
        "descripcion": caso_props.get("descripcion"),
        "estadio": caso_props.get("estadio"),
        "fecha_inicio": caso_props.get("fecha_inicio"),
        "participantes": caso_props.get("participantes") or [],
        "frentes": frentes_out,
        "pendientes": [
            {"id": p["id"], "descripcion": (p.get("props") or {}).get("descripcion"), "estado": (p.get("props") or {}).get("estado")}
            for p in pendientes
        ],
    }


@app.get("/documentos/{documento_id}")
async def obtener_documento(documento_id: str) -> dict:
    doc = await motor_api.obtener(documento_id, tenant=_TENANT)
    if not doc or doc.get("tipo") != "documento_caso":
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    props = doc.get("props") or {}
    return {
        "id": documento_id,
        "titulo": props.get("titulo"),
        "modo": props.get("modo"),
        "estado": props.get("estado"),
        "agente": props.get("agente"),
        "contenido": props.get("contenido"),
    }


def _slug_archivo(titulo: str) -> str:
    """'Evaluación — microbiologo' -> 'evaluacion-microbiologo' — nombre de archivo seguro para
    Content-Disposition, sin depender de que el navegador maneje bien acentos/símbolos en headers."""
    normalizado = unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"-+", "-", re.sub(r"[^a-zA-Z0-9]+", "-", normalizado)).strip("-").lower() or "documento"


@app.get("/documentos/{documento_id}/descargar")
async def descargar_documento(documento_id: str) -> Response:
    """
    Descarga el contenido de un documento como archivo `.md` (Etapa 14, 2026-08-17) — Sebas
    pidió poder descargar los informes. Link directo del navegador (`<a href>`, sin fetch/JS), el
    `Content-Disposition: attachment` es lo que dispara la descarga en vez de navegar a la URL.
    """
    doc = await motor_api.obtener(documento_id, tenant=_TENANT)
    if not doc or doc.get("tipo") != "documento_caso":
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    props = doc.get("props") or {}
    contenido = props.get("contenido") or ""
    nombre_archivo = f"{_slug_archivo(props.get('titulo') or 'documento')}.md"
    return Response(
        content=contenido,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )


# ── Adjuntar un archivo al chat (Etapa 17, 2026-08-17) ──────────────────────────
#
# Sebas: "cómo le subo un archivo al conductor? Andrés me pasó información de la composición del
# efluente" — no había ningún camino, ni web ni Conductor. Diseño deliberadamente simple: esto NO
# persiste el archivo en ningún lado (ni el KM ni disco) — solo extrae el texto y lo devuelve. El
# frontend lo suma al próximo mensaje que se manda al chat, como si Sebas lo hubiera tipeado él
# mismo — mismo mecanismo que ya usa el resto del chat (texto plano), sin inventar un tipo de
# contenido nuevo ni una tabla de "archivos" en el KM. Si en algún momento hace falta guardar el
# archivo original (no solo su texto), es una decisión aparte — no la pide el pedido de hoy.
#
# Extracción de PDF: reusa `knowledge_module.document_store.store.extract_text` — ya es genérico
# de plataforma (Capa 0-1), no se reimplica acá. Extracción de .docx/.txt/.md: es igual de
# genérica en espíritu, pero se implementa acá (CRIZA) por ahora — promoverla a `knowledge_module`
# es un buen candidato si otra instancia la necesita (mismo criterio que ya se usó con el motor
# dirigido por objetivo, ver Norte global de CLAUDE.md), no antes de que haga falta de verdad.

_EXTENSIONES_SOPORTADAS = {".pdf", ".docx", ".txt", ".md"}
_MAX_CARACTERES_ARCHIVO = 60_000  # generoso, pero evita mandar un documento gigante en un solo turno


def _extraer_pdf(contenido: bytes) -> str:
    # NamedTemporaryFile(delete=True) + reabrir el mismo path desde otro handle falla en Windows
    # por el locking del sistema de archivos — confirmado al mano. delete=False + unlink manual
    # en el finally evita ese problema.
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(contenido)
        tmp_path = Path(tmp.name)
    try:
        return _extraer_texto_pdf_de_path(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


def _extraer_docx(contenido: bytes) -> str:
    documento = docx.Document(io.BytesIO(contenido))
    return "\n".join(p.text for p in documento.paragraphs if p.text.strip())


@app.post("/archivos/extraer")
async def extraer_texto_archivo(archivo: UploadFile = File(...)) -> dict:
    ext = Path(archivo.filename or "").suffix.lower()
    if ext not in _EXTENSIONES_SOPORTADAS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato no soportado ({ext or 'sin extensión'}). Soportados: PDF, Word (.docx), texto (.txt/.md).",
        )

    contenido = await archivo.read()

    if ext == ".pdf":
        texto = _extraer_pdf(contenido)
    elif ext == ".docx":
        texto = _extraer_docx(contenido)
    else:
        texto = contenido.decode("utf-8", errors="replace")

    if not texto.strip():
        raise HTTPException(status_code=422, detail="No se pudo extraer texto del archivo (¿es un escaneo sin capa de texto?).")

    truncado = len(texto) > _MAX_CARACTERES_ARCHIVO
    if truncado:
        texto = texto[:_MAX_CARACTERES_ARCHIVO]

    return {"nombre_archivo": archivo.filename, "texto": texto, "truncado": truncado}


def _mensajes_a_turnos(mensajes: list[dict], rol_agente: str) -> list[dict]:
    """
    Reconstruye los turnos VISIBLES (lo que se ve en el chat) a partir de los `mensajes` crudos
    guardados en el KM (Etapa 16, 2026-08-17) — esos incluyen los pasos intermedios de tool-use/
    tool-result que nunca se le mostraron a Sebas en pantalla, así que hace falta filtrarlos, no
    solo reproducir la lista tal cual.

    Un mensaje "user" con `content` string es un turno real de Sebas (lo que arma
    `enviar_mensaje()` en cada agente); con `content` lista es un envoltorio de `tool_result`, se
    descarta. Un mensaje "assistant" es la respuesta final del turno solo si NINGÚN bloque es
    `tool_use` — si los tiene, es un paso intermedio del loop de tools, se descarta.
    """
    turnos = []
    for m in mensajes:
        content = m.get("content")
        if m.get("role") == "user":
            if isinstance(content, str):
                turnos.append({"rol": "vos", "texto": content})
        elif m.get("role") == "assistant":
            bloques = content if isinstance(content, list) else []
            if any(b.get("type") == "tool_use" for b in bloques):
                continue
            texto = "".join(b.get("text", "") for b in bloques if b.get("type") == "text")
            if texto:
                turnos.append({"rol": rol_agente, "texto": texto})
    return turnos


def _resumen_sesion(sesion: dict, rol_agente: str) -> dict | None:
    """None si la sesión no tiene ningún turno visible todavía (sesión recién creada, abandonada
    sin mandar mensaje) — no tiene sentido listarla en el historial."""
    props = sesion.get("props") or {}
    turnos = _mensajes_a_turnos(props.get("mensajes") or [], rol_agente)
    if not turnos:
        return None
    primer_texto = turnos[0]["texto"]
    return {
        "id": sesion["id"],
        "iniciada_en": props.get("iniciada_en"),
        "actualizada_en": props.get("actualizada_en"),
        "primer_mensaje": primer_texto[:140] + "…" if len(primer_texto) > 140 else primer_texto,
        "modelo": props.get("modelo"),
    }


# ── Chat del Conductor ────────────────────────────────────────────────────────

class _MensajeIn(BaseModel):
    texto: str


class _CrearSesionConductorIn(BaseModel):
    # Opcional (Etapa 15, 2026-08-17) — elegir modelo por sesión de chat. None = default del
    # agente (env var CONDUCTOR_MODEL). Ver utils/ai_client.py::MODELOS_DISPONIBLES.
    modelo: str | None = None


@app.post("/conductor/sesiones")
async def crear_sesion_conductor(body: _CrearSesionConductorIn | None = None) -> dict:
    # load_plantilla es idempotente (upsert) — correrlo acá evita depender de un paso de setup
    # manual aparte; el costo (una query extra) es despreciable comparado con lo que sigue
    # (llamadas al modelo de varios segundos).
    await load_plantilla(str(_PLANTILLA_SESIONES), tenant=_TENANT)

    ahora = datetime.now(timezone.utc).isoformat()
    resultado = await motor_api.guardar_ficha(
        area="conductor_sesiones", tipo="sesion", tenant=_TENANT,
        campos={"mensajes": [], "iniciada_en": ahora, "actualizada_en": ahora, "modelo": body.modelo if body else None},
    )
    if not resultado.get("success"):
        raise HTTPException(status_code=500, detail=f"No se pudo crear la sesión: {resultado.get('error')}")
    return {"session_id": resultado["id"]}


@app.get("/conductor/sesiones")
async def listar_sesiones_conductor() -> list[dict]:
    """
    Historial de conversaciones con el Conductor (Etapa 16, 2026-08-17) — bug real: Sebas volvió
    a `/conductor` más tarde y la respuesta que había recibido "desapareció". Causa: la página
    creaba una sesión nueva en cada carga y nunca guardaba el `session_id` en ningún lado del
    browser — la conversación anterior seguía intacta en el KM, pero no había forma de volver a
    encontrarla desde la web. Esta lista es la mitad "encontrarla" del fix (la otra mitad es
    recordar la sesión activa, ver `web/app/conductor/page.tsx`).
    """
    sesiones = await motor_api.listar(area="conductor_sesiones", tipo="sesion", limit=200, tenant=_TENANT)
    resumenes = [r for s in sesiones if (r := _resumen_sesion(s, "conductor")) is not None]
    resumenes.sort(key=lambda r: r["actualizada_en"] or "", reverse=True)
    return resumenes


@app.get("/conductor/sesiones/{session_id}")
async def obtener_sesion_conductor(session_id: str) -> dict:
    try:
        sesion = await motor_api.obtener(session_id, tenant=_TENANT)
    except Exception:
        sesion = None
    if not sesion or sesion.get("tipo") != "sesion":
        raise HTTPException(status_code=404, detail="Sesión no encontrada")

    props = sesion.get("props") or {}
    return {
        "id": session_id,
        "modelo": props.get("modelo"),
        "turnos": _mensajes_a_turnos(props.get("mensajes") or [], "conductor"),
    }


@app.post("/conductor/sesiones/{session_id}/mensajes")
async def enviar_mensaje_conductor(session_id: str, body: _MensajeIn) -> dict:
    if not body.texto.strip():
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío")

    try:
        sesion = await motor_api.obtener(session_id, tenant=_TENANT)
    except Exception:
        sesion = None  # session_id no es un UUID válido — mismo resultado que "no encontrada"
    if not sesion or sesion.get("tipo") != "sesion":
        raise HTTPException(status_code=404, detail="Sesión no encontrada — crear una nueva con POST /conductor/sesiones")

    props = sesion.get("props") or {}
    messages = props.get("mensajes") or []
    kwargs_modelo = {"model": props["modelo"]} if props.get("modelo") else {}
    respuesta, messages = await _enviar_mensaje_conductor(messages, body.texto, **kwargs_modelo)

    await motor_api.actualizar_props(
        session_id,
        {
            "mensajes": _serializar_mensajes(messages),
            "actualizada_en": datetime.now(timezone.utc).isoformat(),
        },
        tenant=_TENANT,
    )

    return {"respuesta": respuesta}


@app.post("/conductor/sesiones/{session_id}/cerrar")
async def cerrar_sesion_conductor(session_id: str) -> dict:
    """
    Llamar cuando Sebas termina una conversación (ej. arranca una nueva desde la web) — evalúa
    si la sesión dejó una lección de dominio nueva y, si sí, la guarda al KM (Etapa 9, ver
    docs/DESIGN_GATE.md). Idempotente en la práctica: llamarla dos veces sobre la misma sesión
    no duplica nada porque la segunda evaluación ve la lección que la primera ya guardó (vía
    `aprendizaje.leer_lecciones_caso`) y la reconoce como ya cubierta.
    """
    try:
        sesion = await motor_api.obtener(session_id, tenant=_TENANT)
    except Exception:
        sesion = None
    if not sesion or sesion.get("tipo") != "sesion":
        raise HTTPException(status_code=404, detail="Sesión no encontrada")

    messages = (sesion.get("props") or {}).get("mensajes") or []
    leccion = await _cerrar_sesion_conductor(messages, tenant=_TENANT)
    return {"leccion_guardada": leccion is not None, "id": leccion.get("id") if leccion else None}


# ── Chat con un especialista puntual (Etapa 10, 2026-08-16) ────────────────────
#
# Distinto del chat del Conductor: acá Sebas habla directo con un especialista sobre un frente
# concreto — mismo conocimiento/herramientas que la corrida formal de un turno, pero sin producir
# un documento_caso (eso sigue siendo exclusivo del camino de un turno vía la costura — ver
# <especialista>_agent.py::TOOLS_CHAT, que excluye submit_evaluacion_tecnica a propósito).

class _CrearSesionEspecialistaIn(BaseModel):
    # Opcional (Etapa 12, 2026-08-16) — "consulta libre": Sebas pidió poder preguntarle algo
    # puntual a un especialista sin necesitar un caso/frente ya creado, y sin pagar el costo de
    # armar ese contexto. Sin frente_id, la sesión arranca vacía (ver <especialista>.enviar_mensaje).
    frente_id: str | None = None
    # Opcional (Etapa 15, 2026-08-17) — elegir modelo por sesión. None = default del agente.
    modelo: str | None = None


@app.post("/especialistas/{nombre}/sesiones")
async def crear_sesion_especialista(nombre: str, body: _CrearSesionEspecialistaIn) -> dict:
    if nombre not in _ESPECIALISTAS_CHAT:
        raise HTTPException(status_code=404, detail=f"'{nombre}' no es un especialista disponible. Opciones: {list(_ESPECIALISTAS_CHAT.keys())}.")
    modulo = _ESPECIALISTAS_CHAT[nombre]

    if body.frente_id:
        try:
            mensajes_iniciales = await modulo.iniciar_sesion(body.frente_id, tenant=_TENANT)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
    else:
        mensajes_iniciales = []  # consulta libre — nada de contexto de caso que armar

    await load_plantilla(str(_PLANTILLA_SESIONES_ESPECIALISTA), tenant=_TENANT)
    ahora = datetime.now(timezone.utc).isoformat()
    resultado = await motor_api.guardar_ficha(
        area="especialista_sesiones", tipo="sesion_especialista", tenant=_TENANT,
        campos={
            "especialista": nombre,
            "frente_id": body.frente_id,
            "mensajes": _serializar_mensajes(mensajes_iniciales),
            "iniciada_en": ahora,
            "actualizada_en": ahora,
            "modelo": body.modelo,
        },
    )
    if not resultado.get("success"):
        raise HTTPException(status_code=500, detail=f"No se pudo crear la sesión: {resultado.get('error')}")
    return {"session_id": resultado["id"]}


@app.get("/especialistas/sesiones")
async def listar_sesiones_especialista(especialista: str) -> list[dict]:
    """Historial de conversaciones con un especialista puntual (Etapa 16) — mismo fix que
    `GET /conductor/sesiones`, mismo bug. Incluye todas las sesiones de ese especialista, con o
    sin `frente_id` (consulta libre o sobre un caso)."""
    if especialista not in _ESPECIALISTAS_CHAT:
        raise HTTPException(status_code=404, detail=f"'{especialista}' no es un especialista disponible. Opciones: {list(_ESPECIALISTAS_CHAT.keys())}.")
    sesiones = await motor_api.listar(
        area="especialista_sesiones", tipo="sesion_especialista",
        contiene={"especialista": especialista}, limit=200, tenant=_TENANT,
    )
    resumenes = []
    for s in sesiones:
        resumen = _resumen_sesion(s, "especialista")
        if resumen is None:
            continue
        resumen["frente_id"] = (s.get("props") or {}).get("frente_id")
        resumenes.append(resumen)
    resumenes.sort(key=lambda r: r["actualizada_en"] or "", reverse=True)
    return resumenes


@app.get("/especialistas/sesiones/{session_id}")
async def obtener_sesion_especialista(session_id: str) -> dict:
    try:
        sesion = await motor_api.obtener(session_id, tenant=_TENANT)
    except Exception:
        sesion = None
    if not sesion or sesion.get("tipo") != "sesion_especialista":
        raise HTTPException(status_code=404, detail="Sesión no encontrada")

    props = sesion.get("props") or {}
    return {
        "id": session_id,
        "especialista": props.get("especialista"),
        "frente_id": props.get("frente_id"),
        "modelo": props.get("modelo"),
        "turnos": _mensajes_a_turnos(props.get("mensajes") or [], "especialista"),
    }


@app.post("/especialistas/sesiones/{session_id}/mensajes")
async def enviar_mensaje_especialista(session_id: str, body: _MensajeIn) -> dict:
    if not body.texto.strip():
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío")

    try:
        sesion = await motor_api.obtener(session_id, tenant=_TENANT)
    except Exception:
        sesion = None
    if not sesion or sesion.get("tipo") != "sesion_especialista":
        raise HTTPException(status_code=404, detail="Sesión no encontrada — crear una nueva con POST /especialistas/{nombre}/sesiones")

    props = sesion.get("props") or {}
    nombre = props.get("especialista")
    modulo = _ESPECIALISTAS_CHAT[nombre]  # nombre siempre válido — se validó al crear la sesión

    messages = props.get("mensajes") or []
    kwargs_modelo = {"model": props["modelo"]} if props.get("modelo") else {}
    respuesta, messages = await modulo.enviar_mensaje(messages, body.texto, props.get("frente_id"), **kwargs_modelo)

    await motor_api.actualizar_props(
        session_id,
        {"mensajes": _serializar_mensajes(messages), "actualizada_en": datetime.now(timezone.utc).isoformat()},
        tenant=_TENANT,
    )
    return {"respuesta": respuesta}


# ── Características de un agente (Etapa 11, 2026-08-16) ────────────────────────
#
# "¿Qué puede hacer este agente y a qué herramientas está conectado?" — leído en vivo desde
# TOOLS/SYSTEM_PROMPT de cada módulo, no desde un doc paralelo que se desincroniza: si mañana se
# suma o saca una tool, esto se actualiza solo, porque es la MISMA lista que el agente usa para
# operar (ver TOOLS_CHAT más arriba — no una copia).

@app.get("/agentes/{nombre}")
async def obtener_info_agente(nombre: str) -> dict:
    if nombre not in _AGENTES_INFO:
        raise HTTPException(status_code=404, detail=f"'{nombre}' no es un agente disponible. Opciones: {list(_AGENTES_INFO.keys())}.")
    modulo = _AGENTES_INFO[nombre]

    tools = getattr(modulo, "TOOLS", None) or []
    # El Conductor no tiene TOOLS_CHAT (no distingue chat de "corrida formal", es 100% chat) —
    # todas sus tools son "de chat" por default.
    nombres_chat = {t["name"] for t in getattr(modulo, "TOOLS_CHAT", tools)}

    return {
        "nombre": nombre,
        "system_prompt": modulo.SYSTEM_PROMPT,
        "tools": [
            {
                "name": t["name"],
                "description": t["description"],
                "disponible_en_chat": t["name"] in nombres_chat,
            }
            for t in tools
        ],
    }
