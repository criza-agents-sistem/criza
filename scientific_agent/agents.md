# agents.md — Contexto activo del Agente Científico CRIZA

> Este archivo contiene solo lo que importa HOY. No es un historial.
> Para historial de decisiones → `docs/ARCHITECTURE.md` y `docs/progress/`
> Para roadmap completo → `ROADMAP.md`
> Para arquitectura de plataforma → `CLAUDE.md` y `agents.md` en `criza/` (repo padre)

---

## Contexto del proyecto

CRIZA es la primera instancia de la plataforma EMPRESAS-IA — vertical de venture-building en
biotecnología. El **Scout multidominio quedó jubilado** (`scout.py`/`run_scouting.py` borrados,
ver `criza/agents.md` § Borrado histórico) — este repo hoy es solo el **especialista en
proteínas** (`specialist_proteins.py`), invocado por el Orquestador de `criza/` o de forma
standalone vía `run.py`.

Etapa actual: **especialista proteínas v1.4.1**.

---

## Stack activo

- **Especialista proteínas:** `specialist_proteins.py` — ESMFold/ProteinMPNN/FoldX, modelo
  configurable (`SPECIALIST_MODEL` en `.env`)
- **Runner:** `run.py`
- **Literatura:** OpenAlex API (250M+ papers, primaria desde v1.4.1) — fallback Semantic Scholar
- **ESMFold:** Modal serverless — `ESMFOLD_POD_URL` en `.env`, leído en runtime por
  `tools/esmfold_local.py::_get_pod_url()`. **Servicio movido el 2026-08-14** de
  `EMPRESAS-IA/services/esmfold/` a `criza/services/esmfold/` (repo padre, carpeta hermana de
  los agentes) — mismo nombre de app Modal (`criza-esmfold`) y mismo workspace (`criza-dev`) →
  la URL no cambió, cero acción necesaria acá. Deploy/redeploy se corre desde la raíz de
  `criza/`, no desde este repo: `modal deploy services/esmfold/modal_app.py`.
- **RunPod: JUBILADO.** El pod `qruo50jffhrgze` (H200 SXM) fue reemplazado por Modal — no
  volver a levantarlo. La sección "Protocolo RunPod" de `ROADMAP.md` describe el flujo viejo,
  queda como historia hasta que se limpie ese doc (fuera de alcance de hoy).
- **Tests:** pytest, 110 unit tests pasando (`pytest -m "not integration"`), 32 integration
- **Modelo:** `SPECIALIST_MODEL` en `.env`, configurable por agente

---

## Pendientes / flags abiertos

Documentados también en `criza/auditor_registry.yaml` (comentario 2026-07-06, AUDIT-C16/C17) —
se dejan a propósito para que el auditor determinístico del KM los siga marcando hasta que se
cierren:

- [ ] **C16 (ALTO):** `specialist_proteins.py` no implementa el contrato estándar de agentes
  SEB-115 (`INPUT_CONTRACT`/`OUTPUT_CONTRACT`/`run()` async) — es síncrono, devuelve texto
  plano, y está registrado como stub (`"cientifico_especialista": None`) en
  `criza/orquestador/registry.py`. No lo puede invocar el Orquestador todavía.
- [ ] **C17 (ALTO):** `specialist_proteins.py` no escribe nada al Knowledge Module — solo
  persiste un `.md` local en `outputs/`. Viola la regla de escritura al KM (todo output de un
  agente debe quedar en el KM, sin excepción). Es el agente más viejo del proyecto, nunca
  migrado.
- [ ] **C5 (MEDIO):** falta `docs/DESIGN_GATE.md` propio de este módulo — los demás agentes de
  CRIZA lo tienen, este no.
- [ ] **Repo nested sin destino decidido** — este repo (`scientific_agent/`) es un git repo
  independiente (`github.com/CRIZA-ia/scientific`), ignorado por `criza/.gitignore` con el
  comentario "decisión pendiente: ¿submódulo? ¿fusionar historia?". Sigue sin resolver.
- [ ] **Cambios sin commitear en este repo** (detectados 2026-08-14, no son de esta sesión):
  borrado de `scout.py`/`run_scouting.py`/`tests/test_scout.py`/`agents.md` viejo (jubilación
  del scout, ya reflejada en `criza/agents.md`), y actualización de `.env.example`/`ROADMAP.md`/
  `tools/esmfold_local.py` con la migración RunPod→Modal. Nada de esto se commiteó todavía en
  este repo — revisar y commitear cuando corresponda (no se tocó hoy, es un repo aparte).

---

## Reglas específicas

- `load_dotenv()` corre **antes** de importar tools — bug histórico resuelto, no revertir
- `ESMFOLD_POD_URL` se lee en runtime con `_get_pod_url()`, nunca al importar
- Tests de integración excluidos por defecto: `pytest -m "not integration"`
- Outputs y PDB en `.gitignore` — se regeneran, no van al repo
- `ROADMAP.md` = fuente de verdad del estado de desarrollo del agente (desactualizado en la
  sección RunPod, ver Pendientes)

---

## Dónde están las cosas

```
scientific_agent/
├── specialist_proteins.py    ← único agente activo (especialista proteínas)
├── run.py                    ← runner standalone
├── agents.md                 ← este archivo
├── ROADMAP.md                ← versiones y estado (fuente de verdad dev)
│
├── tools/
│   ├── openalex.py           ← search_literature (PRIMARIA desde v1.4.1)
│   ├── semantic_scholar.py   ← fallback si OpenAlex falla
│   ├── uniprot.py            ← get_protein_sequence
│   ├── esmfold_local.py      ← predict_structure_local (Modal, ver Stack activo)
│   ├── esmfold.py            ← predict_structure (fallback API pública, 200aa)
│   ├── stability.py          ← analyze_stability
│   ├── variants.py           ← design_variants (rule-based)
│   ├── mpnn.py                ← design_variants_mpnn (opcional)
│   ├── foldx.py               ← predict_tm_change (opcional)
│   └── compare.py            ← compare_variants
│
├── tests/                    ← 110 unit tests + 32 integration
├── docs/                     ← ARCHITECTURE.md, DECISIONS.md, ONBOARDING.md (falta DESIGN_GATE.md — C5)
├── outputs/                  ← briefs generados (no en git)
└── structures/               ← PDB generados (no en git)
```
