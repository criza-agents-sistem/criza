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

Sesiones de chat en memoria del proceso (`_sesiones_conductor`) — suficiente para un solo
usuario local (Sebas), sin necesidad de un store persistente todavía. Se pierden si se reinicia
el server — aceptado como límite de v1, no un caso de uso que hoy lo necesite.

Ver docs/DESIGN_GATE.md — decisiones A-D (2026-08-16).
"""

import sys
import uuid
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
from utils.casos import (
    listar_casos as _listar_casos_fn,
    obtener_frentes_de_caso as _obtener_frentes_fn,
    obtener_documentos_de_frente as _obtener_documentos_fn,
    obtener_pendientes_de_caso as _obtener_pendientes_fn,
)
from conductor import enviar_mensaje as _enviar_mensaje_conductor

_TENANT = "criza"

app = FastAPI(title="CRIZA API", description="API para la app web (Etapa 6) — casos de solo lectura + chat del Conductor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── Sesiones de chat del Conductor (en memoria del proceso) ────────────────────
_sesiones_conductor: dict[str, list[dict]] = {}


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
    session_id = str(uuid.uuid4())
    _sesiones_conductor[session_id] = []
    return {"session_id": session_id}


@app.post("/conductor/sesiones/{session_id}/mensajes")
async def enviar_mensaje_conductor(session_id: str, body: _MensajeIn) -> dict:
    if session_id not in _sesiones_conductor:
        raise HTTPException(status_code=404, detail="Sesión no encontrada — crear una nueva con POST /conductor/sesiones")
    if not body.texto.strip():
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío")

    messages = _sesiones_conductor[session_id]
    respuesta, messages = await _enviar_mensaje_conductor(messages, body.texto)
    _sesiones_conductor[session_id] = messages

    return {"respuesta": respuesta}
