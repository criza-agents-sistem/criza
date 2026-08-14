# agents.md — CRIZA-biotech

> Contexto activo para Claude. Máximo ~200 líneas.
> Detalle técnico profundo → `ROADMAP.md` de cada componente.
> Arquitectura de plataforma → `KRIZA_Foundation_Document.md` en el repo `EMPRESAS-IA/docs/`
> (plataforma, repo separado — no hay path relativo válido entre `criza/` y `EMPRESAS-IA/` desde
> que CRIZA es su propio repo)

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
| Investigación Amplia | `investigacion_amplia/investigacion_amplia.py` | v2.2 | ✅ SEB-146+204 | análisis EXHAUSTIVO del sector (no muestrea); 7 tools (expand_agrovoc + get_sector_corpus + search_corpus_cientifico + fetch_paper_full_text + search_literature + fetch_page_text + submit); marco_blue_ocean_CRIZA.md + metodologia_busqueda_AGENTE.md cargados en runtime (mismo patrón que armador); pre-flight INTA+CONICET **ahora vía `knowledge_module/preflight.py` genérico** (era inline, migrado 2026-07-02 — era el origen del patrón pero había quedado sin migrar); `fetch_paper_full_text` unificado (INTA `documento` + CONICET `ficha`); TRL obligatorio para TODO candidato alta prioridad, `cobertura_texto_completo` estructural (ya no discrecional); `fuentes_y_cobertura` obligatorio (gap encontrado por el auditor 2026-07-02, no lo tenía); contrato SEB-115 v2.1; + guarda de truncado por `max_tokens` (2026-07-22); **v2.2 (2026-07-22): lee `tarea`/`contexto` del contrato** (antes se descartaban — cable cortado, ver `check_contrato_input_no_leido`) + `system` con `cache_control` (prompt caching, verificado con llamada real: cache_read=8408 en la 2ª llamada); **39/39 unit tests**. `investigacion_amplia/docs/DESIGN_GATE.md` |
| Mercado | `market_agent/market_agent.py` | v1.3 | ✅ SEB-148+115 | demand-first; cruces 1/3/4; corpus_cientifico exhaustivo (limit=100) + series + SENASA + **web_search nativo Anthropic** (Cruce 3 ya no depende de URLs conocidas); marco_blue_ocean_CRIZA.md cargado en runtime; campos estructurales `sustitucion_importacion` (condición 12) + `valor_cliente` (6 dimensiones) + `fuentes_y_cobertura`; pre-flight bloqueante; loop aprendizaje; contrato estándar; `buscar_corpus_cientifico` movido a `criza/utils/corpus.py` (compartido con evidence_generalista); **v1.2 (2026-07-22): el write-back de `props.mercado` al KM se movió de `run.py` al agente** — vivía en el runner, así que el camino orquestado (Motor → `run()`) nunca escribía y el Armador bloqueaba con "mercado: ausente"; + guarda de truncado por `max_tokens`; + `_derive_confidence({})` ahora da "bajo" (daba "alto"); **v1.3 (2026-07-22): lee `tarea`/`contexto`/`foco` del contrato** — `foco` es `caso` cuando además hay `oportunidad_id`: en `pipeline_sector` es `{gate.candidato_elegido}`, la respuesta del humano en el gate, que se descartaba entera + `system` con `cache_control`; **67/67 unit tests**. `market_agent/ROADMAP.md` |
| Evidence Generalista | `evidence_generalista/evidence_generalista.py` | v1.3 | ✅ 2026-07-02 | technology-agnostic; cruce 2; corpus INTA exhaustivo (vía get_sector_corpus, no FTS con LIMIT) + **corpus_cientifico/CONICET vía `buscar_corpus_cientifico`** (gap cerrado 2026-07-02 — antes tenía CERO acceso a CONICET pese a estar documentado como deuda desde 2026-06-16) + AGROVOC; marco_blue_ocean_CRIZA.md cargado en runtime; `fuentes_y_cobertura` obligatorio; pre-flight bloqueante (INTA + corpus_cientifico); contrato estándar v1.2; + guarda de truncado por `max_tokens` (2026-07-22); **v1.3 (2026-07-22): lee `tarea`/`contexto`/`foco`** (antes ni siquiera leía `caso` — cable cortado más grave de los tres agentes) + `system` con `cache_control`; **48/48 unit tests** (medido — este renglón declaraba 47, era incorrecto). `evidence_generalista/docs/DESIGN_GATE.md` |
| Armador | `armador/armador.py` | v1.4 | ✅ SEB-145 | ENSAMBLADOR (no sintetizador); carga `expediente_decision_SPEC.md` en runtime; expediente 5-10 págs; 8 secciones; valida cobertura aguas arriba (sin mercado → bloqueante); `bloque_3.cobertura_global` calculado (no autoreportado); v1.3 (2026-07-22): `MAX_TOKENS` 16000 → 32000 + `messages.stream()` + guarda de truncado ANTES de procesar bloques `tool_use`; **v1.4 (2026-07-22): `nivel_confianza` ahora es `_derive_nivel_confianza(bloque_3)`** — contado (establecidos/asumidos/a_confirmar), no `"alto" if expediente else "bajo"` (la corrida real calculó `Confianza: MEDIO` internamente y `run()` reportaba `alto` al Motor); `MAX_TOKENS` 32000 → 64000 (había quedado justo: usó 30.718); `system` con `cache_control` (SYSTEM_PROMPT 100% estático acá, cachea también entre corridas); **31/31 unit tests**. |
| Especialista proteínas | `scientific_agent/specialist_proteins.py` | v1.4.1 | 🟡 C16/C17 | **Fusionado a este repo el 2026-08-14** (era `github.com/CRIZA-ia/scientific`, repo separado — historial completo preservado vía `git subtree`). Scout multidominio jubilado en el mismo move (`scout.py`/`run_scouting.py` borrados). Sin contrato SEB-115 ni escritura al KM (C16/C17, deuda vieja, sin resolver hoy) — por eso no está enganchado al Orquestador (`registry.py` lo tiene como stub `None`). `scientific_agent/ROADMAP.md` |
| Motor v2 | `orquestador/motor.py` + `registry.py` + `flows/*.yaml` | v2.0 | ✅ SEB-197 | ejecuta flows YAML sin LLM; km_write / agent / gate_humano; routing declarativo; **28/28 unit tests**. |
| **Auditor** | `knowledge_module/auditor/` (Capa 1) + `criza/auditor_registry.yaml` (Capa 2, config) | v1.3 | ✅ 2026-07-22 | **Nuevo.** Verificador determinístico (no LLM — decisión A del gate) contra datos reales del KM y código fuente: **9 checks**. Los 7 originales: población de campos, cobertura de fuentes entre agentes hermanos, sampling no declarado, decisiones diferidas, contrato `fuentes_y_cobertura`, `km_write_ausente`, instancias no registradas. **v1.3 (2026-07-22) agregó 2 checks de contrato de conexión (RACI con dientes):** `check_contrato_input_no_leido` (campo declarado en INPUT_CONTRACT que el agente no lee = cable cortado; atrapó `tarea`/`contexto`/`caso` sin leer en los 3 agentes) y `check_km_conexion` (verifica que `km_escribe`/`km_lee` de los contratos cuadren, que la escritura esté en el módulo del agente y no en su runner —el bug del 22/07—, y cuenta piezas desconectadas). Uso (desde la raíz de `criza/`, con `knowledge_module` instalado en el entorno activo — el paquete no lee ningún `.env` propio, cargar `criza/.env` antes de invocar): `python -m knowledge_module.auditor --registry auditor_registry.yaml --root .`. **32/32 unit tests**. `knowledge_module/docs/AUDITOR_DESIGN_GATE.md` |

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
- **CONICET Digital:** OAI-PMH genérico — `utils/oai_pmh.py` (`OAIPMHHarvester`) +
  `ingest/harvest_conicet.py` (driver, antes `knowledge_module.ingesta.ingest_corpus`) +
  `config/connectors/conicet.yaml`. Movidos de `knowledge_module/` a acá el 2026-08-14 — código
  genérico sin hardcodeo de CRIZA, pero único consumidor real siempre fue CONICET/CRIZA.
