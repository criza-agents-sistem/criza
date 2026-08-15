# agents.md — CRIZA-biotech

> Contexto activo para Claude. Máximo ~200 líneas.
> Detalle técnico profundo → `ROADMAP.md` de cada componente.
> Arquitectura de plataforma → `KRIZA_Foundation_Document.md` en el repo `EMPRESAS-IA/docs/`
> (plataforma, repo separado — no hay path relativo válido entre `criza/` y `EMPRESAS-IA/` desde
> que CRIZA es su propio repo)

---

## Qué es CRIZA

Primera empresa agéntica de la plataforma EMPRESAS-IA (Capa 2). Sistema de transferencia de tecnología
ciencia-industria, foco biotech agro argentino. **Diseño vigente:** múltiples puertas de entrada →
Orquestador (motor dirigido por objetivo) → agentes investigadores → Armador → **expediente de decisión** →
el humano decide. El pipeline viejo Scout→Especialista→Mercado quedó superado (rethink cerrado a nivel
diseño 2026-06-13, `docs/architecture.md` decisiones D1–D10). **Redefinición en curso desde 2026-08-14**
de qué es CRIZA de acá en más — ver "Estado operativo" abajo y `docs/PROPUESTA_DESTINO.md`.

---

## Agentes activos

> Generado por `python scripts/generar_agents_md.py` — no editar a mano entre los marcadores.
> Fuente: `orquestador/agents_registry.yaml` + suite de tests real + última decisión vigente en
> `decisiones_sistema` (KM) para ese componente.

<!-- GENERADO:AGENTES_ACTIVOS:INICIO -->
| Agente | Módulo | Tests | Registrado | Última decisión |
|---|---|---|---|---|
| Mercado | `market_agent/` | 67/67 ✅ (+6 integration) | ✅ activo, DESIGN_GATE.md ✅ | — |
| Evidence Generalista | `evidence_generalista/` | 48/48 ✅ (+1 integration) | ✅ activo, DESIGN_GATE.md ✅ | — |
| Investigación Amplia | `investigacion_amplia/` | 39/39 ✅ (+1 integration) | ✅ activo, DESIGN_GATE.md ✅ | — |
| Armador | `armador/` | 31/31 ✅ (+1 integration) | ✅ activo, DESIGN_GATE.md ✅ | — |
| Especialista Proteínas | `scientific_agent/` | sin tests unit (todos integration/deselected) | 🟡 registrado, inactivo, sin DESIGN_GATE.md | — |
<!-- GENERADO:AGENTES_ACTIVOS:FIN -->

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
pendientes, no tareas ejecutables) — generado desde `decisiones_sistema` (KM), todas con
`estado=vigente`. Una decisión resuelta o superada deja de aparecer acá — el historial completo
sigue en el KM (`scripts/km_decisiones.listar_decisiones_vigentes` solo trae las vigentes) y en
`docs/progress/*.md`. Fases D-G del plan de independización (2026-08-14) y la reestructuración
del KM (2026-07-24) ya cerraron y por eso no se migraron acá — su detalle completo sigue en
`docs/progress/2026-08-14.md` y `knowledge_module/docs/KM_MOTOR_GENERICO_GATE.md`.

