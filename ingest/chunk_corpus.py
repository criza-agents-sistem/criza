"""
chunk_corpus.py — cierra el hallazgo P13 (auditoría de cumplimiento 2026-07-05) para el
área corpus_cientifico: texto_completo truncado a 60.000 caracteres + texto completo no
buscable por fragmento.

Dos pasos, en orden (el primero es prerequisito del segundo):

  1. Backfill de texto_completo — para las fichas 'fuente' donde texto_completo quedó
     truncado por el cap viejo (removido en esta sesión de knowledge_module/ingesta/
     download_corpus_pdfs.py y criza/ingest/download_pdfs.py), re-extrae el texto completo
     desde el PDF ya en disco (plataforma/document_store — sin volver a descargar nada) y
     actualiza la ficha.

  2. Chunking — para toda ficha 'fuente' con texto_completo, genera sus fragmentos
     (knowledge_module/motor/chunking.py, ~500 tokens/50 overlap) como fichas 'fuente_chunk'
     conectadas por 'chunk_de' (schema agregado a corpus_cientifico.yaml en esta sesión,
     mismo patrón que dpn-normativo/config/plantillas/normativa_dpn.yaml::norma_chunk).
     Idempotente: salta fichas que ya tienen conexiones chunk_de entrantes.

Uso:
    python criza/ingest/chunk_corpus.py --dry-run
    python criza/ingest/chunk_corpus.py                      # backfill + chunking, todo
    python criza/ingest/chunk_corpus.py --limit 20            # prueba rápida
    python criza/ingest/chunk_corpus.py --solo-backfill-texto
    python criza/ingest/chunk_corpus.py --solo-chunking
    python criza/ingest/chunk_corpus.py --repositorio INTA
"""

import argparse
import asyncio
import sys
from pathlib import Path

_CRIZA = Path(__file__).parent.parent
if str(_CRIZA) not in sys.path:
    sys.path.insert(0, str(_CRIZA))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Transicional: mientras CRIZA siga en el árbol de EMPRESAS-IA, la conexión al KM vive en
# knowledge_module/.env — cuando CRIZA salga del árbol tendrá su propio .env.
from dotenv import load_dotenv
load_dotenv(_CRIZA.parent / "knowledge_module" / ".env")

from sqlalchemy import text as sa_text

from knowledge_module.db import get_session_factory, reset_engine
from knowledge_module.motor import api as motor_api
from knowledge_module.motor.loader import load_plantilla
from knowledge_module.motor.chunking import chunk_texto
from knowledge_module.ingesta.download_corpus_pdfs import _sanitize
from knowledge_module.document_store.store import pdf_path, extract_text

_PLANTILLA = _CRIZA / "config" / "plantillas" / "corpus_cientifico.yaml"
_TENANT = "criza"
_INSTANCE = "criza"

# Umbral para detectar texto truncado por el cap viejo (60_000 exacto). Un poco por debajo
# porque _sanitize puede recortar algún carácter suelto (surrogates) cerca del borde.
_UMBRAL_TRUNCADO = 59_999


# ── Paso 1: backfill de texto_completo ──────────────────────────────────────────

async def _fichas_truncadas(repositorio: str | None, limit: int | None) -> list[dict]:
    where_repo = "AND f.props->>'repositorio' = :repo" if repositorio else ""
    lim = "LIMIT :lim" if limit else ""
    params: dict = {"t": _TENANT, "umbral": _UMBRAL_TRUNCADO}
    if repositorio:
        params["repo"] = repositorio
    if limit:
        params["lim"] = limit
    async with get_session_factory()() as s:
        r = await s.execute(sa_text(f"""
            SELECT f.id::text, f.props->>'pdf_url' AS pdf_url, f.props->>'url' AS url,
                   f.props->>'repositorio' AS repositorio, f.props->>'titulo' AS titulo
            FROM ficha f
            JOIN tipo_ficha tf ON tf.id = f.tipo_ficha_id
            JOIN area a ON a.id = tf.area_id
            WHERE a.nombre = 'corpus_cientifico' AND a.tenant_id = :t AND tf.nombre = 'fuente'
              AND length(f.props->>'texto_completo') >= :umbral
              {where_repo}
            ORDER BY f.created_at DESC
            {lim}
        """), params)
        return [dict(row._mapping) for row in r.fetchall()]