- **Document Store (Capa 1):** `knowledge_module.document_store.store` (parte del paquete pip
  desde 2026-07-22, antes vivía en `plataforma/document_store/`) — descarga PDFs + extrae texto
  (pypdf). Datos propios de CRIZA en `document_store_data/` (raíz de este repo, gitignored,
  `KM_DOCUMENT_STORE_DIR` en `.env`) — movidos acá el 2026-08-14 desde
  `EMPRESAS-IA/plataforma/document_store/data/criza/`, donde habían quedado huérfanos (1.455
  PDFs) desde antes de la migración del código al paquete.
- **GPU / Compute (`services/`):** Modal serverless, apps propias de CRIZA (workspace
  `criza-dev`) — `services/esmfold/` (app `criza-esmfold`) y `services/bge-m3/` (app
  `criza-bge-m3`). Movidos de `EMPRESAS-IA/services/` acá el 2026-08-14 (mismo motivo que
  CONICET arriba: nada corre compartido en runtime, cada instancia despliega lo suyo). Mismos
  nombres de app y workspace → mismas URLs, sin cambios en `.env`. DPN sigue apuntando a
  `criza-bge-m3` por ahora (pendiente de su propio deploy — ver
  `EMPRESAS-IA/docs/km-aislamiento-diagnostico.md` §12.2-12.5, fuera de esta sesión). Cualquier
  agente puede conectarse a cualquier servicio — son hermanos, no están anidados en ningún
  agente.
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

