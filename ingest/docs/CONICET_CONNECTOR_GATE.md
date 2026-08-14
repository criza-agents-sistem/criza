# Design Gate — Conector de ingesta CONICET (OAI-PMH) + área Corpus

> **Nota 2026-08-14:** movido de `knowledge_module/docs/` a `criza/ingest/docs/` junto con el
> código (`oai_pmh.py` → `criza/utils/oai_pmh.py`, `ingest_corpus.py` →
> `criza/ingest/harvest_conicet.py`). El harvester dejó de ser Capa 1 (`knowledge_module/`) — su
> único consumidor real siempre fue CRIZA, así que baja a Capa 2 junto con él. El resto de este
> documento queda como estaba al diseñarse (2026-06-14, cuando sí vivía en el paquete
> compartido) — la sección "Capa: 1" de abajo es historia, no el estado actual.

**Versión:** 1.0
**Fecha:** 2026-06-14
**Módulo:** harvester OAI-PMH (`criza/utils/oai_pmh.py`, `criza/ingest/harvest_conicet.py`) + config CONICET + área/plantilla `corpus_cientifico`
**Capa:** 2 (específico de CRIZA, desde 2026-08-14 — antes vivía como Capa 1 en `knowledge_module/`, ver nota arriba)
**Estado:** 🟡 LISTO CON DEUDA — decisiones cerradas (2026-06-14); deuda intencional documentada en §4. Desarrollo puede arrancar.

> **Regla de uso:** se crea ANTES de codear. Desarrollo arranca con estado 🟡 o ✅.
> Trazabilidad: el architecture.md de la instancia [2026-06-14] + épico SEB-143 / issue SEB-150.
> Sustrato: `knowledge_module/docs/KM_MOTOR_GENERICO_GATE.md` (el motor donde aterriza).

---

## 1. Identidad

| Pregunta | Respuesta |
|---|---|
| ¿Qué es? | Un cosechador OAI-PMH **genérico** (Capa 1) que trae metadata de repositorios académicos y la ingesta como fichas `fuente` en una **área de corpus** del motor del KM. CONICET Digital es su primera instancia configurada (Capa 2). |
| ¿Qué problema resuelve? | El sistema no tiene **fuentes locales** verificables en el KM. Es el origen del rethink: sin literatura local (CONICET/INTA), el expediente se apoya en fuentes extranjeras/viejas y no genera confianza de inversión. |
| ¿Quién lo usa? | Los **agentes investigadores** (Evidencia Científica SEB-149, Investigación Amplia SEB-146, Mercado SEB-148) — leen el corpus por búsqueda semántica (`vecinos`/`buscar`) al poblar los cruces del expediente. |
| ¿De qué depende? | Motor genérico del KM (`motor/api.py` `guardar_ficha`, embeddings BGE-m3 en Modal), Neon. Endpoint `ri.conicet.gov.ar/oai/request` (verificado en vivo, SEB-150). |
| ¿Qué depende de él? | La calidad/localidad de los cruces 1 y 2 del expediente. Otros conectores de otras fuentes e instancias reusan el mismo harvester genérico. |
| ¿Milestone más próximo? | M1 — primer expediente con evidencia local real. Primer eslabón de la secuencia CONICET → Mercado → Armador. |

---

## 2. Trazabilidad diseño → implementación

### Entidades / componentes

| Entidad | Doc de diseño | En código (archivo) | Capa | Scope v0.1 | Estado |
|---|---|---|---|---|---|
| **Harvester OAI-PMH genérico** | architecture.md [2026-06-14] | `knowledge_module/connectors/oai_pmh.py` | 1 | ✅ incluido | 🔜 construir |
| **Cosecha incremental** (`from`/`until`, resumption tokens, último datestamp) | architecture.md [2026-06-14] | `connectors/oai_pmh.py` (estado de cosecha) | 1 | ✅ incluido | 🔜 construir |
| **Mapeo OAI_DC → ficha `fuente`** | §5.B | `connectors/oai_pmh.py` (parser DC) | 1 | ✅ incluido | 🔜 construir |
| **Config de conector CONICET** (endpoint, sets, filtros agro/ganadería/biotech) | §5.C | config de instancia (YAML/py, en el repo de esa instancia) | 2 | ✅ incluido | 🔜 construir |
| **Filtro de pertinencia** (agro/ganadería/biotech sobre metadata DC) | §5.C | parte de la config CONICET | 2 | ✅ incluido | 🔜 construir |
| **Área/plantilla `corpus_cientifico`** | KM_MOTOR_GENERICO_GATE §5.B | `knowledge_module/plantillas/corpus_cientifico.yaml` | 1 | ✅ incluido | 🔜 construir |
| **tipo_ficha `fuente`** (campos abajo; vectoriza título+abstract; dedup por identifier) | §5.B | en `corpus_cientifico.yaml` | 1 | ✅ incluido | 🔜 construir |
| **Ingesta corpus** (harvest → `guardar_ficha`) | architecture.md [2026-06-14] | `knowledge_module/ingesta/ingest_corpus.py` | 1 | ✅ incluido | 🔜 construir |
| **Fetch de full-text** | §4 | — | 1 | 🔵 v0.2 | 🔵 postergado |
| **Conexión `fuente` ↔ `problema`/`solucion`** | §5.D | — | — | 🔵 a futuro (la hacen los investigadores) | 🔵 postergado con decisión |

