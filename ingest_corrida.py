"""
Ingesta de corridas al Knowledge Module.

Uso principal: llamado automáticamente al terminar una corrida en test_metodologia.py.
También se puede usar standalone para ingestar outputs históricos:

    python ingest_corrida.py <archivo_output.md> <sector>

Hace dos cosas:
1. Guarda la Corrida (metadatos de ejecución)
2. Extrae las oportunidades del output markdown y guarda cada una como Oportunidad
"""

import asyncio
import json
import sys as _sys
if hasattr(_sys.stdout, "reconfigure") and _sys.stdout.encoding != "utf-8":
    _sys.stdout.reconfigure(encoding="utf-8")
import os
import sys
from pathlib import Path
from datetime import date

from dotenv import load_dotenv

# Config: DATABASE_URL/EMBEDDING_* del KM + ANTHROPIC_API_KEY, todo en el .env propio de criza/
# (el paquete knowledge_module no lee ningún .env propio — ver knowledge_module/auditor/__main__.py).
_criza_dir = Path(__file__).parent
load_dotenv(_criza_dir / ".env", override=True)

import anthropic
from km_tools.store import store_corrida, store_document, store_opportunity, store_learning


# ── Extracción de oportunidades ──────────────────────────────────────────────

EXTRACTION_PROMPT = """\
Sos un extractor de datos estructurados. Se te va a pasar el output de un agente de búsqueda
de oportunidades de transferencia tecnológica (blue ocean). Tu tarea es extraer la lista de
oportunidades y devolverla como JSON puro, sin texto adicional.

Formato de output (JSON array):
[
  {
    "idea": "descripción concisa de la oportunidad (1-2 oraciones, máximo 200 caracteres)",
    "prioridad": "alta" | "media" | "baja",
    "gaps_pendientes": "qué falta validar o qué es incierto (1-2 oraciones, puede ser null)"
  },
  ...
]

Reglas:
- Si el output tiene secciones "Oportunidad N", "Candidato", "Ficha" o similar, extraé cada una.
- La "idea" debe ser auto-contenida: debe entenderse sin leer el informe completo.
- La "prioridad" debe inferirse del texto (palabras como "urgente", "alto potencial", "moderado", etc.).
  Si no hay señal clara, usá "media".
- "gaps_pendientes" = lo que el agente marcó como incierto, pendiente de validar, o pregunta abierta.
- Si no encontrás oportunidades claras, devolvé [].
- Devolvé SOLO el JSON, sin markdown, sin explicaciones.
"""


def extract_opportunities_from_output(output_text: str, sector: str) -> list[dict]:
    """
    Usa Claude para extraer oportunidades estructuradas del output del agente divergente.
    Devuelve lista de dicts con keys: idea, prioridad, gaps_pendientes
    """
    client = anthropic.Anthropic()
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5",  # modelo barato para extracción
            max_tokens=4096,
            system=EXTRACTION_PROMPT,
            messages=[{
                "role": "user",
                "content": f"Sector: {sector}\n\n---\n\n{output_text[:12000]}"  # cap para no exceder contexto
            }]
        )
        raw = resp.content[0].text.strip()
        # Limpiar posible markdown code block
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as e:
        print(f"  [KM] Advertencia: no se pudo extraer oportunidades del output: {e}")
        return []


# ── Función principal de ingesta ─────────────────────────────────────────────

