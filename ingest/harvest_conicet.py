"""
Ingesta del corpus científico CONICET al KM — vía protocolo OAI-PMH.

Lee la config del conector (criza/config/connectors/conicet.yaml), cosecha registros vía
OAI-PMH, aplica filtro de pertinencia, deduplica por identifier exacto y guarda fichas `fuente`
en el motor del KM.

Movido de knowledge_module/ingesta/ingest_corpus.py el 2026-08-14, junto con utils/oai_pmh.py:
único consumidor real es CONICET/CRIZA — bajo el principio de "cada instancia sus herramientas",
baja acá en vez de vivir en el paquete compartido (que además reusaba el harvester genérico
solo para este único caso).

Uso CLI:
    # Ver sets disponibles en el repositorio configurado
    python ingest/harvest_conicet.py --list-sets --config config/connectors/conicet.yaml

    # Cosecha completa (primera vez)
    python ingest/harvest_conicet.py --config config/connectors/conicet.yaml

    # Cosecha incremental desde fecha
    python ingest/harvest_conicet.py --config config/connectors/conicet.yaml --from 2025-01-01

    # Límite para tests rápidos
    python ingest/harvest_conicet.py --config config/connectors/conicet.yaml --limit 50
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

import yaml
from sqlalchemy import text

# ── paths ──────────────────────────────────────────────────────────────────
_CRIZA = Path(__file__).parent.parent
if str(_CRIZA) not in sys.path:
    sys.path.insert(0, str(_CRIZA))

from dotenv import load_dotenv
load_dotenv(_CRIZA / ".env")

from utils.oai_pmh import OAIPMHHarvester, OAIRecord
from knowledge_module.db import get_session_factory, reset_engine
from knowledge_module.motor import api as motor_api
from knowledge_module.motor.loader import load_plantilla

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ── Dedup por identifier exacto ────────────────────────────────────────────────

async def _load_existing_identifiers(tenant: str) -> set[str]:
    """Carga en memoria todos los identifiers de fuentes ya en el corpus."""
    async with get_session_factory()() as s:
        r = await s.execute(
            text("""
                SELECT f.props->>'identifier' AS ident
                FROM ficha f
                JOIN tipo_ficha tf ON tf.id = f.tipo_ficha_id
                JOIN area a ON a.id = tf.area_id
                WHERE a.nombre = 'corpus_cientifico'
                  AND a.tenant_id = :t
                  AND tf.nombre = 'fuente'
                  AND f.props->>'identifier' IS NOT NULL
            """),
            {"t": tenant},
        )
        return {row.ident for row in r.fetchall()}


# ── Filtro de pertinencia ──────────────────────────────────────────────────────

def _es_pertinente(record: OAIRecord, keywords: list[str], abstract_min: int) -> bool:
    """
    Devuelve True si el registro pasa el filtro de pertinencia.
    Busca keywords (case-insensitive) en título, abstract y subjects.
    Si la lista de keywords está vacía, todo pasa.
    """
    if len(record.abstract) < abstract_min:
        return False

    if not keywords:
        return True

    texto_busqueda = " ".join([
        record.titulo,
        record.abstract,
        " ".join(record.subjects),
    ]).lower()

    return any(kw.lower() in texto_busqueda for kw in keywords)


# ── Conversión OAIRecord → campos de ficha ────────────────────────────────────

def _record_a_campos(record: OAIRecord, repositorio: str) -> dict:
    """Convierte un OAIRecord a los campos del tipo_ficha 'fuente'."""
    titulo_abstract = f"{record.titulo}. {record.abstract}".strip()
    return {
        "titulo": record.titulo,
        "abstract": record.abstract,
        "autores": record.autores,
        "anio": record.anio,
        "identifier": record.identifier,
        "url": record.url or "",
        "repositorio": repositorio,
        "idioma": record.idioma or "",
        "tipo_recurso": record.tipo_recurso or "",
        "sets": record.sets,
        "titulo_abstract": titulo_abstract,  # campo vectorizado
        "open_access": record.open_access,
        "pdf_url": None,          # se completa en ingesta/download_corpus_pdfs.py
        "texto_completo": None,   # idem — requiere scrapear la landing page + descargar
    }


# ── Estado de cosecha incremental ─────────────────────────────────────────────

def _leer_estado(state_path: Path) -> dict:
    if state_path.exists():
        return json.loads(state_path.read_text(encoding="utf-8"))
    return {}


def _guardar_estado(state_path: Path, estado: dict) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(estado, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Ingesta principal ──────────────────────────────────────────────────────────

async def ingestar(
    config_path: str,
    from_date: str | None = None,
    until_date: str | None = None,
    limit: int | None = None,
    list_sets: bool = False,
    plantilla_path: str = None,
) -> dict:
    """
    Orquesta la cosecha OAI-PMH y la ingesta al KM.

    `plantilla_path` es obligatorio: la plantilla del área (con su tenant) se pasa explícita,
    no hay default (mismo criterio que el resto de los conectores de CRIZA).

    Returns: stats dict {cosechados, filtrados, deduplicados, ingeridos, errores}.
    """
    cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))

    endpoint = cfg["endpoint"]
    if "tenant" not in cfg:
        raise ValueError(
            f"{config_path}: falta 'tenant'. Cada config de conector debe declararlo explícito."
        )
    tenant = cfg["tenant"]
    repositorio = cfg.get("repositorio", "desconocido")
    sets_a_cosechar = cfg.get("sets", []) or [None]  # None = sin filtro de set
    keywords = cfg.get("pertinencia_keywords", [])
    abstract_min = cfg.get("abstract_min_chars", 100)
    delay = cfg.get("request_delay_seconds", 1.5)
    timeout = cfg.get("timeout_seconds", 30)
    max_retries = cfg.get("max_retries", 3)

    harvester = OAIPMHHarvester(
        endpoint=endpoint,
        request_delay=delay,
        timeout=timeout,
        max_retries=max_retries,
    )

    if list_sets:
        sets = harvester.list_sets()
        logger.info("Sets disponibles en %s (%d):", endpoint, len(sets))
        for s in sets:
            logger.info("  %s — %s", s["spec"], s["name"])
        return {"sets": sets}

    if not plantilla_path:
        raise ValueError(
            "plantilla_path es obligatorio: la plantilla del área (con su tenant). "
            "Ej.: config/plantillas/corpus_cientifico.yaml"
        )
    plantilla = plantilla_path
    reset_engine()
    logger.info("Cargando plantilla corpus_cientifico...")
    await load_plantilla(plantilla)

    # Estado de cosecha incremental
    config_dir = Path(config_path).parent
    state_file = config_dir / f"{Path(config_path).stem}_harvest_state.json"
    estado = _leer_estado(state_file)

    # from_date: CLI > último estado guardado
    if from_date is None:
        from_date = estado.get("ultimo_datestamp")

    logger.info(
        "Iniciando cosecha — repositorio=%s from=%s until=%s sets=%s",
        repositorio, from_date or "todo", until_date or "hoy", sets_a_cosechar,
    )

    # Cargar identifiers existentes para dedup exacto
    existing = await _load_existing_identifiers(tenant)
    logger.info("Identifiers en corpus existente: %d", len(existing))

    stats = {"cosechados": 0, "filtrados": 0, "deduplicados": 0, "ingeridos": 0, "errores": 0}
    ultimo_datestamp = from_date

    for set_spec in sets_a_cosechar:
        for record in harvester.harvest(
            set_spec=set_spec,
            from_date=from_date,
            until_date=until_date,
        ):
            stats["cosechados"] += 1

            # Registrar datestamp para cosecha incremental
            if record.datestamp > (ultimo_datestamp or ""):
                ultimo_datestamp = record.datestamp

            # Filtro de pertinencia
            if not _es_pertinente(record, keywords, abstract_min):
                stats["filtrados"] += 1
                continue

            # Dedup exacto por identifier
            if record.identifier in existing:
                stats["deduplicados"] += 1
                continue

            # Guardar en el motor
            try:
                campos = _record_a_campos(record, repositorio)
                result = await motor_api.guardar_ficha(
                    area="corpus_cientifico",
                    tipo="fuente",
                    campos=campos,
                    tenant=tenant,
                )
                if result.get("success"):
                    stats["ingeridos"] += 1
                    existing.add(record.identifier)
                else:
                    logger.error("Error guardando ficha %s: %s", record.identifier, result.get("error"))
                    stats["errores"] += 1
            except Exception as exc:
                logger.error("Excepción guardando %s: %s", record.identifier, exc, exc_info=True)
                stats["errores"] += 1

            if limit and (stats["ingeridos"] + stats["deduplicados"]) >= limit:
                logger.info("Límite de %d alcanzado, deteniendo.", limit)
                break

    # Guardar estado incremental
    if ultimo_datestamp:
        _guardar_estado(state_file, {
            "ultimo_datestamp": ultimo_datestamp,
            "ultimo_run": str(Path(config_path).stem),
        })
        logger.info("Estado guardado: ultimo_datestamp=%s", ultimo_datestamp)

    logger.info(
        "Cosecha finalizada — cosechados=%d filtrados=%d deduplicados=%d ingeridos=%d errores=%d",
        stats["cosechados"], stats["filtrados"], stats["deduplicados"],
        stats["ingeridos"], stats["errores"],
    )
    return stats


# ── Entrypoint CLI ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Ingesta corpus científico CONICET (OAI-PMH) → KM")
    parser.add_argument("--config", required=True, help="Path al YAML de config del conector")
    parser.add_argument("--from", dest="from_date", help="Fecha inicio cosecha YYYY-MM-DD")
    parser.add_argument("--until", dest="until_date", help="Fecha fin cosecha YYYY-MM-DD")
    parser.add_argument("--limit", type=int, help="Límite de registros a ingestar (para tests)")
    parser.add_argument("--list-sets", action="store_true", help="Solo listar sets del repositorio")
    parser.add_argument("--plantilla", help="Path a la plantilla YAML del área (no requerido con --list-sets)")
    args = parser.parse_args()

    result = asyncio.run(ingestar(
        config_path=args.config,
        from_date=args.from_date,
        until_date=args.until_date,
        limit=args.limit,
        list_sets=args.list_sets,
        plantilla_path=args.plantilla,
    ))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