**Campos del tipo_ficha `fuente` (v0.1):** `titulo` · `abstract` · `autores` · `anio` · `identifier`
(OAI identifier / DOI / handle) · `url` · `repositorio` (CONICET/INTA/…) · `idioma` · `tipo_recurso`
(article/thesis/report) · `sets` (raw OAI). **Vectoriza:** `titulo` + `abstract`. **Deduplica por:** `identifier`.

### Contratos / interfaces

| Contrato | Entre quiénes | Doc | En código | Estado |
|---|---|---|---|---|
| `guardar_ficha(area='corpus_cientifico', tipo='fuente', tenant_id, campos)` | harvester → motor | KM_MOTOR_GENERICO_GATE §E | `motor/api.py` (ya existe) | ✅ reusar |
| Mapeo OAI Dublin Core → campos `fuente` | OAI-PMH → ingesta | §5.B | `connectors/oai_pmh.py` | 🔜 definir |
| Lectura del corpus por investigadores | motor → agentes | `vecinos`/`buscar` (ya existen) | `motor/api.py` | ✅ reusar (a futuro) |

---

## 3. Checklist del playbook

### Seguridad Nivel 1
- [ ] OAI-PMH es público sin key → no hay credencial de fuente. Credencial de Neon en `.env`, nunca en código.
- [ ] `.env` en `.gitignore`; `.env.example` completo (hereda de `knowledge_module/`).
- [ ] Sin credenciales en historial de git.

### Seguridad Nivel 3
¿Aplica? [ ] Sí / [x] **No** — el corpus son papers **públicos** (metadata académica abierta), no datos
sensibles de terceros. Igual: `tenant_id` ya es obligatorio en el motor (las fichas `fuente` llevan
un tenant_id fijo por instancia), así que el aislamiento por instancia se respeta por diseño.

### Estructura de archivos
- [ ] Harvester en `knowledge_module/connectors/`; ingesta en `knowledge_module/ingesta/`.
- [ ] Plantilla en `knowledge_module/plantillas/corpus_cientifico.yaml`.
- [ ] `docs/CONICET_CONNECTOR_GATE.md` ← este archivo ✅.
- [ ] `.env.example` actualizado si suma variables (endpoint configurable).

### Testing
- [ ] **Unit:** parser OAI_DC → ficha `fuente` (con fixture de respuesta XML real); filtro de pertinencia (incluye/excluye); cosecha incremental (cálculo de `from`).
- [ ] **Integration:** harvest real acotado (un set chico o `until` corto) → fichas en Neon; re-harvest no duplica (idempotencia por identifier).
- [ ] Markers `unit`/`integration` (convención del repo).

### Observabilidad
¿Va a producción / multiusuario? Sí (los investigadores leen el corpus).
- [ ] Log de cada cosecha: cosechados / filtrados-fuera / ingeridos / deduplicados, + datestamp final.
- [ ] Log de errores (timeouts OAI, resumption token vencido) con stack trace.

### Backups y resiliencia
- [ ] DB = Neon (heredado del KM, mismo plan). El corpus se puede **re-cosechar** desde CONICET (la fuente es la verdad) → pérdida recuperable por diseño.
- [ ] Si CONICET cae durante la cosecha: la cosecha es incremental y reanudable (último datestamp guardado) → reintentar sin perder lo ya ingerido.

---

## 4. Scope explícito por versión

