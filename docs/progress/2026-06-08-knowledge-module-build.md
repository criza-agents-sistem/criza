# Sesión 2026-06-08 (noche) — Knowledge Module: build inicial

## Qué se hizo

### Knowledge Module v0.1 construido y funcionando

Estructura completa en `EMPRESAS-IA/knowledge_module/` (Capa 1, no dentro de criza/).

**Stack:**
- DB: Neon + pgvector (tablas creadas: corrida, oportunidad, aprendizaje, corrida_oportunidad)
- Embeddings: sentence-transformers local (paraphrase-multilingual-MiniLM-L12-v2, 384 dims)
  → abstracción lista para swappear a BGE-m3 (SEB-118) cambiando solo .env
- MCP server: FastMCP con 6 tools expuestas a los agentes

**Tools implementadas:**
- `km_store_corrida` — guarda una ejecución del agente
- `km_store_opportunity` — guarda oportunidad, deduplica por similitud semántica (≥0.92 → incrementa veces_detectada)
- `km_store_learning` — guarda aprendizaje, refuerza nivel_confianza si ya existe similar
- `km_search` — búsqueda semántica sobre oportunidades y aprendizajes
- `km_get_opportunity` — historial completo de una oportunidad (corridas que la generaron, validaciones, gaps)
- `km_update_opportunity` — actualiza estado/validaciones de una oportunidad

**Tests: 7/7 pasando**
- 3 unit (embeddings, sin DB)
- 4 integration (contra Neon real: store, search, deduplicación, historial)

**Decisión técnica importante:**
El engine de SQLAlchemy se crea lazy (no al importar el módulo) para no quedar atado
al event loop de importación — patrón necesario para tests async y para el MCP server.

## Pendientes / próxima sesión

1. **ROADMAP.md** del knowledge_module — falta escribirlo
2. **Conectar el MCP al agente divergente** — agregar las tools km_* al test_metodologia.py
   para que al final de cada corrida guarde automáticamente la corrida y las oportunidades
3. **Ingestar los outputs existentes** — cargar los 3 informes de corridas del 2026-06-08
   y los aprendizajes de la knowledge_base_ligera.md en el KM
4. **SEB-118 (BGE-m3)** — swap del embedding local por self-hosted, cuando corresponda
5. **Rotar el password de Neon** — Sebas lo tiene que hacer desde el dashboard de Neon

## Archivos creados

```
knowledge_module/
├── server.py
├── db.py
├── embeddings.py
├── schema.sql
├── requirements.txt
├── pytest.ini
├── .env (local, no commiteado)
├── .env.example
├── .gitignore
├── tools/
│   ├── __init__.py
│   ├── store.py
│   ├── search.py
│   └── retrieve.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    └── test_tools.py
```