- [ ] **Plomería del pipeline orquestado (2026-07-22) — CERRADA salvo 1 punto.** La primera
      corrida real de punta a punta destapó que `pipeline_dolor`/`pipeline_sector` **nunca habían
      producido un expediente** (el write al KM de mercado vivía en `run.py`, invisible para el
      Motor). De los 5 hallazgos de plomería, **4 arreglados en la sesión**: cable cortado
      `tarea`/`contexto`/`caso` (los 3 agentes no leían nada de eso — en `pipeline_sector` esto
      incluía la respuesta del humano en el gate, que se descartaba), `nivel_confianza` del
      armador (contado, no "¿produje un archivo?"), `MAX_TOKENS` del armador (64000), prompt
      caching en los 4 agentes (verificado con llamada real a la API, no mock: cache_read=8408
      en la 2ª llamada). El auditor ganó 2 checks nuevos (`check_contrato_input_no_leido`,
      `check_km_conexion`) que verifican estas conexiones contra el código real — "RACI con
      dientes" en vez de tabla en prosa. **Queda 1 punto, no es plomería:** `objetivo` decorativo
      del motor — es la pregunta de fondo del rediseño del conductor, documentada como decisión
      abierta, no un bug. Detalle completo: `docs/progress/2026-07-22.md`. Diseño abierto (NO
      decidido): `EMPRESAS-IA/docs/PROPUESTA_CONDUCTOR.md` (repo plataforma, separado).
- [x] **Reestructuración del KM — CERRADA 2026-07-24, fue más lejos de lo planeado.** No solo se
      empaquetó como paquete Python instalable (`src/` layout, `pyproject.toml`, extras opcionales
      `[local-embeddings]`/`[ingesta]`/`[espacio]`/`[servidor]`/`[dev]`) — se separó a su **propio
      repo privado**, `github.com/sebasbizzi/km-knowledge-module`, sin historial previo (commit
      único, tag `v0.1.0`), para que el paquete no arrastre ninguna referencia a las instancias
      que lo consumen (barrido exhaustivo de referencias a CRIZA/DPN/etc. en código y docs). Local:
      `EMPRESAS-IA/knowledge_module/` sigue siendo el working directory, pero ahora es un repo
      anidado gitignorado por el padre (mismo patrón que `criza/`/`dpn-normativo/`), ya NO
      trackeado por el repo raíz de `EMPRESAS-IA`. Sumó capacidades nuevas al motor genérico:
      `detectar_clusters`, `detectar_huecos`/`validar_huecos` (extra `[espacio]`), coordenadas 3D
      persistidas + cola de jobs de refresco (`motor/proyeccion.py`), y un servidor HTTP opcional
      server-to-server (`server.py`, extra `[servidor]`) con auth de 2 niveles, rate limit y HTTPS
      exigido. Los 2 checks del auditor pendientes de portar ya viajaron dentro del split. Detalle
      completo y verificación real contra Neon: `knowledge_module/docs/KM_MOTOR_GENERICO_GATE.md`.
      **Pendiente, no de hoy:** conectar `criza/` para que instale el paquete desde el repo nuevo
      (`pip install`, todavía no se tocó nada de `criza/` en este trabajo) — es tarea de la
      conversación de CRIZA, no de la del KM.