async def _ingest_async(
    sector: str,
    agente: str,
    modo: str,
    fecha: str,
    modelo: str,
    output_text: str,
    tokens_input: int = None,
    tokens_output: int = None,
    costo_usd: float = None,
    notas: str = None,
    verbose: bool = True,
) -> dict:
    """Guarda la corrida y sus oportunidades en el Knowledge Module."""

    if verbose:
        print(f"\n  [KM] Ingesta de corrida — sector: {sector}")

    # 1. Guardar corrida
    corrida_result = await store_corrida(
        sector=sector,
        agente=agente,
        modo=modo,
        fecha=fecha,
        modelo=modelo,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        costo_usd=costo_usd,
        notas=notas,
    )

    if not corrida_result["success"]:
        print(f"  [KM] ERROR al guardar corrida: {corrida_result['error']}")
        return corrida_result

    corrida_id = corrida_result["data"]["id"]
    if verbose:
        print(f"  [KM] Corrida guardada: {corrida_id}")

    # 2. Guardar el output completo como Documento (capa de contenido completo)
    doc_result = await store_document(
        corrida_id=corrida_id,
        contenido=output_text,
        sector=sector,
        agente=agente,
        fecha=fecha,
        modelo=modelo,
        tipo="analisis",
        titulo=f"{agente.capitalize()} — {sector} — {fecha}",
    )
    if verbose:
        if doc_result["success"]:
            print(f"  [KM] Documento guardado: {doc_result['data']['id']}")
        else:
            print(f"  [KM] Advertencia: no se pudo guardar el Documento: {doc_result['error']}")

    # 3. Extraer oportunidades del output
    if verbose:
        print(f"  [KM] Extrayendo oportunidades del output...")

    opportunities = extract_opportunities_from_output(output_text, sector)
    if verbose:
        print(f"  [KM] {len(opportunities)} oportunidades detectadas")

    # 4. Guardar cada oportunidad
    stored = []
    for op in opportunities:
        result = await store_opportunity(
            sector=sector,
            idea=op.get("idea", ""),
            prioridad=op.get("prioridad", "media"),
            origen="agente",
            corrida_id=corrida_id,
            gaps_pendientes=op.get("gaps_pendientes"),
        )
        action = result.get("data", {}).get("action", "?") if result["success"] else "ERROR"
        if verbose:
            idea_short = op.get("idea", "")[:60]
            print(f"  [KM]   → {action}: {idea_short}...")
        stored.append(result)

    return {
        "corrida_id": corrida_id,
        "documento_id": doc_result["data"]["id"] if doc_result["success"] else None,
        "oportunidades_total": len(opportunities),
        "oportunidades_guardadas": sum(1 for r in stored if r["success"]),
    }


def km_ingest(
    sector: str,
    agente: str,
    modo: str,
    fecha: str,
    modelo: str,
    output_text: str,
    tokens_input: int = None,
    tokens_output: int = None,
    costo_usd: float = None,
    notas: str = None,
    verbose: bool = True,
) -> dict:
    """
    Punto de entrada sincrónico. Llama desde test_metodologia.py o cualquier runner.

    Ejemplo:
        from knowledge_module.ingest_corrida import km_ingest
        km_ingest(sector="ganadería", agente="divergente", modo="A",
                  fecha="2026-06-09", modelo="claude-sonnet-4-6",
                  output_text=out, tokens_input=usage["input"],
                  tokens_output=usage["output"], costo_usd=cost)
    """
    # Resetear engine antes de asyncio.run() para no quedar pegado al loop anterior
    from knowledge_module.db import reset_engine
    reset_engine()

    return asyncio.run(_ingest_async(
        sector=sector, agente=agente, modo=modo, fecha=fecha, modelo=modelo,
        output_text=output_text, tokens_input=tokens_input, tokens_output=tokens_output,
        costo_usd=costo_usd, notas=notas, verbose=verbose,
    ))


# ── CLI para ingestar outputs históricos ─────────────────────────────────────

if __name__ == "__main__":
    """
    Uso: python ingest_corrida.py <ruta_output.md> "<sector>"

    Ejemplo:
        python ingest_corrida.py ../criza/divergent_agent/outputs/test_metodologia_ganaderia_2026-06-08.md "ganadería de Córdoba, Argentina"
    """
    if len(sys.argv) < 3:
        print("Uso: python ingest_corrida.py <archivo_output.md> '<sector>'")
        sys.exit(1)

    fp = Path(sys.argv[1])
    sector_arg = sys.argv[2]

    if not fp.exists():
        print(f"Archivo no encontrado: {fp}")
        sys.exit(1)

    output_text = fp.read_text(encoding="utf-8")

    # Inferir fecha del nombre del archivo (formato: ..._YYYY-MM-DD.md o ..._YYYY-MM-DD_N.md)
    stem = fp.stem  # e.g. test_metodologia_ganaderia_2026-06-08
    fecha_inferred = date.today().isoformat()
    parts = stem.split("_")
    for i, p in enumerate(parts):
        if len(p) == 10 and p[4] == "-" and p[7] == "-":
            fecha_inferred = p
            break

    print(f"Ingesta de: {fp.name}")
    print(f"Sector: {sector_arg}")
    print(f"Fecha inferida: {fecha_inferred}")

    result = km_ingest(
        sector=sector_arg,
        agente="divergente",
        modo="A",
        fecha=fecha_inferred,
        modelo="claude-sonnet-4-6",
        output_text=output_text,
        notas=f"Ingesta histórica desde archivo: {fp.name}",
    )

    print(f"\nResultado: {result}")