async def _resolver_pdf_url_inta(fichas: list[dict], set_id: str = "civcya") -> dict[str, str]:
    """
    migrate_inta_to_corpus.py (2026-07-02) nunca copió pdf_url a la ficha migrada — solo 'url'
    (la landing page hdl.handle.net). Sin esto, las fichas INTA truncadas no tienen forma de
    ubicar su PDF cacheado en disco. Resuelve en dos pasos, igual que
    criza/ingest/download_pdfs.py:
      1. Metadata OAI-PMH (_build_pdf_map) — rápido, sin requests extra.
      2. Para lo que queda sin resolver: scraping de la página INTA (get_pdf_url), igual que
         el flag --scrape-missing de download_pdfs.py — la mayoría de los PDFs de INTA no
         están en la metadata OAI-PMH directamente, solo se encuentran scrapeando el handle.

    Devuelve {ficha_id: pdf_url} solo para las que se pudieron resolver.
    """
    import time
    from utils.inta import harvest, get_pdf_url

    print(f"  Re-cosechando metadata INTA ('{set_id}') para resolver pdf_url faltantes...")
    records = harvest(set_id)
    pdf_map = {r.get("handle_url"): r.get("pdf_url") for r in records
               if r.get("handle_url") and r.get("pdf_url")}

    resueltos: dict[str, str] = {}
    pendientes: list[dict] = []
    for ficha in fichas:
        url = ficha.get("url")
        if url and url in pdf_map:
            resueltos[ficha["id"]] = pdf_map[url]
        else:
            pendientes.append(ficha)
    print(f"  {len(resueltos)}/{len(fichas)} pdf_url resueltos vía metadata OAI-PMH")

    if pendientes:
        print(f"  Scrapeando {len(pendientes)} páginas INTA para el resto (igual que --scrape-missing)...")
        for i, ficha in enumerate(pendientes, 1):
            url = ficha.get("url")
            if not url:
                continue
            handle_id = url.replace("https://hdl.handle.net/", "").replace("http://hdl.handle.net/", "").strip("/")
            time.sleep(0.5)
            pdf_url = get_pdf_url(handle_id)
            if pdf_url:
                resueltos[ficha["id"]] = pdf_url
            if i % 50 == 0:
                print(f"    scrapeadas {i}/{len(pendientes)}")
        print(f"  {len(resueltos)}/{len(fichas)} pdf_url resueltos en total (metadata + scraping)")

    return resueltos


async def backfill_texto_completo(dry_run: bool, repositorio: str | None, limit: int | None) -> dict:
    stats = {"candidatas": 0, "actualizadas": 0, "sin_pdf_url": 0, "sin_pdf_en_disco": 0,
              "sin_texto_extraible": 0}

    fichas = await _fichas_truncadas(repositorio, limit)
    stats["candidatas"] = len(fichas)
    print(f"Backfill texto_completo — {len(fichas)} fichas truncadas encontradas")

    faltantes_inta = [f for f in fichas if not f.get("pdf_url") and f.get("repositorio") == "INTA"]
    pdf_url_resueltos = await _resolver_pdf_url_inta(faltantes_inta) if faltantes_inta else {}

    for i, ficha in enumerate(fichas, 1):
        pdf_url = ficha.get("pdf_url") or pdf_url_resueltos.get(ficha["id"])
        titulo = (ficha.get("titulo") or "")[:60]

        if not pdf_url:
            stats["sin_pdf_url"] += 1
            print(f"  [{i}/{len(fichas)}] sin pdf_url resoluble — {titulo}")
            continue

        p = pdf_path(pdf_url, _INSTANCE)
        if not p:
            stats["sin_pdf_en_disco"] += 1
            print(f"  [{i}/{len(fichas)}] PDF no está en disco — {titulo}")
            continue

        texto = extract_text(p)
        if not texto.strip():
            stats["sin_texto_extraible"] += 1
            print(f"  [{i}/{len(fichas)}] sin texto extraíble — {titulo}")
            continue

        texto_limpio = _sanitize(texto)
        cambios = {"texto_completo": texto_limpio}
        if not ficha.get("pdf_url"):
            cambios["pdf_url"] = pdf_url  # persistir el pdf_url resuelto — cierra el gap para el futuro

        if dry_run:
            print(f"  DRY [{i}/{len(fichas)}] {len(texto_limpio):,} chars (antes truncado) — {titulo}")
            stats["actualizadas"] += 1
            continue

        await motor_api.actualizar_props(ficha["id"], cambios, tenant=_TENANT)
        stats["actualizadas"] += 1
        if i % 20 == 0 or i <= 5:
            print(f"  [{i}/{len(fichas)}] {len(texto_limpio):,} chars — {titulo}")

    return stats


# ── Paso 2: chunking ─────────────────────────────────────────────────────────────

