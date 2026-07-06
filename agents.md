# agents.md — CRIZA-biotech

> Contexto activo para Claude. Máximo ~200 líneas.
> Detalle técnico profundo → `ROADMAP.md` de cada componente.
> Arquitectura de plataforma → `../KRIZA_Foundation_Document.md`

---

## ⚠️ ESTADO — estructura redefinida (rethink, cerrada a nivel diseño 2026-06-13)

El sistema fue **rediseñado**. **Fuente de verdad del diseño nuevo:** `docs/architecture.md` [2026-06-13]
(decisiones D1–D10) + épico Linear **SEB-143** + `docs/progress/2026-06-13.md` + memoria
`project_rethink_convergente`. Cambios de fondo:
- **Entregable = "expediente de decisión"** (el sistema ARMA, el humano ELIGE) — no una recomendación/embudo.
- **Múltiples puertas de entrada** (sector / dolor / tecnología / planta-recurso / empresario) → un mismo expediente.
- **Set de agentes nuevo:** Descubrimiento de Demanda (divergente redefinido) · Evidencia Científica (amplía
  el científico) · Mercado (repotenciado) · Investigación Amplia (NUEVO) · Armador (convergente transformado,
  sin embudo). Fase 2 = familia Diseño y Desarrollo. Orquestador = **motor dirigido por objetivo (semilla del CEO)**.
- **Transversal:** KM como sustrato (seam) + loop de aprendizaje (lecciones, SEB-156) + veracidad por dato.
- **Próximo = construcción:** SEB-150 (conector CONICET) + SEB-145 (Armador). Design Gate antes de cada agente.

> La tabla "Agentes activos" de abajo describe el **código que existe HOY** (punto de partida), que el
> rethink va a transformar. Leerla como estado actual, NO como diseño objetivo (ese está en architecture.md).

---

## Qué es CRIZA

Primera empresa agéntica de la plataforma EMPRESAS-IA (Capa 2). Sistema de transferencia de tecnología
ciencia-industria, foco biotech agro argentino. **Diseño vigente:** múltiples puertas de entrada →
Orquestador (motor dirigido por objetivo) → agentes investigadores → Armador → **expediente de decisión** →
el humano decide. (El pipeline viejo Scout→Especialista→Mercado quedó superado por el rethink — ver banner.)

---

## Agentes activos

