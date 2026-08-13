# Migraciones propias de CRIZA (Capa 2)

Schema/seed-data específico de CRIZA/INTA, no genérico — por eso no viajó al paquete
`knowledge_module` cuando se separó a `github.com/sebasbizzi/km-knowledge-module` (2026-07-24).
Hasta esa fecha vivían sin trackear en ningún repo (numeradas junto con las migraciones genéricas
del KM, que ahora son `001`/`002`/`003` en el repo nuevo — números distintos, no confundir).

**Las 4 ya están aplicadas al Neon real de CRIZA. No re-ejecutar.** Se versionan acá como
definición de schema/seed-data, no como pendientes de correr.

| Archivo | Qué hace | Aplicada |
|---|---|---|
| `001_v02_tenant_documento.sql` | KM v0.2: agrega `tenant_id` + nodo `Documento` + arista `GENERA` | 2026-06-09 |
| `002_reembed_bgem3.py` | Re-embedea oportunidades/aprendizajes de MiniLM (384 dims) a BGE-m3 (1024 dims) — SEB-121 | ✅ |
| `004_tipo_documento_inta.sql` | Amplía `documento.tipo` con la taxonomía real de colecciones INTA Digital (tesis, ponencias, libros, etc.) | 2026-06-30 |
| `005_tipo_ficha_oportunidad.sql` | Agrega `tipo_ficha='oportunidad'` al área `descubrimiento`, tenant `criza` — nodo raíz que el Motor crea al iniciar un pipeline | 2026-07-01 |
