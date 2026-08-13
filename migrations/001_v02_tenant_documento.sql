-- ─────────────────────────────────────────────────────────────────────────────
-- Migración 001 — KM v0.2: tenant_id + nodo Documento + arista GENERA
-- Fecha: 2026-06-09
-- Ejecutar UNA VEZ contra la DB de Neon.
-- Es idempotente: usa IF NOT EXISTS / DO $$ blocks para no fallar si ya fue aplicada.
-- ─────────────────────────────────────────────────────────────────────────────

-- ── 1. Agregar tenant_id a tablas existentes ─────────────────────────────────
-- DEFAULT 'criza' garantiza que los ~30 registros existentes queden correctamente asignados.

ALTER TABLE corrida
    ADD COLUMN IF NOT EXISTS tenant_id VARCHAR NOT NULL DEFAULT 'criza';

ALTER TABLE oportunidad
    ADD COLUMN IF NOT EXISTS tenant_id VARCHAR NOT NULL DEFAULT 'criza';

ALTER TABLE aprendizaje
    ADD COLUMN IF NOT EXISTS tenant_id VARCHAR NOT NULL DEFAULT 'criza';

-- Índices para filtrar por tenant (necesarios cuando haya más de uno)
CREATE INDEX IF NOT EXISTS idx_corrida_tenant ON corrida (tenant_id);
CREATE INDEX IF NOT EXISTS idx_oportunidad_tenant ON oportunidad (tenant_id);
CREATE INDEX IF NOT EXISTS idx_aprendizaje_tenant ON aprendizaje (tenant_id);

-- ── 2. Nodo Documento ────────────────────────────────────────────────────────
-- Almacena el output completo de una corrida (texto markdown sin reducir).
-- Permite recuperar el análisis completo si las Oportunidades extraídas pierden contexto.

CREATE TABLE IF NOT EXISTS documento (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id   VARCHAR NOT NULL DEFAULT 'criza',
    tipo        VARCHAR NOT NULL DEFAULT 'analisis'
                CHECK (tipo IN ('analisis', 'informe', 'borrador')),
    titulo      VARCHAR,
    contenido   TEXT NOT NULL,   -- output markdown completo
    agente      VARCHAR NOT NULL CHECK (agente IN ('divergente', 'convergente')),
    sector      VARCHAR NOT NULL,
    fecha       DATE NOT NULL,
    modelo      VARCHAR NOT NULL,
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_documento_tenant ON documento (tenant_id);
CREATE INDEX IF NOT EXISTS idx_documento_sector ON documento (sector, fecha);
CREATE INDEX IF NOT EXISTS idx_documento_agente ON documento (agente);

-- ── 3. Arista GENERA (Corrida → Documento) ───────────────────────────────────

CREATE TABLE IF NOT EXISTS corrida_documento (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    corrida_id   UUID NOT NULL REFERENCES corrida(id) ON DELETE CASCADE,
    documento_id UUID NOT NULL REFERENCES documento(id) ON DELETE CASCADE,
    created_at   TIMESTAMP DEFAULT NOW(),
    UNIQUE (corrida_id, documento_id)
);

CREATE INDEX IF NOT EXISTS idx_corrida_documento_corrida ON corrida_documento (corrida_id);
CREATE INDEX IF NOT EXISTS idx_corrida_documento_documento ON corrida_documento (documento_id);
