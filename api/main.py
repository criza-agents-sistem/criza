"""
API — CRIZA (Etapa 6 del plan de construcción, 2026-08-16; chat del Conductor sumado el mismo
día, v1.2 adelantada a pedido de Sebas)

Backend delgado para la app Next.js (`web/`) — reusa `knowledge_module`/`utils/casos.py` y
`conductor/conductor.py` directo, sin lógica duplicada.

Dos superficies distintas, cada una con su propia relación con producción/staging:
- `/casos`, `/casos/{id}`, `/documentos/{id}` — solo lectura, GET, leen `DATABASE_URL`
  (producción) sin riesgo de escritura.
- `/conductor/*` — el Conductor SÍ puede escribir al KM cuando invoca un especialista
  (`correr_especialista`, vía la costura) — usa la misma `DATABASE_URL` que el resto del proceso
  (producción por default). Sebas es dueño de decidir qué corridas promueve, igual que con
  cualquier otro cliente de la costura.

Sesiones de chat del Conductor persistidas en el KM (área `conductor_sesiones`, plantilla
`config/plantillas/conductor_sesiones.yaml`) — no en memoria del proceso. Sebas preguntó
explícitamente cómo resolver que se perdían al reiniciar `api/run.py`; la respuesta es la misma
que ya usa todo lo demás en este proyecto (`pipeline_status`, `token_usage`): el KM, no un
archivo local nuevo (CLAUDE.md: "si el output de un agente no está en el KM, no existe para el
sistema"). `session_id` que ve el browser es directamente el id de la ficha — no hay un id
separado que mantener sincronizado.

Ver docs/DESIGN_GATE.md — decisiones A-E (2026-08-16).
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

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

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from knowledge_module.motor import api as motor_api
from knowledge_module.motor.loader import load_plantilla
from utils.casos import (
    listar_casos as _listar_casos_fn,
    obtener_frentes_de_caso as _obtener_frentes_fn,
    obtener_documentos_de_frente as _obtener_documentos_fn,
    obtener_pendientes_de_caso as _obtener_pendientes_fn,
)
from conductor import enviar_mensaje as _enviar_mensaje_conductor, serializar_mensajes as _serializar_mensajes_conductor

_TENANT = "criza"
_PLANTILLA_SESIONES = _CRIZA_DIR / "config" / "plantillas" / "conductor_sesiones.yaml"

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


# ── Chat del Conductor ────────────────────────────────────────────────────────

class _MensajeIn(BaseModel):
    texto: str


@app.post("/conductor/sesiones")
async def crear_sesion_conductor() -> dict:
    # load_plantilla es idempotente (upsert) — correrlo acá evita depender de un paso de setup
    # manual aparte; el costo (una query extra) es despreciable comparado con lo que sigue
    # (llamadas al modelo de varios segundos).
    await load_plantilla(str(_PLANTILLA_SESIONES), tenant=_TENANT)

    ahora = datetime.now(timezone.utc).isoformat()
    resultado = await motor_api.guardar_ficha(
        area="conductor_sesiones", tipo="sesion", tenant=_TENANT,
        campos={"mensajes": [], "iniciada_en": ahora, "actualizada_en": ahora},
    )
    if not resultado.get("success"):
        raise HTTPException(status_code=500, detail=f"No se pudo crear la sesión: {resultado.get('error')}")
    return {"session_id": resultado["id"]}


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

    messages = (sesion.get("props") or {}).get("mensajes") or []
    respuesta, messages = await _enviar_mensaje_conductor(messages, body.texto)

    await motor_api.actualizar_props(
        session_id,
        {
            "mensajes": _serializar_mensajes_conductor(messages),
            "actualizada_en": datetime.now(timezone.utc).isoformat(),
        },
        tenant=_TENANT,
    )

    return {"respuesta": respuesta}
