# agents.md — Contexto activo del Agente Científico CRIZA

> Este archivo contiene solo lo que importa HOY. No es un historial.
> Para historial de decisiones → `docs/ARCHITECTURE.md` y `docs/progress/`
> Para roadmap completo → `ROADMAP.md`
> Para arquitectura de plataforma → `KRIZA_Foundation_Document.md`

---

## Contexto del proyecto

CRIZA es la primera instancia de la plataforma EMPRESAS-IA (codename) — vertical de venture-building en biotecnología. El pipeline tiene dos niveles: Scout multidominio (primer filtro, ancho) + Especialistas de dominio (análisis profundo). El usuario actúa como orquestador-colaborador hasta que exista el Orquestador-agente formal.

Etapa actual: **scout v1.1 + especialista proteínas v1.4.1** — construyendo Agente de Mercado (SEB-96).

---

## Stack activo

- **Scout:** `scout.py` — OpenAlex + razonamiento, modelo claude-sonnet-4-6
- **Especialista proteínas:** `specialist_proteins.py` (ex agent.py) — ESMFold/ProteinMPNN/FoldX, modelo configurable
- **Runners:** `run_scouting.py` (scout) · `run.py` (especialista proteínas)
- **Literatura:** OpenAlex API (250M+ papers) — fallback Semantic Scholar
- **GPU:** RunPod pod `qruo50jffhrgze` (H200 SXM, US-CA-2) — **APAGADO por defecto**
- **Tests:** pytest, 110 unit tests pasando
- **CI:** GitHub Actions en cada PR
- **Modelos:** SCOUT_MODEL + SPECIALIST_MODEL en `.env` (configurable por agente)

---

## Linear

- **Proyecto:** CRIZA
- **Equipo:** Sebabizz._dev
- **Cycle activo:** Cycle 3 (junio 2026)
- **Milestone actual:** M1 — Base sólida → M2 Knowledge Module (próximo)

---

## Pendientes / flags abiertos

- [ ] **SEB-96** — Agente de Mercado v0 (próximo a construir)
- [ ] **Tests de scout.py** — faltan unit tests (gap de playbook, pendiente)
- [ ] **SEB-115** — Contrato estándar de agentes (costura, adoptar con Científico + Mercado)
- [ ] **SEB-118** — Embeddings BGE-m3 — DEADLINE antes de ingest DPN
- [ ] **SEB-121** — Knowledge Module ligero (con loop de aprendizaje)
- [ ] **SEB-94** — FoldX: registrarse en foldxsuite.crg.eu y descargar binario
- [ ] **SEB-95** — Serverless GPU (RunPod Serverless o Modal)
- [ ] Naming de la plataforma (codename EMPRESAS-IA — pasada de naming pendiente)
- [ ] Pod RunPod `qruo50jffhrgze` debe estar STOPPED cuando no se usa

---

## Protocolo RunPod

Pod **APAGADO por defecto**. Iniciarlo solo para análisis con proteínas largas (>200aa):
1. cloud.runpod.io → Pods → Start (`mighty_brown_lark`)
2. Esperar ~3-5 min → verificar: `curl https://qruo50jffhrgze-8000.proxy.runpod.net/health`
3. Al terminar → **Stop** (nunca Terminate)

---

## Reglas específicas

- `load_dotenv()` corre **antes** de importar tools — bug histórico resuelto, no revertir
- `ESMFOLD_POD_URL` se lee en runtime con `_get_pod_url()`, nunca al importar
- Tests de integración excluidos por defecto: `pytest -m "not integration"`
- Outputs y PDB en `.gitignore` — se regeneran, no van al repo
- `ROADMAP.md` = fuente de verdad del estado de desarrollo del agente
- Modelo por agente: SCOUT_MODEL (Sonnet) · SPECIALIST_MODEL (configurable, puede ser Opus para deep-dive)
- Scout v1.1: GMO+peletizado es CONTEXTO HABILITADOR, no criterio. Sectores sin restricción.
- `specialist_proteins.py` reemplazó a `agent.py` — no existe más `agent.py`

---

## Dónde están las cosas

```
scientific_agent/
├── scout.py                  ← Scout multidominio v1.1 (primer filtro)
├── specialist_proteins.py    ← Especialista proteínas (ex agent.py)
├── run_scouting.py           ← Runner del scout
├── run.py                    ← Runner del especialista proteínas
├── agents.md                 ← este archivo
├── ROADMAP.md                ← versiones y estado (fuente de verdad dev)
│
├── tools/
│   ├── openalex.py           ← search_literature (PRIMARIA desde v1.4.1)
│   ├── semantic_scholar.py   ← fallback si OpenAlex falla
│   ├── uniprot.py            ← get_protein_sequence
│   ├── esmfold_local.py      ← predict_structure_local (RunPod)
│   ├── esmfold.py            ← predict_structure (fallback 200aa)
│   ├── stability.py          ← analyze_stability
│   ├── variants.py           ← design_variants (rule-based)
│   ├── mpnn.py               ← design_variants_mpnn (opcional)
│   ├── foldx.py              ← predict_tm_change (opcional)
│   └── compare.py            ← compare_variants
│
├── tests/                    ← 110 unit tests + 32 integration
├── docs/                     ← ARCHITECTURE.md, DECISIONS.md, progress/
├── outputs/                  ← briefs y scouting generados (no en git)
└── structures/               ← PDB generados (no en git)
```