| Agente | Archivo | Versión | Estado | Detalle |
|---|---|---|---|---|
| Investigación Amplia | `investigacion_amplia/investigacion_amplia.py` | v2.1 | ✅ SEB-146+204 | análisis EXHAUSTIVO del sector (no muestrea); 7 tools (expand_agrovoc + get_sector_corpus + search_corpus_cientifico + fetch_paper_full_text + search_literature + fetch_page_text + submit); marco_blue_ocean_CRIZA.md + metodologia_busqueda_AGENTE.md cargados en runtime (mismo patrón que armador); pre-flight INTA+CONICET **ahora vía `knowledge_module/preflight.py` genérico** (era inline, migrado 2026-07-02 — era el origen del patrón pero había quedado sin migrar); `fetch_paper_full_text` unificado (INTA `documento` + CONICET `ficha`); TRL obligatorio para TODO candidato alta prioridad, `cobertura_texto_completo` estructural (ya no discrecional); `fuentes_y_cobertura` obligatorio (gap encontrado por el auditor 2026-07-02, no lo tenía); contrato SEB-115 v2.1; **37/37 unit tests**. `investigacion_amplia/docs/DESIGN_GATE.md` |
| Mercado | `market_agent/market_agent.py` | v1.1 | ✅ SEB-148+115 | demand-first; cruces 1/3/4; corpus_cientifico exhaustivo (limit=100) + series + SENASA + **web_search nativo Anthropic** (Cruce 3 ya no depende de URLs conocidas); marco_blue_ocean_CRIZA.md cargado en runtime; campos estructurales `sustitucion_importacion` (condición 12) + `valor_cliente` (6 dimensiones) + `fuentes_y_cobertura`; pre-flight bloqueante; loop aprendizaje; contrato estándar; `buscar_corpus_cientifico` movido a `criza/utils/corpus.py` (compartido con evidence_generalista); **63/63 unit tests**. `market_agent/ROADMAP.md` |
| Evidence Generalista | `evidence_generalista/evidence_generalista.py` | v1.2 | ✅ 2026-07-02 | technology-agnostic; cruce 2; corpus INTA exhaustivo (vía get_sector_corpus, no FTS con LIMIT) + **corpus_cientifico/CONICET vía `buscar_corpus_cientifico`** (gap cerrado 2026-07-02 — antes tenía CERO acceso a CONICET pese a estar documentado como deuda desde 2026-06-16) + AGROVOC; marco_blue_ocean_CRIZA.md cargado en runtime; `fuentes_y_cobertura` obligatorio; pre-flight bloqueante (INTA + corpus_cientifico); contrato estándar v1.2; **47/47 unit tests**. `evidence_generalista/docs/DESIGN_GATE.md` |
| Armador | `armador/armador.py` | v1.2 | ✅ SEB-145 | ENSAMBLADOR (no sintetizador); carga `expediente_decision_SPEC.md` en runtime; expediente 5-10 págs; 8 secciones; valida cobertura aguas arriba (sin mercado → bloqueante); `bloque_3.cobertura_global` calculado (no autoreportado); **25/25 unit tests**. |
| Especialista proteínas | `scientific_agent/specialist_proteins.py` | v1.4.1 | ✅ | `scientific_agent/ROADMAP.md` |
| Motor v2 | `orquestador/motor.py` + `registry.py` + `flows/*.yaml` | v2.0 | ✅ SEB-197 | ejecuta flows YAML sin LLM; km_write / agent / gate_humano; routing declarativo; **28/28 unit tests**. |
| **Auditor** | `knowledge_module/auditor/` (Capa 1) + `criza/auditor_registry.yaml` (Capa 2, config) | v1.0 | ✅ 2026-07-02 | **Nuevo.** Verificador determinístico (no LLM — decisión A del gate) contra datos reales del KM y código fuente: 5 checks — población de campos declarados vs real (con `segmentar_por` para no esconder gaps de un repositorio detrás del promedio), cobertura de fuentes propias entre agentes hermanos, sampling no declarado, decisiones diferidas sin revisar (grep filas de tabla en DESIGN_GATE/ROADMAP), contrato `fuentes_y_cobertura`. Corrida real (primera vez): encontró y se usó para cerrar el gap de `fuentes_y_cobertura` faltante en investigacion_amplia. Uso: `cd knowledge_module && python -m auditor --registry ../criza/auditor_registry.yaml --root ..`. **14/14 unit tests**. `knowledge_module/docs/AUDITOR_DESIGN_GATE.md` |

## Borrado (histórico)

Movido a `criza/_archivo_temporal/` el 2026-07-01, confirmado sin referencias vivas (grep en todo
el repo) y **borrado definitivamente el 2026-07-02**. Ya no existe en el filesystem.

| Qué era | Por qué se borró |
|---|---|
| `divergent_agent/` | Reemplazado por Investigación Amplia. Sus assets vigentes (marco_blue_ocean, metodologia_busqueda) están en `docs/`. |
| `convergent_agent/` | Reemplazado por Mercado + Evidence + Armador. Paradigma distinto (converger a 1 → el sistema elige), reemplazado por expediente donde el humano elige. |
| `orquestador_v1.py` + `run.py` | Orquestador v1 LLM puro, reemplazado por Motor v2 YAML. |
| `scout.py` + `run_scouting.py` | Scout jubilado, marcado JUBILADO en agents.md. |
| `metodologia_convergente_AGENTE.md` | Metodología del convergente muerto. |

