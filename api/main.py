"""
API de solo lectura — CRIZA (Etapa 6 del plan de construcción, 2026-08-16)

Backend delgado para la app Next.js (`web/`) — reusa `knowledge_module`/`utils/casos.py`
directo, sin lógica de queries duplicada. Solo GET, nada escribe. Lee contra `DATABASE_URL`
(producción) — de solo lectura, sin riesgo de escritura, no hace falta staging acá (a diferencia
de la Etapa 4).

Ver docs/DESIGN_GATE.md — decisiones A-C (2026-08-16).
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

_API_DIR = Path(__file__).parent
_CRIZA_DIR = _API_DIR.parent
sys.path.insert(0, str(_CRIZA_DIR))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from knowledge_module.motor import api as motor_api
from utils.casos import (
    listar_casos as _listar_casos_fn,
    obtener_frentes_de_caso as _obtener_frentes_fn,
    obtener_documentos_de_frente as _obtener_documentos_fn,
    obtener_pendientes_de_caso as _obtener_pendientes_fn,
)

_TENANT = "criza"

app = FastAPI(title="CRIZA API", description="API de solo lectura para la app web (Etapa 6)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET"],
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