async def _fichas_con_texto(repositorio: str | None, limit: int | None) -> list[dict]:
    where_repo = "AND f.props->>'repositorio' = :repo" if repositorio else ""
    lim = "LIMIT :lim" if limit else ""
    params: dict = {"t": _TENANT}
    if repositorio:
        params["repo"] = repositorio
    if limit:
        params["lim"] = limit
    async with get_session_factory()() as s:
        r = await s.execute(sa_text(f"""
            SELECT f.id::text, f.props->>'texto_completo' AS texto_completo,
                   f.props->>'titulo' AS titulo
            FROM ficha f
            JOIN tipo_ficha tf ON tf.id = f.tipo_ficha_id
            JOIN area a ON a.id = tf.area_id
            WHERE a.nombre = 'corpus_cientifico' AND a.tenant_id = :t AND tf.nombre = 'fuente'
              AND f.props->>'texto_completo' IS NOT NULL AND f.props->>'texto_completo' != ''
              {where_repo}
            ORDER BY f.created_at DESC
            {lim}
        """), params)
        return [dict(row._mapping) for row in r.fetchall()]


# Concurrencia de fichas procesadas en simultáneo. El servicio BGE-m3 self-hosted en Modal
# escala contenedores con carga concurrente (ver motor_api.guardar_fichas_batch, dpn-normativo/
# docs/architecture.md §Hallazgo throughput) — procesar ficha por ficha sin esto tomó ~1 min
# por fuente en una corrida real (2026-07-06), a ese ritmo 1414 fuentes hubieran tardado ~24h.
# Con concurrencia=20 y luego 8/5 usando el batch_size default de guardar_fichas_batch (256)
# el servicio devolvió mayoría de 500/204 (2026-07-06) — 5 concurrentes x 256 textos/request
# es hasta 1280 textos en vuelo contra un servicio CPU-only de 4GB RAM, muy por encima de lo
# validado. dpn-normativo/docs/architecture.md §Hallazgo throughput ya probó esta misma
# infraestructura con 0 errores usando concurrencia=12 y batch_size=20 (~15 textos/s
# sostenido) — se replica ese mismo patrón acá en vez de reinventar uno nuevo.
_CONCURRENCIA = 10
_BATCH_SIZE_EMBED = 20
_MAX_REINTENTOS = 5
_ESPERA_REINTENTO = 5.0
_SEM_CONEXIONES = asyncio.Semaphore(5)


async def _procesar_una_ficha(
    ficha: dict, dry_run: bool, tamano_tokens: int, overlap_tokens: int,
) -> tuple[str, int, str]:
    """Retorna (status, n_fragmentos, mensaje_error) para una ficha."""
    existentes = await motor_api.conexiones_de(
        ficha["id"], tipo_conexion="chunk_de", direccion="entrantes", tenant=_TENANT,
    )
    if existentes:
        return ("ya_chunkeada", 0, "")

    fragmentos = chunk_texto(ficha["texto_completo"], tamano_tokens, overlap_tokens)
    if not fragmentos:
        return ("sin_fragmentos", 0, "")

    if dry_run:
        return ("chunkeada", len(fragmentos), "")

    campos_list = [{"orden": f["orden"], "texto": f["texto"]} for f in fragmentos]

    ultimo_error = ""
    for intento in range(1, _MAX_REINTENTOS + 1):
        try:
            res = await motor_api.guardar_fichas_batch(
                area="corpus_cientifico", tipo="fuente_chunk", campos_list=campos_list, tenant=_TENANT,
                batch_size=_BATCH_SIZE_EMBED,
            )
        except Exception as exc:
            ultimo_error = f"{type(exc).__name__}: {exc}"
            if intento < _MAX_REINTENTOS:
                await asyncio.sleep(_ESPERA_REINTENTO * intento)
                continue
            return ("error", 0, ultimo_error)

        if not res.get("success"):
            ultimo_error = res.get("error", "")
            if intento < _MAX_REINTENTOS:
                await asyncio.sleep(_ESPERA_REINTENTO * intento)
                continue
            return ("error", 0, ultimo_error)

        # Conexiones acotadas por un semáforo propio, chico — documentos con cientos de
        # fragmentos (ej. 734 en una tesis) agotaban el pool de conexiones de SQLAlchemy
        # al disparar un guardar_conexion concurrente por cada chunk sin límite (2026-07-07,
        # ver criza/docs/progress/2026-07-07.md) dejando fichas fuente_chunk creadas pero sin
        # su conexión al padre. _SEM_CONEXIONES acota cuántas corren a la vez.
        try:
            async def _conectar(chunk_id: str) -> None:
                async with _SEM_CONEXIONES:
                    await motor_api.guardar_conexion(
                        area="corpus_cientifico", tipo="chunk_de",
                        desde_ficha_id=chunk_id, hacia_ficha_id=ficha["id"], tenant=_TENANT,
                    )

            await asyncio.gather(*(_conectar(chunk_id) for chunk_id in res["ids"]))
        except Exception as exc:
            # las fichas fuente_chunk ya se insertaron — quedan sin conexión chunk_de.
            # No se reintenta el guardado completo (duplicaría las fichas); se reporta el
            # gap para resolución manual en vez de fallar en silencio.
            return ("error", 0, f"chunks creados sin conexión ({len(res['ids'])} ids): {exc}")

        return ("chunkeada", len(fragmentos), "")

    return ("error", 0, ultimo_error)