- [ ] **Deuda de tests encontrada al independizar CRIZA (2026-08-13), deliberadamente NO resuelta
      hoy — sesión dedicada aparte.** Al verificar la instalación de `knowledge_module` por pip se
      corrió la suite completa por primera vez de punta a punta y aparecieron: `km_tools/tests`
      6/28 verde (22 fallos) + `utils/tests` que cuelga (probablemente llamadas reales a
      AGROVOC/INTA sin timeout) — causa exacta de cada fallo sin confirmar, podrían ser bugs
      reales, tests desactualizados, o dependencia del estado real del Neon (que cambia con el
      tiempo). Detalle completo: `docs/progress/2026-08-13.md` sección 4. **Criterio explícito de
      Sebas para avanzar:** no forzarlo al costado de otra tarea — mismo motivo por el que la
      auditoría de cumplimiento de abajo dice "no resolver nada de esto sin Sebas, ya se corrigió
      mal una vez por apurar la lectura". Se suma al mismo tipo de sesión dedicada que esa
      auditoría, no es un plan paralelo nuevo. **Primer paso recomendado de esa sesión:** correr
      `python -m knowledge_module.auditor --registry auditor_registry.yaml --root .` (ya
      reconectado hoy) para tener una foto estructurada y actual de gaps antes de entrar
      hallazgo por hallazgo. Esa corrida ya se hizo hoy (5 ALTO, 10 MEDIO, 46 BAJO, detalle en
      `docs/progress/2026-08-13.md` §5) — incluye un hallazgo MEDIO **nuevo, causado por la
      independización de hoy**: el auditor genérico (Capa 1) tiene hardcodeado que busca
      `docs/NEW_INSTANCE_PROTOCOL.md`/`docs/platform-boundary.md` relativos al `--root`,
      asumiendo un monorepo — ya no existen ahí desde que `criza/` es su propio repo. Mismo
      patrón que C25, visto del otro lado. Sin resolver — decisión de diseño del auditor.
- [x] **Fase D del plan de independización — repo GitHub propio + push, CERRADA 2026-08-14 (ya
      estaba hecha desde el 2026-08-13, solo faltaba verificar y documentar).** `sebasbizzi/criza`
      existe en GitHub, privado, remote `origin` configurado, local `master` y `origin/master` en
      el mismo commit (0 ahead/0 behind).
