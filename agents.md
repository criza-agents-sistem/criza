# agents.md — Contexto activo del Agente Científico CRIZA

> Este archivo contiene solo lo que importa HOY. No es un historial.
> Para historial de decisiones → `docs/ARCHITECTURE.md` y `docs/progress/`
> Para roadmap completo → `ROADMAP.md`

---

## Contexto del proyecto

Agente de IA que analiza la viabilidad técnica de producir moléculas de alto valor por fermentación microbiana. Dado un objetivo de producción, ejecuta un pipeline computacional (literatura → secuencia → estructura → variantes → brief) y entrega hipótesis priorizadas para que el laboratorio valide solo las más prometedoras. Comprime semanas de diseño experimental en minutos.

Etapa actual: **v1.4.1 en uso** — transición planificada a cloud deployment con interfaz (SEB-96).

---

## Stack activo

- **Lenguaje:** Python 3.13
- **Motor de razonamiento:** Claude claude-sonnet-4-5 (Anthropic API) con tool use
- **Literatura:** OpenAlex API (250M+ papers, free) — fallback a Semantic Scholar
- **Secuencias:** UniProt REST API
- **Estructura:** ESMFold local via RunPod (pod `qruo50jffhrgze`, H200 SXM) — fallback a ESM Atlas API (200aa)
- **Variants:** Rule-based (tools/variants.py) + ProteinMPNN opcional + FoldX opcional
- **Tests:** pytest, 110 unit tests
- **Infra:** RunPod Secure Cloud, network volume `criza-workspace` 30GB US-CA-2

---

## Linear

- **Proyecto:** CRIZA
- **Equipo:** Sebabizz._dev
- **Cycle activo:** Cycle 2 (hasta 01/06/2026)
- **Milestone actual:** M1 — Base sólida (en curso) → M2 Knowledge Module (próximo)

---

## Pendientes / flags abiertos

- [ ] **SEB-96** — Agente de Mercado v0 (web search + COMTRADE + email) — próxima feature principal
- [ ] **SEB-109** — Docker: verificar que `docker compose run --rm scientific-agent` funciona (requiere Sebas)
- [ ] **SEB-110** — Branch strategy: configurar protection rules en GitHub (requiere Sebas en github.com)
- [ ] **SEB-111** — GitHub Actions CI — workflow creado, pendiente activar en repo
- [ ] **SEB-94** — FoldX: registrarse en foldxsuite.crg.eu y descargar binario
- [ ] **SEB-95** — Migración ESMFold a serverless (RunPod Serverless o Modal)
- [ ] **SEB-61** — Knowledge Module schema DPN: bloqueado esperando consulta con Defensoría
- [ ] Pod RunPod `qruo50jffhrgze` debe estar STOPPED cuando no se usa ($4.39/hr mientras corre)

---

## Protocolo RunPod — leer antes de análisis con proteínas largas

El pod está **APAGADO por defecto**.

Para análisis con `predict_structure_local` (proteínas >200aa):
1. cloud.runpod.io → Pods → Start (`mighty_brown_lark`)
2. Esperar ~3-5 min para que startup.sh levante ESMFold
3. Verificar: `curl https://qruo50jffhrgze-8000.proxy.runpod.net/health`
4. Al terminar → Stop (no Terminate)

---

## Reglas específicas de este proyecto

- `load_dotenv()` debe correr **antes** de importar tools — bug histórico resuelto, no revertir
- `ESMFOLD_POD_URL` se lee en runtime con `_get_pod_url()`, nunca al importar el módulo
- Tests de integración excluidos por defecto: `pytest -m "not integration"`
- Outputs y estructuras PDB están en `.gitignore` — se regeneran, no van al repo
- `ROADMAP.md` es la fuente de verdad del estado de desarrollo del agente

---

## Dónde están las cosas

```
scientific_agent/
├── agent.py              ← loop agéntico + system prompt + tool dispatch
├── run.py                ← CLI interactivo (casos preconfigurados)
├── run_scouting.py       ← runner para scouting de oportunidades agro
├── agents.md             ← este archivo
├── ROADMAP.md            ← versiones y estado (fuente de verdad dev)
│
├── tools/                ← una herramienta por archivo
│   ├── openalex.py       ← search_literature (PRIMARIA desde v1.4.1)
│   ├── semantic_scholar.py ← fallback si OpenAlex falla
│   ├── uniprot.py        ← get_protein_sequence
│   ├── esmfold_local.py  ← predict_structure_local (RunPod, sin límite de longitud)
│   ├── esmfold.py        ← predict_structure (API pública, max 200aa, fallback)
│   ├── stability.py      ← analyze_stability
│   ├── variants.py       ← design_variants (rule-based)
│   ├── mpnn.py           ← design_variants_mpnn (ProteinMPNN, opcional)
│   ├── foldx.py          ← predict_tm_change (FoldX, opcional)
│   └── compare.py        ← compare_variants
│
├── tests/                ← 110 unit tests + 32 integration (excluidos por defecto)
├── docs/                 ← ARCHITECTURE.md, DECISIONS.md, ONBOARDING.md, progress/
├── outputs/              ← briefs generados (no en git)
└── structures/           ← PDB generados (no en git)
```
