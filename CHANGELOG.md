# Changelog — Agente Científico CRIZA

Formato: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)

---

## v1.3.0 — Mayo 2026

### Added
- Suite de tests completa: 80 unit tests + 24 integration tests (`tests/`)
- `conftest.py` con fixtures compartidas para todos los tests
- `pytest.ini` con markers `unit` / `integration` (default: solo unit)
- `requirements-dev.txt` con dependencias de testing
- Carpeta `docs/` — documentación técnica separada del código
- Carpeta `outputs/` — briefs y demos generados (no son código)
- `CHANGELOG.md` (este archivo)

### Changed
- `ARCHITECTURE.md` → movido a `docs/ARCHITECTURE.md`, actualizado a v1.3
- `DECISIONS.md` → movido a `docs/DECISIONS.md`, agregado ADR-007 (fallback graceful)
- `ONBOARDING.md` → movido a `docs/ONBOARDING.md`
- `demo_andres_lactoferrina.md` → movido a `outputs/`
- `informe_andres_lactoferrina.md` → movido a `outputs/`
- `README.md` → tabla de herramientas actualizada a 8 tools, links a `docs/`
- `ROADMAP.md` → marcado v1.1-A y v1.1-B como completados, versionado a v1.3

---

## v1.2.0 — Mayo 2026

### Added
- `tools/mpnn.py` — `design_variants_mpnn()`: diseño de variantes via ProteinMPNN (ML)
  - Subprocess call a ProteinMPNN `protein_mpnn_run.py`
  - Parser de FASTA con scores negative log-likelihood
  - Fallback graceful si `PROTEINMPNN_PATH` no está configurado
- `tools/foldx.py` — `predict_tm_change()`: predicción ΔΔG y ΔTm via FoldX
  - Pipeline: RepairPDB → BuildModel → parseo de `.fxout`
  - Conversión ΔΔG → ΔTm con factor empírico 1.7 °C·mol/kcal
  - Fallback graceful si `FOLDX_PATH` no está configurado
- `.env.example` actualizado con `PROTEINMPNN_PATH` y `FOLDX_PATH`

### Changed
- `agent.py` → v1.3-0: importa y expone `design_variants_mpnn` y `predict_tm_change`
- `tools/__init__.py` → 9 exports (incluyendo nuevas herramientas)
- `ARCHITECTURE.md` → secciones para ProteinMPNN y FoldX

---

## v1.1.0 — Mayo 2026

### Added
- `tools/semantic_scholar.py` — `search_literature()`: reemplaza PubMed como fuente bibliográfica
  - Cobertura 200M+ papers (vs. PubMed solo biomédico)
  - Retorna DOI, citation count, PDF open access
  - Rate limit: 100 req/5min sin API key; 1 req/seg con `SEMANTIC_SCHOLAR_API_KEY`

### Changed
- `agent.py` → migra de `search_pubmed` a `search_literature`
- `ARCHITECTURE.md` → documenta decisión Semantic Scholar vs. PubMed
- `DECISIONS.md` → ADR-001 (Semantic Scholar)

### Kept
- `tools/pubmed.py` → mantenido como fallback/referencia, no expuesto en el agente

---

## v1.0.0 — Mayo 2026

### Added
- `tools/stability.py` — `analyze_stability()`: mapeo de regiones inestables por pLDDT
- `tools/variants.py` — `design_variants()`: diseño rule-based de variantes termoestables
  - Sustituciones de prolina en bucles
  - Mutaciones de consenso
  - Variantes combinadas
- `tools/compare.py` — `compare_variants()`: validación computacional via ESMFold
- Persistencia de PDB en `structures/` (input para herramientas de diseño)

### Changed
- `agent.py` → workflow extendido a 7 pasos (agrega estabilidad, variantes, comparación)

---

## v0.1.0 — Mayo 2026

### Added
- `agent.py` — loop agéntico con tool use (Anthropic SDK)
- `tools/pubmed.py` — `search_pubmed()`: búsqueda bibliográfica via NCBI E-utilities
- `tools/uniprot.py` — `get_protein_sequence()`: secuencias via UniProt REST
- `tools/esmfold.py` — `predict_structure()`: predicción estructural via ESM Atlas API
  - Límite de 200 aa (confiabilidad sobre completitud)
  - Normalización automática de pLDDT (escala 0–1 → 0–100)
- `run.py` — CLI con casos preconfigurados
- `Dockerfile` + `docker-compose.yml`
- `ARCHITECTURE.md`, `DECISIONS.md`, `ONBOARDING.md`, `README.md`, `ROADMAP.md`
