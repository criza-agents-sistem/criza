"""
Modelo ORM legacy de CRIZA (Capa 2) — tabla `documento`.

Se movió acá desde `knowledge_module/db.py` al empaquetar el KM (2026-07-22): es un concepto
específico de CRIZA, no de la plataforma. Se declara sobre la `Base` genérica del paquete
(`knowledge_module.db.Base`) y comparte su engine.

El motor genérico (`knowledge_module.motor`, tablas `ficha`/`conexion`) es el sustrato de
plataforma; este modelo es el esquema legacy que CRIZA todavía usa vía `criza/km_tools/`
(`store_fuente_externa`, `batch_store_fuentes_externas`, `get_sector_corpus`,
`search_fuentes_externas`, `get_paper_full_text`, `get_ficha_full_text`).

Archivado el 2026-08-15 (`_archivo_temporal/`, ver `docs/progress/2026-08-15.md`): las clases
`Corrida`, `Oportunidad`, `Aprendizaje`, `CorridaOportunidad`, `CorridaDocumento` — eran el
esquema del pipeline scout/agente divergente/convergente, borrado el 2026-07-02. Las tablas
correspondientes siguen existiendo en Neon (no se tocaron datos), solo se archivó el código que
las escribía/exponía — ya no tenían ningún consumidor real.
"""

from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    Column,
    Computed,
    Date,
    DateTime,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID as PG_UUID

from knowledge_module.db import Base


class Documento(Base):
    """
    Nodo Documento (v0.3) — output de corrida o fuente externa (paper, norma, informe).

    Para documentos externos (papers INTA, normativa DPN):
      - contenido  = resumen/abstract
      - texto_completo = texto extraído del PDF (opcional, puede ser null)
      - agente     = "harvest" | "ingest"
      - modelo     = "n/a"

    Para outputs de corridas internas (agente="divergente"/"convergente" — pipeline archivado
    el 2026-08-15, valores del CHECK constraint que se mantienen por compatibilidad con filas
    históricas, no porque algo los siga escribiendo):
      - contenido  = markdown completo del análisis
      - texto_completo = null
      - agente     = nombre del agente que lo generó
    """
    __tablename__ = "documento"

    id               = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id        = Column(String, nullable=False, default="criza")
    tipo             = Column(String, nullable=False, default="analisis")
    titulo           = Column(String)
    contenido        = Column(Text, nullable=False)
    texto_completo   = Column(Text, nullable=True)
    autores          = Column(Text, nullable=True)   # JSON array serializado
    subjects         = Column(Text, nullable=True)   # JSON array serializado
    agente           = Column(String, nullable=False)
    sector           = Column(String, nullable=False)
    fecha            = Column(Date, nullable=False)
    modelo           = Column(String, nullable=False)
    fuente_url       = Column(String, nullable=True)
    doi              = Column(String, nullable=True)
    fts_vector       = Column(
        TSVECTOR,
        Computed(
            "to_tsvector('simple', coalesce(titulo,'') || ' ' || coalesce(contenido,'') || ' ' || coalesce(subjects,''))",
            persisted=True,
        ),
        nullable=True,
    )
    created_at       = Column(DateTime, default=func.now())
    updated_at       = Column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint(
            "agente IN ('divergente','convergente','harvest','ingest')",
            name="documento_agente_check",
        ),
        CheckConstraint(
            "tipo IN ('analisis','informe','borrador','paper','reporte','norma','patente','otro')",
            name="documento_tipo_check",
        ),
        # fuente_url UNIQUE excluye NULLs (docs internos sin URL)
        Index("uq_documento_fuente_url", "fuente_url", unique=True,
              postgresql_where=text("fuente_url IS NOT NULL")),
    )