async def generar_chunks(
    dry_run: bool, repositorio: str | None, limit: int | None,
    tamano_tokens: int = 500, overlap_tokens: int = 50,
) -> dict:
    stats = {"candidatas": 0, "ya_chunkeadas": 0, "chunkeadas": 0, "sin_fragmentos": 0,
              "errores": 0, "fragmentos_creados": 0}

    fichas = await _fichas_con_texto(repositorio, limit)
    stats["candidatas"] = len(fichas)
    print(f"Chunking — {len(fichas)} fichas con texto_completo (concurrencia={_CONCURRENCIA})")

    sem = asyncio.Semaphore(_CONCURRENCIA)
    completadas = 0

    async def _con_semaforo(ficha: dict) -> tuple[dict, str, int, str]:
        async with sem:
            status, n, err = await _procesar_una_ficha(ficha, dry_run, tamano_tokens, overlap_tokens)
            return ficha, status, n, err

    tareas = [asyncio.create_task(_con_semaforo(f)) for f in fichas]
    for tarea in asyncio.as_completed(tareas):
        ficha, status, n, err = await tarea
        completadas += 1
        titulo = (ficha.get("titulo") or "")[:60]

        if status == "ya_chunkeada":
            stats["ya_chunkeadas"] += 1
        elif status == "sin_fragmentos":
            stats["sin_fragmentos"] += 1
        elif status == "error":
            stats["errores"] += 1
            print(f"  ✗ [{completadas}/{len(fichas)}] {err} — {titulo}")
        else:
            stats["chunkeadas"] += 1
            stats["fragmentos_creados"] += n

        if completadas % 20 == 0 or completadas <= 5 or completadas == len(fichas):
            prefix = "DRY " if dry_run else ""
            print(f"  {prefix}[{completadas}/{len(fichas)}] {n} fragmentos — {titulo}")

    return stats


# ── main ──────────────────────────────────────────────────────────────────────

async def run(
    dry_run: bool, repositorio: str | None, limit: int | None,
    solo_backfill: bool, solo_chunking: bool,
) -> None:
    reset_engine()

    print("Cargando plantilla corpus_cientifico (fuente_chunk + chunk_de)...")
    resumen = await load_plantilla(str(_PLANTILLA))
    print(f"  área={resumen['area']} tipos_ficha={resumen['tipos_ficha']} "
          f"tipos_conexion={resumen['tipos_conexion']}")

    if not solo_chunking:
        print("\n=== Paso 1: backfill de texto_completo ===")
        stats1 = await backfill_texto_completo(dry_run, repositorio, limit)
        for k, v in stats1.items():
            print(f"  {k}: {v}")

    if not solo_backfill:
        print("\n=== Paso 2: chunking ===")
        stats2 = await generar_chunks(dry_run, repositorio, limit)
        for k, v in stats2.items():
            print(f"  {k}: {v}")


def main():
    parser = argparse.ArgumentParser(
        description="Backfill de texto_completo sin cap + chunking de corpus_cientifico/fuente"
    )
    parser.add_argument("--dry-run", action="store_true", help="Muestra qué haría sin escribir")
    parser.add_argument("--repositorio", default=None, help="Filtrar por repositorio (ej. INTA, CONICET)")
    parser.add_argument("--limit", type=int, default=None, help="Máximo de fichas a procesar por paso")
    parser.add_argument("--solo-backfill-texto", action="store_true", dest="solo_backfill",
                         help="Correr solo el paso 1 (backfill de texto_completo)")
    parser.add_argument("--solo-chunking", action="store_true", dest="solo_chunking",
                         help="Correr solo el paso 2 (chunking)")
    args = parser.parse_args()

    if args.solo_backfill and args.solo_chunking:
        parser.error("--solo-backfill-texto y --solo-chunking son mutuamente excluyentes")

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(run(
        dry_run=args.dry_run, repositorio=args.repositorio, limit=args.limit,
        solo_backfill=args.solo_backfill, solo_chunking=args.solo_chunking,
    ))


if __name__ == "__main__":
    main()