> **Replanteo 2026-06-02:** el descubrimiento pasa de **supply-first** (scout: "¿qué podemos
> producir?") a **demand-first** ("¿dónde hay demanda reprimida que el biotech destrabaría?").
> El scout se jubila; sus partes buenas se absorben en el agente divergente nuevo. Diverge y
> converge son dos agentes especializados acoplados por un **artefacto con schema definido**
> (no comunicación en vivo). Detalle y trazabilidad completa en `docs/architecture.md`.
>
> **Principio de veracidad (obligatorio en ambos agentes nuevos):** datos comprobados, no
> suposiciones. El output alimenta una decisión de inversión real. Todo dato lleva etiqueta
> [VERIFICADO]/[ESTIMADO]/[INFERIDO] + fuente. Gap declarado > inferencia disfrazada de hecho.

---

## Stack activo

- **Modelos:** SCOUT_MODEL · SPECIALIST_MODEL · MARKET_MODEL — configurables en `.env` de cada componente
- **Default:** `claude-sonnet-4-6` para todos. Cambiar a Opus para análisis profundos.
- **Literatura:** OpenAlex API (250M+ papers, sin key) — fallback Semantic Scholar
- **INTA Digital:** OAI-PMH (`repositorio.inta.gob.ar/oai/request`) + discover scraping — `criza/utils/inta.py`; AGROVOC tesauro — `criza/utils/agrovoc.py`
- **Document Store (Capa 0-1):** `plataforma/document_store/store.py` — descarga PDFs + extrae texto (pypdf)
- **GPU / Compute:** Modal serverless — ESMFold en `criza-esmfold`, BGE-m3 en `criza-bge-m3`
- **RunPod:** pod `qruo50jffhrgze` (H200 SXM) — **REEMPLAZADO por Modal. Mantener apagado.**
- **Tests:** pytest con markers `unit` / `integration`

---

## Linear

- **Proyecto:** CRIZA | **Equipo:** Sebabizz._dev
- **Cycle activo:** ver Linear directamente (no hardcodeado acá — mismo motivo que la sección de arriba)

---

## Estado operativo — ver Linear

El estado de tareas (qué está Done/In Progress/Todo, en qué orden) vive en **Linear**
(proyecto CRIZA, equipo Sebabizz._dev) — es la fuente de verdad según la tabla de este mismo
CLAUDE.md, no este archivo. Este archivo no duplica esa lista: la duplicación es lo que hizo
que este archivo se desactualizara (alguien actualiza Linear, se olvida de actualizar acá, o
viceversa) y creciera muy por encima de su propio límite de ~200 líneas.

Bloqueadores estructurales que **no** tienen equivalente en Linear (decisiones de arquitectura
pendientes, no tareas ejecutables):

- [ ] Rotar password Neon (acción manual de Sebas, no una tarea de desarrollo)
- [ ] Renombrar carpeta `EMPRESAS-IA/` (hoy `KRIZA/`) — pendiente migración de memoria de Claude
- [ ] **Auditoría objective-first "qué falta para que todo funcione"** — absorbida y ampliada por
      la auditoría de cumplimiento de plataforma 2026-07-05/06 (bullet siguiente). No generar un
      tercer plan paralelo.
- [ ] **Auditoría de cumplimiento de plataforma (2026-07-05/06)** — sin cambios de código, solo
      lectura. 24 hallazgos propios de CRIZA (C1-C24): 5 de Design Gate/estructura (sin CLAUDE.md
      propio, checkbox falso, gates desactualizados) + 10 de **código transversal atrapado en
      Capa 2** (openalex.py, token_tracker.py, inta.py duplicando el harvester genérico — el
      hallazgo prioritario, ver principio de plataforma-primero) + 5 sin issue en Linear todavía
      (límite del plan gratuito) incluyendo que **el loop de aprendizaje está roto en Motor v2**
      (nunca persiste lecciones) y `specialist_proteins.py` no escribe al KM ni tiene contrato
      SEB-115. Detalle completo + evidencia: `../docs/AUDITORIA_CUMPLIMIENTO_2026-07-05.md`.
      Issues: SEB-244 a SEB-248, SEB-266 a SEB-275. Panel: `../plataforma/control_panel/`.
      **Pendiente: revisar cada uno con Sebas antes de resolver.**

---

## Knowledge Module — estado rápido

| Capa | Qué hace | Versión | Estado |
|---|---|---|---|
| DB (Neon) | 5 tablas: corrida, oportunidad, aprendizaje, documento, corrida_oportunidad, corrida_documento | v0.7 schema | ✅ live |
| ORM | SQLAlchemy async — modelos: Corrida, Oportunidad, Aprendizaje, Documento, CorridaOportunidad, CorridaDocumento | v0.3 | ✅ |
| Ingesta interna | `ingest_corrida.py`: guarda Corrida → Documento (completo) → Oportunidades (extraídas por Haiku) | v0.2 | ✅ auto-conectado al divergente |
| Ingesta externa | `tools/store.py::store_fuente_externa` + `batch_store_fuentes_externas` (ON CONFLICT DO NOTHING, atómico) — dedup por fuente_url, idempotente | v0.2 | ✅ 2026-06-27 |
| Harvest INTA | `criza/ingest/harvest_inta.py`: OAI-PMH → KM, CICVyA completo — **1.643 documentos en DB (`documento`)**. Taxonomía `tipo` corregida 2026-06-30: COLECCION_TIPO (24 col_ID → tipo) + fix bug `institutos` (s.text vs s.attrib). Distribución post-backfill: ~1.088 paper · 168 ponencia · 91 tesis · ~168 reporte · 9 parte_libro · 5 libro · 4 divulgacion · 1 folleto. | v0.2 | ✅ 2026-06-30 |
| Download PDFs INTA | `criza/ingest/download_pdfs.py`: descarga bitstreams open-access + extrae texto → `texto_completo` en KM. `_sanitize()` elimina null bytes y surrogates. **~984 docs con texto completo** (de 1.643; ~610 sin PDF público accesible). | v0.1 | ✅ 2026-06-29 |
| Migración INTA → corpus_cientifico | `criza/ingest/migrate_inta_to_corpus.py`: copia `documento` (agente=harvest) → `ficha/corpus_cientifico` con embeddings BGE-m3, sin tocar `documento`. **1.643/1.643 migrados, 0 errores**. Cierra el gap de búsqueda semántica que INTA no tenía (solo FTS). `documento` queda como fuente de `get_sector_corpus` (FTS exhaustivo); `corpus_cientifico` como fuente de `search_corpus_cientifico` (semántico, filtrable por `repositorio`). Costo Modal: ~$0,003/registro (CPU-only, no GPU). **Gap encontrado 2026-07-02: `_doc_a_campos` migraba metadata pero descartaba `texto_completo` — 1.643/1.643 fichas quedaron con el campo vacío pese a que ~984 lo tenían en `documento`.** Fix: bug corregido en el script (para migraciones futuras) + `criza/ingest/backfill_inta_texto_completo.py` (nuevo) parcheó las 1.643 fichas ya existentes vía `motor_api.actualizar_props` (no re-vectoriza). **Backfill real: 984/1.643 actualizadas, 659 sin match en `documento` (genuinamente sin PDF), 0 errores.** | v1.1 | ✅ 2026-07-02 |
| `oai_pmh.py` — open_access | `knowledge_module/connectors/oai_pmh.py`: detecta `dc:rights` en el harvest OAI-PMH — verificado en vivo contra CONICET (vocabulario eu-repo). Genérico, sirve para cualquier repositorio DSpace (CONICET, INTA si se re-cosecha, futuro). | v1.1 | ✅ 2026-07-02 |
| Full-text CONICET (+genérico) | `knowledge_module/ingesta/download_corpus_pdfs.py`: para fichas `open_access=true` sin `texto_completo`, scrapea la landing page (patrón DSpace bitstream, descarta links `isAllowed=n`), descarga+extrae. Bulk, no bajo demanda — cierra gap de sesgo donde el agente decidía discrecionalmente qué texto leer. `_sanitize()` reusa el fix de null bytes de `download_pdfs.py` (INTA). `find_pdf_access()` distingue 3 estados (no 2): descargable / **requiere_solicitud** (con `solicitud_url` autoservicio "Consultar", o sin ella si es bitstream `isAllowed=n` — hay que pedirlo a mano, ej. contacto CONICET) / nada — declarado siempre, nunca en silencio (verificado a mano por Sebas, 3 casos reales). `get_ficha_full_text` surfacea el estado real en el error, no un "no disponible" genérico. **Backfill final: 430/625 con texto completo (68,8%) · 162/625 requiere solicitud (11 con autoservicio, 151 sin) · 33/625 genuinamente sin nada.** Motivado por auditoría de sesgos 2026-07-02, ver `orchestration-layer.md` Decisión 6. | v1.1 | ✅ 2026-07-02 |
| FTS | `fts_vector` GENERATED STORED + GIN index; `search_fuentes_externas` (FTS sobre Documento); 8/8 tests `test_batch_store.py` | v0.1 | ✅ 2026-06-27 |
| MCP server | `server.py`: 6 tools — km_store_corrida, km_store_opportunity, km_store_learning, km_search, km_get_opportunity, km_update_opportunity, **km_search_fuentes_externas** | v0.2 | ✅ 2026-06-27 |
| Embeddings | BGE-m3 self-hosted en Modal, 1024 dims | prod | ✅ SEB-121 — swap completo, 44 filas migradas |
| Pre-flight genérico | `knowledge_module/preflight.py`: `FuenteCheck`/`run_preflight()` — patrón objective-first (bloqueante/advertencia) generalizado de investigacion_amplia a los 4 agentes. Ver `docs/orchestration-layer.md` Decisión 6. | v1.0 | ✅ 2026-07-02 — **6/6 unit tests** |
| Tests | 7 unit (tools) + 5 unit (ingest) + 2 integration | — | ✅ 14/14 |

---

## Dónde están las cosas

```
EMPRESAS-IA/                     ← carpeta raíz (hoy nombrada KRIZA/)
├── KRIZA_Foundation_Document.md ← arquitectura de 4 capas de la plataforma
├── docs/playbook.md             ← norma Capa 0 para todos los repos
├── STATUS.md                    ← decisiones de la fase de diseño inicial
│
├── plataforma/                  ← Capa 0-1 genérica (reutilizable por CRIZA, DPN, futuras)
│   └── document_store/
│       ├── store.py             ← descarga PDFs + extrae texto; keyed por instance
│       └── data/{instance}/     ← PDFs en disco (ignorados en git)
│
└── criza/                       ← este repo: CRIZA-biotech (Capa 2)
    ├── agents.md                ← este archivo
    ├── docs/
    │   ├── architecture.md      ← decisiones técnicas del sistema CRIZA
    │   └── progress/            ← logs de sesión (YYYY-MM-DD.md)
    ├── utils/
    │   ├── agrovoc.py           ← cliente AGROVOC (FAO tesauro) — expand_term
    │   ├── inta.py              ← conector INTA Digital (OAI-PMH + discover)
    │   └── openalex.py          ← cliente OpenAlex
    ├── ingest/
    │   └── harvest_inta.py      ← orquestador harvest: OAI-PMH → KM (CICVyA 1640 registros)
    ├── divergent_agent/
    │   └── test_metodologia.py  ← agente divergente + auto-ingesta en KM
    ├── convergent_agent/
    │   ├── convergent_agent.py  ← agente convergente (embudo N→1)
    │   ├── km_selector.py       ← el seam: selección de input desde el KM (Auto/Manual)
    │   ├── run.py               ← runner + ingesta 3 capas
    │   ├── ROADMAP.md · docs/DESIGN_GATE.md
    │   └── tests/               ← 12 unit + 2 integration
    ├── scientific_agent/
    │   ├── ROADMAP.md           ← estado del agente científico (fuente de verdad)
    │   ├── scout.py · specialist_proteins.py · run.py · run_scouting.py
    │   ├── tools/               ← 9 tools (OpenAlex, UniProt, ESMFold, etc.)
    │   └── tests/               ← 110 unit + 32 integration
    ├── market_agent/
    │   ├── ROADMAP.md · docs/DESIGN_GATE.md
    │   ├── market_agent.py · run.py
    │   ├── tools/               ← 6 tools (corpus CONICET, series, stats, web, email, corpus)
    │   └── tests/               ← 32 unit (8 nuevos v1)
    ├── investigacion_amplia/
    │   ├── investigacion_amplia.py  ← 5 tools; cruce 3 + mapa_candidatos; SEB-146
    │   ├── docs/DESIGN_GATE.md      ← decisiones de diseño, 🟡 Listo con deuda
    │   └── tests/               ← 18 unit tests
    ├── orquestador/
    │   ├── orquestador.py       ← v1 LLM puro (legacy)
    │   ├── motor.py             ← v2 motor YAML declarativo (SEB-197) ✅
    │   ├── registry.py          ← lazy imports de todos los agentes
    │   ├── flows/
    │   │   ├── pipeline_dolor.yaml   ← dolor → market + evidence + armador
    │   │   └── pipeline_sector.yaml  ← sector → IA + gate humano + market + evidence + armador
    │   ├── docs/DESIGN_GATE.md · DISEÑO_MOTOR_ORQUESTADOR.md
    │   └── tests/               ← 28 unit (motor v2)
    └── armador/
        ├── ROADMAP.md · docs/DESIGN_GATE.md
        ├── armador.py · run.py
        └── tests/               ← 14 unit

EMPRESAS-IA/knowledge_module/    ← Capa 1 — memoria semántica compartida
    ├── README.md · ROADMAP.md · schema.sql
    ├── db.py · embeddings.py · server.py
    ├── ingest_corrida.py · ingest_historico.py
    ├── tools/store.py           ← store_fuente_externa (papers, normas, etc.)
    ├── migrate_documento_v03.py ← migración DB: columnas nuevas + constraints expandidos
    ├── migrations/001_v02_tenant_documento.sql
    ├── tests/ (14 tests)
    └── docs/ KM_DESIGN_GATE.md · architecture.md
```

---

## Convención para agregar un nuevo agente

Seguir esta estructura y checklist exactos para que cualquier agente nuevo sea plug-in.

### Estructura de archivos

```
nuevo_agente/
├── nuevo_agente.py    ← TOOLS + SYSTEM_PROMPT + dispatch_tool() + run_agent()
├── run.py             ← runner interactivo con casos de ejemplo
├── ROADMAP.md         ← versiones, tools activas, estado, próximos pasos
├── .env.example       ← ANTHROPIC_API_KEY + NUEVO_MODEL + keys específicas
├── requirements.txt
├── tools/
│   ├── __init__.py    ← exports de todas las tools
│   └── <tool>.py      ← una tool por archivo, retorna dict estándar
└── tests/
    ├── __init__.py
    ├── conftest.py    ← fixtures + markers (unit / integration)
    └── test_<tool>.py ← un archivo por tool
```

### Contrato estándar de agentes (SEB-115 — obligatorio para todos los agentes nuevos)

Todo agente debe exponer en su módulo principal:

```python
INPUT_CONTRACT  = {"agent": str, "version": str, "fields": {caso, tarea, contexto, conocimiento, herramientas}}
OUTPUT_CONTRACT = {"agent": str, "version": str, "fields": {análisis, nivel_confianza, recomendaciones, próximo_agente, nuevo_conocimiento}}

async def run(contract_input: dict, verbose: bool = False, model: str = DEFAULT_MODEL) -> dict:
    """Interfaz de contrato estándar para el Orquestador. Wraps run_agent()."""
    ...
```

- `próximo_agente`: `None` si el Orquestador decide routing, nombre del agente si el agente mismo sabe (e.g. `"cientifico_especialista"` del Evidence Generalista)
- `nivel_confianza`: `"alto" | "medio" | "bajo"` derivado de los estados epistémicos del output
- `nuevo_conocimiento`: lista de strings → van al loop de aprendizaje

### Contrato de output de tools (obligatorio)

```python
{
    "success": bool,
    "data": ...,           # el resultado útil
    "source": "...",       # "[VERIFICADO]" | "[ESTIMADO, fuente: X]" | "[INFERIDO]"
    "error": str | None,   # None si success=True, mensaje claro si False
}
```

### Checklist de creación (= Definition of Done del agente)

1. Estructura de archivos según template
2. SYSTEM_PROMPT con workflow obligatorio + etiquetas de confianza en output
3. Tools en `tools/` con contrato estándar de output
4. Tests: unit con mocks + al menos 1 integration por tool → todos pasando
5. `.env.example` completo
6. `ROADMAP.md` con versión inicial, tools, próximos pasos
7. Agregar entrada en tabla "Agentes activos" de este `agents.md`
8. Issue en Linear → Done con DoD verificado

---

## REGLAS OPERATIVAS — no modificar, no borrar

> Esta sección se lee en cada sesión y permanece fija durante toda la vida del proyecto.

### Definition of Done

Una tarea de código está Done cuando:

- [ ] El código funciona según lo especificado
- [ ] Tiene tests para funciones críticas
- [ ] No hay credenciales expuestas en el código
- [ ] **`agents.md` — tabla "Agentes activos" actualizada si el módulo cambió de versión/estado.
      Obligatorio, no discrecional — mismo criterio que `architecture.md` ("registrar en el
      momento de la decisión", no "después"). Si terminaste la sesión y esta tabla no refleja
      lo que cambiaste, la sesión no está cerrada.**
- [ ] La sesión está documentada en `docs/progress/YYYY-MM-DD.md`

Verificar esta lista ANTES de mover un issue a Done en Linear.

### SDLC — fases activas

No avanzar a la siguiente fase sin confirmar que la anterior está resuelta:

Planificación → Requerimientos → Diseño → Desarrollo → Testing → Deployment → Mantenimiento

### Seguridad mínima siempre activa

- Nunca hardcodear credenciales. Siempre variables de entorno.
- `.env` siempre en `.gitignore` antes del primer commit.
- Antes de cada commit: verificar que no hay credenciales expuestas.

### Linear — workflow

- Al iniciar tarea → In Progress
- Al completar tarea → verificar DoD → Done → avisar al usuario y esperar instrucción
- Issues no completados al cerrar cycle → vuelven a backlog, no se arrastran solos
