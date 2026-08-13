-- 004_tipo_documento_inta.sql
-- Amplía documento.tipo (additivo, no renombra nada existente) para reflejar la
-- taxonomía real de colecciones INTA Digital, descubierta al auditar CICVyA:
-- tesis, ponencias, libros, partes de libro, divulgación y folletos estaban
-- todos cayendo en "paper" o "reporte" por defecto en harvest_inta.py.
--
-- "paper" y "reporte" se mantienen como están (no se renombran) para no romper
-- el enum de tipo que ya usan los tools de los agentes (investigacion_amplia,
-- evidence_generalista) ni los 1,643 docs ya clasificados correctamente.

ALTER TABLE documento DROP CONSTRAINT IF EXISTS documento_tipo_check;
ALTER TABLE documento ADD CONSTRAINT documento_tipo_check
   CHECK (tipo IN (
       'analisis','informe','borrador',           -- internos (corridas)
       'paper','reporte','norma','patente','otro', -- existentes (no tocar)
       'tesis','ponencia','libro','parte_libro','divulgacion','folleto'  -- nuevos (INTA)
   ));