| Entidad / feature | Versión | Razón del postergue | Bloqueante |
|---|---|---|---|
| ~~Fetch de **full-text** (PDF/texto completo)~~ | ✅ **v0.2 — cerrado 2026-07-02** | Se determinó en auditoría de sesgos que "el full-text se trae cuando un agente profundiza" reproducía el mismo sesgo de muestreo ya corregido en la búsqueda del corpus — dejaba a discreción del agente qué leer. Cerrado con `knowledge_module/ingesta/download_corpus_pdfs.py`: bulk, no bajo demanda, mismo criterio que INTA. Ver `orchestration-layer.md` Decisión 6. | — |
| Conexión `fuente` ↔ `problema`/`solucion` | a futuro | El corpus arranca como **pool consultable**, no pre-conectado. Los investigadores conectan evidencia a oportunidades cuando llenan cruces. | No |
| Conector **INTA** (SEB-151) | cuando se destrabe acceso | Host INTA caído; depende de Andrés + vía SNRD. Reusa este mismo harvester. | No (bloqueado aparte) |
| Navegación visual 3D del espacio | Etapa 2 del KM | Diferencial, sin tokens; la etapa 1 ya guarda los embeddings para construirlo sin rehacer. | No |

---

## 5. Decisiones requeridas antes de arrancar

| # | Pregunta | Decisión tomada | Fecha |
|---|---|---|---|
| A | ¿Dónde aterrizan los papers en el KM? | ✅ **Opción A** — área/plantilla propia `corpus_cientifico` en el motor genérico (espacio separado del de descubrimiento). Descartadas `documento` legacy (se retira) y store aparte (segundo sustrato). | 2026-06-14 |
| B | ¿Qué se guarda y cómo se identifica/deduplica cada `fuente`? | ✅ metadata Dublin Core + abstract; vectoriza título+abstract; **dedup por `identifier`** (OAI/DOI/handle). Full-text → v0.2. | 2026-06-14 |
| C | ¿Cómo se filtra la pertinencia (agro/ganadería/biotech)? | ✅ **Medir primero los sets OAI de CONICET**; si hay set temático aprovechable, cosechar por set; si no, **filtrar por keywords sobre los campos DC** (título/abstract/subject). Default operativo: keywords. Es config Capa 2, ajustable sin tocar el harvester. | 2026-06-14 |
| D | ¿El corpus se pre-conecta a problema/solución? | ✅ **No.** Pool consultable por búsqueda semántica; las conexiones las hacen los investigadores a futuro. | 2026-06-14 |
| E | ¿Capa del harvester vs la config? | ✅ Harvester OAI-PMH **genérico = Capa 1** (`knowledge_module/`); endpoint + sets + filtros de un conector concreto = **Capa 2** (config de instancia). El harvester es reusable por cualquier fuente e instancia. | 2026-06-14 |
| F | ¿"No se pudo descargar el PDF" es un solo estado o hay que distinguir? | ✅ **Tres estados, no dos.** Verificado a mano contra 3 casos reales: "sin material" y "material existe pero hay que pedirlo" NO son lo mismo — tratarlos igual sería la misma discreción/sesgo que se corrigió en otros lados. `find_pdf_access()` distingue: descargable directo / `requiere_solicitud` (con `solicitud_url` si DSpace ofrece autoservicio tipo "Consultar", sin ella si es un bitstream `isAllowed=n` sin camino de autoservicio visible) / nada. Se declara siempre, nunca se archiva en silencio como "no disponible". No se automatiza la solicitud (mandatorio bloquearía el pipeline esperando un ida y vuelta que puede tardar días) — queda como gap visible para que el humano decida caso por caso si vale la pena pedirlo (ej. vía contactos en CONICET). | 2026-07-02 |

Sin decisiones abiertas que bloqueen. La única incógnita (sets temáticos de CONICET, decisión C) tiene
default operativo y se resuelve **midiendo en la primera cosecha**, no bloquea el diseño.

---

## 6. Estado del gate

| Estado | Condición |
|---|---|
| 🔴 BLOQUEADO | Hay decisiones abiertas en §5 o GAPs en §2 |
| 🟡 LISTO CON DEUDA | Decisiones cerradas; hay items 🔵 documentados como deuda intencional |
| ✅ LISTO | Todo resuelto |

**Estado actual:** ✅ **LISTO** — decisiones A–E cerradas (2026-06-14); full-text fetch cerrado 2026-07-02.

**Deuda intencional (no bloquea):**
- 🔵 Conexión `fuente`↔`problema`/`solucion` → la hacen los investigadores a futuro.
- 🔵 Vigilar escala del índice HNSW (miles de fichas; trigger T5 del motor) — empezar y medir.

---

*Actualizar antes de cada sesión que agregue entidades. Si surge una entidad nueva, agregarla a §2 ANTES de codearla.*
