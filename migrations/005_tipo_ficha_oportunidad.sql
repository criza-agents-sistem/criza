-- Agrega tipo_ficha 'oportunidad' al área 'descubrimiento' — tenant criza.
-- Es el nodo raíz que el Motor crea al iniciar un pipeline de análisis.
-- El motor llama guardar_ficha(area="descubrimiento", tipo="oportunidad", ...).

INSERT INTO tipo_ficha (area_id, nombre, descripcion, campos, vectorizar, dedup_por, dedup_umbral)
SELECT
    a.id,
    'oportunidad',
    'Punto de entrada al pipeline: sector o recurso a analizar',
    '["nombre", "descripcion"]'::JSONB,
    'nombre',
    'nombre',
    0.90
FROM area a
WHERE a.nombre = 'descubrimiento' AND a.tenant_id = 'criza'
ON CONFLICT (area_id, nombre) DO NOTHING;