- [x] **Fase E del plan de independización — move físico de la carpeta, CERRADA 2026-08-14.**
      `C:\Users\sebab\Documents\Plataformas\criza` es ahora hermana de `EMPRESAS-IA\`, mismo
      patrón que `Conflur\`. Verificado: `EMPRESAS-IA\criza` ya no existe (no quedó duplicado ni
      carpeta vieja colgando).
- [x] **Fase F del plan de independización — reflejar la salida en `EMPRESAS-IA/CLAUDE.md`,
      CERRADA 2026-08-14.** Casi todo ya estaba hecho desde un commit del 2026-08-13
      (`3d058db`); hoy se cerró el bullet de "pendiente operativo" que seguía diciendo "falta el
      Move-Item" + se cortó la herencia stale de CRIZA en 4 secciones que instruían leer/escribir
      `criza/...` por path relativo roto (commits `139c170` + `a80303d` en `EMPRESAS-IA`, sin
      push todavía).
- [x] **Fase G del plan de independización — verificación post-move, CERRADA 2026-08-14.**
      5/5 puntos verificados reales (no mock): `pip install -e` a ruta correcta, `motor_api.
      buscar()` real contra Neon, auditor (61 hallazgos, idéntico a la foto del 2026-08-13, sin
      regresión), suite de tests por módulo (todo lo verde sigue verde, la deuda conocida de
      `km_tools`/`utils` sigue igual). **Plan de independización de CRIZA (Fases A-G) completo.**
      Detalle completo: `docs/progress/2026-08-14.md`.
- [ ] Rotar password Neon (acción manual de Sebas, no una tarea de desarrollo)
- [ ] Renombrar carpeta `EMPRESAS-IA/` (hoy `KRIZA/`) — pendiente migración de memoria de Claude
- [ ] **Auditoría objective-first "qué falta para que todo funcione"** — absorbida y ampliada por
      la auditoría de cumplimiento de plataforma 2026-07-05/06 (bullet siguiente). No generar un
      tercer plan paralelo.
- [ ] **Auditoría de cumplimiento de plataforma (2026-07-05/06, en revisión activa con Sebas)** —
      51 hallazgos totales, revisión hallazgo por hallazgo en curso. Temas 1-2 (git, docs
      desactualizados) y parte del Tema 3 (tenant hardcodeado) ya resueltos. **Hallazgo central
      nuevo: el KM comparte una sola base entre instancias, sin RLS, contradiciendo su propio
      diseño (P11) — decidido volver a base separada por instancia. **En ejecución desde
      2026-07-22, ver el bloqueador activo más arriba.** También:
      chunking nunca construido para CRIZA + truncado a 60k caracteres con pérdida de datos (P13),
      criterio de Capa 1 corregido ("Capa Estructural" = solo lo operativo, no lo genérico-parece).
      Detalle completo: `EMPRESAS-IA/docs/AUDITORIA_CUMPLIMIENTO_2026-07-05.md` (repo plataforma).
      Panel: `EMPRESAS-IA/plataforma/control_panel/`. **No resolver nada de esto sin Sebas —
      varios ítems ya fueron corregidos una vez por apurar la lectura.**

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
| Chunking corpus_cientifico | `knowledge_module/motor/chunking.py::chunk_texto()` (Capa 1, ~500 tokens/50 overlap, respeta párrafos, 8 unit tests) + `fuente_chunk`/`chunk_de` en `criza/config/plantillas/corpus_cientifico.yaml` (Capa 2, mismo patrón que `norma_chunk`/`chunk_de` de DPN) + `criza/ingest/chunk_corpus.py` (backfill + ingesta). Cierra hallazgo P13 (auditoría 2026-07-05): texto_completo ya no se trunca a 60k chars (cap removido de `download_pdfs.py` y `download_corpus_pdfs.py`) y es buscable por fragmento, no solo por título/abstract. **Completo: 1.414/1.414 fuentes con texto_completo, 34.857 fragmentos, 0 huérfanos.** En el camino: la DB Neon llegó a su límite de 512MB (resuelto con upgrade a plan Launch, ~$2-6/mes real medido) y `asyncio.gather` sin límite al crear conexiones `chunk_de` dejó 1.141 chunks temporalmente sin conexión (agotamiento del pool — fixeado con semáforo de 5, y reparados por matching de contenido normalizado). Se sacó también `texto_vectorizado` de `ficha` (Capa 1 — `migrations/006_drop_texto_vectorizado.sql`, aplicada a CRIZA y DPN): duplicaba `props` sin que nada lo leyera. Detalle completo en `criza/docs/architecture.md` [2026-07-06] y [2026-07-07], `criza/docs/progress/2026-07-06.md` y `2026-07-07.md`. | v1.1 | ✅ |
| FTS | `fts_vector` GENERATED STORED + GIN index; `search_fuentes_externas` (FTS sobre Documento); 8/8 tests `test_batch_store.py` | v0.1 | ✅ 2026-06-27 |
| MCP server | `server.py`: 6 tools — km_store_corrida, km_store_opportunity, km_store_learning, km_search, km_get_opportunity, km_update_opportunity, **km_search_fuentes_externas** | v0.2 | ✅ 2026-06-27 |
| Embeddings | BGE-m3 self-hosted en Modal, 1024 dims | prod | ✅ SEB-121 — swap completo, 44 filas migradas |
| Pre-flight genérico | `knowledge_module/preflight.py`: `FuenteCheck`/`run_preflight()` — patrón objective-first (bloqueante/advertencia) generalizado de investigacion_amplia a los 4 agentes. Ver `docs/orchestration-layer.md` Decisión 6. | v1.0 | ✅ 2026-07-02 — **6/6 unit tests** |
| Tests | 7 unit (tools) + 5 unit (ingest) + 2 integration | — | ✅ 14/14 |

---

## Dónde están las cosas

CRIZA es su propio repo (`Plataformas/criza/`), independiente de `EMPRESAS-IA/` (plataforma,
repo separado) y de `knowledge_module` (instalado por pip, no es carpeta hermana — ver
`pip install -e` en la sección de abajo).

```
criza/                          ← este repo: CRIZA-biotech (Capa 2)
    ├── agents.md                ← este archivo
    ├── .env                     ← DATABASE_URL, EMBEDDING_*, ANTHROPIC_API_KEY (propio, no versionado)
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
    ├── scientific_agent/        ← fusionado el 2026-08-14 (era repo separado, historial preservado)
    │   ├── ROADMAP.md           ← estado del agente científico (fuente de verdad)
    │   ├── specialist_proteins.py · run.py
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

knowledge_module (Capa 1 — memoria semántica compartida): repo propio, `github.com/sebasbizzi/
km-knowledge-module`, instalado por pip en modo editable. Comando exacto verificado post-move
(2026-08-14, `criza/` y `knowledge_module/` ya no son carpetas hermanas):
`pip install -e "C:\Users\sebab\Documents\Plataformas\EMPRESAS-IA\knowledge_module"`. Detalle de
su estructura interna: `knowledge_module/docs/KM_DESIGN_GATE.md` en ese repo, no acá.
```

> Nota: el árbol de arriba (dentro de `criza/`) quedó desactualizado en algunos puntos antes de
> esta migración (menciona `divergent_agent/`, `convergent_agent/` — ya borrados, ver sección
> "Borrado" abajo) — no se resincronizó entero en este cambio, solo se corrigió que `criza/` deje
> de mostrarse como subcarpeta de `EMPRESAS-IA/`.

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
