"""
Modelos ORM legacy de CRIZA (Capa 2) — tablas `corrida`, `oportunidad`, `aprendizaje`,
`documento` y sus aristas.

Se movieron acá desde `knowledge_module/db.py` al empaquetar el KM (2026-07-22): son conceptos
específicos de CRIZA (blue oceans, corridas divergente/convergente), no de la plataforma. Se
declaran sobre la `Base` genérica del paquete (`knowledge_module.db.Base`) y comparten su engine.

El motor genérico (`knowledge_module.motor`, tablas `ficha`/`conexion`) es el sustrato de
plataforma; estos modelos son el esquema legacy que CRIZA todavía usa vía `criza/km_tools/`.
"""

import os
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    Column,
    Computed,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID as PG_UUID
from sqlalchemy.orm import relationship

from knowledge_module.db import Base


class Corrida(Base):
    __tablename__ = "corrida"

    id            = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id     = Column(String, nullable=False, default="criza")
    sector        = Column(String, nullable=False)
    agente        = Column(String, nullable=False)
    modo          = Column(String, nullable=False)
    fecha         = Column(Date, nullable=False)
    modelo        = Column(String, nullable=False)
    tokens_input  = Column(Integer)
    tokens_output = Column(Integer)
    costo_usd     = Column(Float)
    notas         = Column(Text)
    created_at    = Column(DateTime, default=func.now())
    updated_at    = Column(DateTime, default=func.now(), onupdate=func.now())

    oportunidades = relationship(
        "Oportunidad", secondary="corrida_oportunidad", back_populates="corridas"
    )
    documentos    = relationship(
        "Documento", secondary="corrida_documento", back_populates="corridas"
    )


class Oportunidad(Base):
    __tablename__ = "oportunidad"

    id              = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id       = Column(String, nullable=False, default="criza")
    sector          = Column(String, nullable=False)
    idea            = Column(Text, nullable=False)
    prioridad       = Column(String, nullable=False)
    estado_analisis = Column(String, nullable=False, default="detectada")
    origen          = Column(String, nullable=False, default="agente")
    veces_detectada = Column(Integer, nullable=False, default=1)
    validaciones    = Column(Text)
    gaps_pendientes = Column(Text)
    razon_descarte  = Column(Text)
    embedding       = Column(Vector(int(os.getenv("EMBEDDING_DIM", "384"))))
    created_at      = Column(DateTime, default=func.now())
    updated_at      = Column(DateTime, default=func.now(), onupdate=func.now())

    corridas = relationship(
        "Corrida", secondary="corrida_oportunidad", back_populates="oportunidades"
    )


class Aprendizaje(Base):
    __tablename__ = "aprendizaje"

    id                   = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id            = Column(String, nullable=False, default="criza")
    contenido            = Column(Text, nullable=False)
    tipo                 = Column(String, nullable=False)
    nivel_confianza      = Column(Float, nullable=False, default=0.5)
    veces_confirmado     = Column(Integer, nullable=False, default=1)
    ultima_vez_relevante = Column(Date)
    fuente               = Column(String, nullable=False)
    origen_nombre        = Column(String)
    embedding            = Column(Vector(int(os.getenv("EMBEDDING_DIM", "384"))))
    created_at           = Column(DateTime, default=func.now())
    updated_at           = Column(DateTime, default=func.now(), onupdate=func.now())


class CorridaOportunidad(Base):
    """Arista PRODUCE: Corrida → Oportunidad."""
    __tablename__ = "corrida_oportunidad"

    id               = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    corrida_id       = Column(PG_UUID(as_uuid=True), ForeignKey("corrida.id", ondelete="CASCADE"), nullable=False)
    oportunidad_id   = Column(PG_UUID(as_uuid=True), ForeignKey("oportunidad.id", ondelete="CASCADE"), nullable=False)
    prioridad_corrida = Column(String)
    created_at       = Column(DateTime, default=func.now())

    __table_args__ = (UniqueConstraint("corrida_id", "oportunidad_id"),)


class Documento(Base):
    """
    Nodo Documento (v0.3) — output de corrida o fuente externa (paper, norma, informe).

    Para documentos externos (papers INTA, normativa DPN):
      - contenido  = resumen/abstract
      - texto_completo = texto extraído del PDF (opcional, puede ser null)
      - agente     = "harvest" | "ingest"
      - modelo     = "n/a"

    Para outputs de corridas internas:
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

    corridas    = relationship(
        "Corrida", secondary="corrida_documento", back_populates="documentos"
    )


class CorridaDocumento(Base):
    """Arista GENERA: Corrida → Documento."""
    __tablename__ = "corrida_documento"

    id           = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    corrida_id   = Column(PG_UUID(as_uuid=True), ForeignKey("corrida.id", ondelete="CASCADE"), nullable=False)
    documento_id = Column(PG_UUID(as_uuid=True), ForeignKey("documento.id", ondelete="CASCADE"), nullable=False)
    created_at   = Column(DateTime, default=func.now())

    __table_args__ = (UniqueConstraint("corrida_id", "documento_id"),)