<!-- GENERADO:ESTADO_OPERATIVO:INICIO -->
- [ ] **Diseño concreto de la app: modelo de datos de caso + páginas (sin scaffold Next.js todavía)** (2026-08-15, Sebas + Claude). Área KM `casos` (config/plantillas/casos.yaml): tipo_ficha caso (nombre, descripcion, estadio, participantes embebidos), frente, pendiente, artefacto_externo, documento_caso (modo chat/documento — bisagra del §7.3), dato_extraido (contacto/cifra/plazo). 5 conexiones tipadas dentro del área. Páginas propuestas: / (lista de casos), /casos/[id] (frentes/pendientes/artefactos), /casos/[id]/frente/[id] (chat o documento), /casos/nuevo. Cargados los 2 casos reales (Biogás/Helios, MicroBigs) con datos sacados de casos/*.md — no inventados. **Motivo:** PROPUESTA_DESTINO.md §7: 7 ideas ya confirmadas por Sebas a partir de releer los 2 casos reales. El scaffold de Next.js en sí queda para una sesión propia con su Design Gate — esto es la parte de "diseño concreto" verificable hoy sin escribir frontend. **Alternativas consideradas:** Conexión tipada participa_en (usuario -> caso) — descartada otra vez por la misma restricción del loader (ver docs/MEJORAS_KM.md #1): se resuelve con participantes embebido en caso.props.; Construir también el scaffold de Next.js hoy — descartado: módulo nuevo, necesita su propio Design Gate por CLAUDE.md, alcance mucho mayor que una sesión.
- [ ] **Modelo de datos de usuarios/roles (sin auth real todavia)** (2026-08-15, Sebas + Claude). Area KM nueva usuarios (config/plantillas/usuarios.yaml): tipo_ficha usuario (nombre, email, rol_global, estado activo/invitado/inactivo, notas) + tipo_ficha rol (catalogo abierto: admin, colaborador, referente, observador). Sembrado real: Sebas (admin, activo), Pablo y Andres (referente, invitado, sin email — dueños de MicroBigs y Biogas respectivamente, sin acceso directo hoy). **Motivo:** PROPUESTA_DESTINO.md §9: dejar preparado sumar a Pablo/Andres mas adelante sin rediseñar, sin implementar login real todavia (uso actual: solo Sebas). **Alternativas consideradas:** Conexion tipada participa_en (usuario -> caso) en el mismo paso — descartada: el loader del motor exige que ambos extremos de una tipo_conexion se declaren en la misma plantilla, y hoy no existe todavia un nodo real de "caso" (el unico nodo real, oportunidad/descubrimiento, es flaco y de otra area). Se agrega cuando el item 3 (diseño de la app + modelo de datos de caso) defina esa ficha.; Tabla Postgres dedicada en vez de ficha JSONB del motor generico — descartada por ahora: no hay auth real todavia, no hace falta la integridad relacional estricta que pediria eso (unique email, FKs) hasta que se implemente login de verdad.
- [ ] **Registry data-driven + la costura de persistencia al KM** (2026-08-15, Sebas + Claude). orquestador/agents_registry.yaml (nuevo) reemplaza los imports hardcodeados de registry.py. orquestador/invocador.py (nuevo, 'la costura') persiste el resultado de cualquier agente al KM de forma genérica, sin que el agente tenga que acordarse. Los 4 agentes actuales se normalizaron a este contrato. Cerró dos gaps reales: Armador nunca había persistido su propio expediente, e Investigación Amplia duplicaba su informe en dos props. **Motivo:** Persistir el resultado dependía de que cada agente se acordara — causa exacta del bug real del 22/07 (Mercado corrió, costó plata, y su escritura era invisible para el Motor). Sin garantía estructural, cualquier especialista nuevo podía repetir el mismo error. **Alternativas consideradas:** Seguir con imports hardcodeados y persistencia por agente; Solo agregar tests que detecten el bug de nuevo, sin cambiar la arquitectura
- [ ] **Redefinición del objetivo de CRIZA: de blue-ocean-discovery a equipo asesor** (2026-08-14, Sebas). CRIZA deja de tener como propósito central 'encontrar blue oceans' — pasa a ser un equipo de agentes de IA asesores, con blue-ocean-discovery como capacidad invocable cuando el caso la amerita. Ver docs/PROPUESTA_DESTINO.md — borrador todavía sin cerrar, no reemplaza el Norte global de CLAUDE.md hasta que cierre. **Motivo:** El objetivo original ya cumplió su función — de ahí salieron proyectos reales (biogás vía Andrés, MicroBigs vía Pablo) que ahora necesitan acompañamiento continuo, no un expediente de inversión único. **Alternativas consideradas:** Mantener el objetivo original y tratar estos casos como excepción; Redefinir el propósito central del sistema
- [ ] **Rotar password de Neon** (2026-08-13, Sebas). Acción manual pendiente de Sebas — no es una tarea de desarrollo. **Motivo:** Buena práctica de seguridad tras la independización del repo. **Alternativas consideradas:** —
- [ ] **Deuda de tests encontrada al independizar CRIZA — sesión dedicada aparte** (2026-08-13, Sebas). km_tools/tests 6/28 verde (22 fallos) + utils/tests cuelga. Causa exacta sin confirmar (podrían ser bugs reales, tests desactualizados, o dependencia del estado real del Neon). Detalle: docs/progress/2026-08-13.md §4. **Motivo:** No forzarlo al costado de otra tarea — mismo criterio que la auditoría de cumplimiento: ya se corrigió mal una vez por apurar la lectura. **Alternativas consideradas:** Arreglarlo ahora, al costado de otra tarea; Sesión dedicada aparte
- [ ] **Auditor determinístico — 9 checks contra datos reales del KM y código fuente** (2026-07-22, Sebas + Claude). knowledge_module/auditor/ (Capa 1) + criza/auditor_registry.yaml (Capa 2, config). Verifica población de campos, cobertura de fuentes entre agentes hermanos, sampling no declarado, decisiones diferidas, contrato fuentes_y_cobertura, km_write_ausente, instancias no registradas, contrato_input_no_leido, km_conexion. 32/32 unit tests. **Motivo:** Verificación determinística, no LLM, contra el código y el KM reales — para no depender de que un humano se acuerde de revisar cada conexión a mano. **Alternativas consideradas:** Revisión manual periódica; Verificador determinístico
- [ ] **objetivo del Motor sigue decorativo — depende del diseño del Conductor** (2026-07-22, Sebas + Claude). El campo `objetivo` que arma el Motor al crear una oportunidad se guarda como texto pero no influye en ninguna decisión de ruteo — todo el ruteo real está pre-declarado en el YAML del flow. No se resuelve todavía. **Motivo:** Es la pregunta de fondo del diseño del Conductor (PROPUESTA_CONDUCTOR.md) — resolverla aislada, sin el Conductor definido, sería adivinar la forma final. **Alternativas consideradas:** Resolverlo ahora de forma aislada; Esperar a diseñar el Conductor completo
- [ ] **Auditoría de cumplimiento de plataforma — 51 hallazgos, revisión activa** (2026-07-05, Sebas). Revisión hallazgo por hallazgo en curso con Sebas. Temas 1-2 (git, docs desactualizados) y parte del Tema 3 (tenant hardcodeado) ya resueltos. Hallazgo central: el KM comparte una sola base entre instancias sin RLS (P11) — decidido volver a base separada por instancia. Detalle: EMPRESAS-IA/docs/AUDITORIA_CUMPLIMIENTO_2026-07-05.md. **Motivo:** No resolver nada de esto sin Sebas — varios ítems ya se corrigieron mal una vez por apurar la lectura. **Alternativas consideradas:** Resolver todo de una vez; Revisión hallazgo por hallazgo con Sebas
- [ ] **Renombrar carpeta EMPRESAS-IA/ (hoy KRIZA/ en disco)** (2026-07-01, Sebas). Pendiente — requiere migración de memoria de Claude antes de renombrar. **Motivo:** El nombre de carpeta quedó desactualizado tras sucesivos cambios de naming de la plataforma. **Alternativas consideradas:** —
<!-- GENERADO:ESTADO_OPERATIVO:FIN -->

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
- [ ] **Si la tarea generó una decisión de arquitectura/desarrollo de CRIZA → registrada en
      `decisiones_sistema` (KM) vía `scripts/km_decisiones.registrar_decision(...)` y
      `python scripts/generar_agents_md.py` corrido para que "Agentes activos" y "Estado
      operativo" la reflejen. Obligatorio, no discrecional — mismo criterio que
      `architecture.md` ("registrar en el momento de la decisión", no "después"). Esas dos
      secciones **no se editan a mano** (decisión 2026-08-15, ver `docs/progress/2026-08-15.md`
      — la edición manual fue la causa de que se desactualizaran). Si terminaste la sesión y no
      corriste el generador tras una decisión nueva, la sesión no está cerrada.**
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
