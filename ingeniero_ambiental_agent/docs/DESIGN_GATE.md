# Design Gate — Especialista Ingeniero Ambiental

**Versión:** 1.0
**Fecha:** 2026-08-16
**Módulo:** `criza/ingeniero_ambiental_agent/`
**Capa:** 2 (instancia CRIZA)
**Estado:** ✅ LISTO

---

## 1. Identidad

| Pregunta | Respuesta |
|---|---|
| ¿Qué es? | Segundo especialista de la "biblioteca de especialistas" (`docs/PROPUESTA_DESTINO.md` §5) — evalúa factibilidad de **ingeniería** de un enfoque técnico ya identificado: balances de masa/energía, dimensionamiento preliminar, integración con la planta existente, limitaciones operativas/logísticas. Distinto del Microbiólogo (que evalúa madurez biológica/química) — este especialista responde "¿se puede construir y operar de verdad?", no "¿es biológicamente viable?". |
| ¿Qué problema resuelve en una oración? | El gap real que el Microbiólogo ya identificó en una corrida real contra Helios: "se necesita calcular el costo energético... balance energético/térmico de la planta" — no un gap inventado, un gap que un especialista real ya señaló. |
| ¿Quién lo usa? | Sebas, directo o vía el Conductor (`correr_especialista`, generalizado en esta etapa — ver Design Gate del Conductor). |
| ¿De qué depende? | `utils/ai_client.py`, `utils/corpus.py`, `km_tools/search.py`, `utils/openalex.py`, `utils/agrovoc.py`, `utils/casos.py`, `knowledge_module.preflight`, `knowledge_module.aprendizaje`. |
| ¿Qué depende de él? | El Conductor (`correr_especialista`) puede invocarlo — primer consumidor real de la generalización de esa tool. |
| ¿Milestone? | Etapa 7 del plan de construcción del nuevo sistema de agentes (`docs/progress/2026-08-16.md`). |

---

## 2. Trazabilidad diseño → implementación

### Por qué este especialista, ahora, y no otro/antes

No es una elección abstracta de "cuál de los 3 candidatos de §5 sigue" — es la respuesta directa
a lo que el Microbiólogo **ya recomendó en una corrida real** contra el 'Frente técnico' de
Helios (Etapa 4, verificación real): *"Se requiere evaluación de: (1) diseño de biorreactor
gas-líquido... (2) balance de masa y energía de las rutas de concentración: se necesita calcular
el costo energético..."* — exactamente el dominio de un ingeniero ambiental/de procesos, no
inventado en abstracto.

### Clonado de `microbiologo_agent.py`, con una simplificación real (no solo copiar)

Mismo template probado (SEB-115, `_run_loop` compartido, preflight, `utils/casos.py`) — pero con
una diferencia deliberada: **solo soporta `frente_id` (modelo `casos.yaml`), no `oportunidad_id`**.
`microbiologo_agent.py` soporta los dos porque se construyó en la Etapa 1 (antes de que
`casos.yaml` existiera como camino real) y se extendió en la Etapa 4 — este especialista se
construye directamente en la Etapa 7, cuando `frente_id` ya es el único modelo que un caso real
usa. Agregar el camino `oportunidad_id` acá sería diseñar para un caller que no existe — ningún
flow YAML lo invocaría, y el principio de esta sesión ("no diseñar sin necesidad real") aplica
tanto para sumar como para omitir.

### Entidades

| Entidad | Descripción | Estado |
|---|---|---|
| `search_literature` | OpenAlex vía `utils/openalex.py` (compartido). | ✅ construido |
| `buscar_corpus_cientifico` | Búsqueda semántica CONICET+INTA (compartido). | ✅ construido |
| `search_corpus_inta` | FTS exhaustivo INTA (compartido). | ✅ construido |
| `expand_agrovoc` | Expansión AGROVOC (compartido). | ✅ construido |
| `submit_evaluacion_tecnica` | Mismo schema exacto que `microbiologo_agent` (Design Gate de ese agente, decisión E: "mismo schema se reusa para el ingeniero ambiental, así el futuro Armador/Conductor pueden leer especialistas distintos con el mismo shape") — no se creó un schema nuevo. | ✅ construido |

**Sin tools de dominio específicas** (ej. simuladores de proceso, bases de datos de equipos) —
mismo criterio que el Microbiólogo en su v1: solo se suman si una corrida real muestra que hacen
falta, no antes.

### Contrato SEB-115

```python
INPUT_CONTRACT  = {"agent": "ingeniero_ambiental", "version": "1.0",
                   "fields": {caso, tarea, contexto, conocimiento: {"frente_id": str}, herramientas}}
OUTPUT_CONTRACT = {"agent": "ingeniero_ambiental", "version": "1.0",
                   "km_escribe": ["documento_caso conectado vía frente_produce_documento"],
                   "fields": {análisis, nivel_confianza, recomendaciones, próximo_agente, nuevo_conocimiento}}
```

`conocimiento` acepta **solo** `frente_id` (no `oportunidad_id`) — a diferencia del Microbiólogo,
por la razón de arriba.

### KM write

| Tipo de output | Qué contiene | Key en KM | Cómo | Estado |
|---|---|---|---|---|
| **Resultado estructurado + informe** | Mismo shape que Microbiólogo (`evaluacion_tecnica` reusa el nombre del campo por consistencia de schema, aunque el contenido es de ingeniería, no de biología) | `documento_caso` conectado vía `frente_produce_documento` | La costura (`invocador.py::invocar_agente`), no el agente | ✅ construido |
| **Token usage** | Tokens consumidos | `props.token_usage.ingeniero_ambiental` del **frente** | El agente sí escribe esto — mismo patrón que Microbiólogo | ✅ construido |
| **Aprendizaje** | Lecciones del caso | área `lecciones` | 🔵 pendiente | misma deuda intencional que Microbiólogo — no se cierra acá |

---

## 3. Checklist del playbook

### Estructura de archivos

- [x] `ingeniero_ambiental_agent.py` — SYSTEM_PROMPT + TOOLS + `run_agent_desde_frente()` + `run()`
- [x] `run.py` — runner
- [x] `docs/DESIGN_GATE.md` — este archivo
- [x] `.env.example`
- [x] `tests/`

### Testing

- [x] Test: `TOOLS` tiene exactamente 5 tools (4 de corpus + `submit_evaluacion_tecnica`)
- [x] **Test explícito del checklist anti-sesgo: `SYSTEM_PROMPT` no contiene ninguna de las
      strings "Helios", "biogás", "biodigestor", "Mateo", "Andrés"** — mismo control que el
      Microbiólogo, contra el mismo sesgo de `specialist_proteins.py`.
- [x] Test: `run()` requiere `frente_id`, no acepta `oportunidad_id` (a propósito, ver decisión A)
- [x] Test: `run_agent_desde_frente` mock captura `submit_evaluacion_tecnica`
- [x] Al menos 1 integration test real contra un frente real (staging, no producción)

---

## 4. Scope explícito por versión

| Feature | Versión | Razón |
|---|---|---|
| Camino `oportunidad_id` (modelo viejo) | No planeado | Ningún caller real lo necesitaría — ver decisión A. |
| Tools de dominio específicas (simuladores de proceso, bases de equipos) | v2, si hace falta | No se identificó ninguna necesidad concreta todavía. |
| Persistencia de lecciones de caso | backlog | Misma deuda intencional que Microbiólogo. |

---

## 5. Decisiones requeridas antes de arrancar

| # | Pregunta | Opciones | Decisión tomada | Fecha |
|---|---|---|---|---|
| A | ¿Soporta `oportunidad_id` además de `frente_id`, como el Microbiólogo? | Sí, por consistencia de template / No, solo `frente_id` | **Solo `frente_id`.** Ningún flow YAML ni caller real invocaría este especialista contra el modelo viejo — el Microbiólogo lo soporta por herencia histórica (se construyó antes de `casos.yaml`), no porque haga falta hoy. Sumarlo acá sería diseñar para un caller hipotético, contra el criterio de toda la sesión. | 2026-08-16 |
| B | ¿Qué especialidad exacta, de los 3 candidatos de `PROPUESTA_DESTINO.md` §5? | Ingeniero ambiental / Agrónomo | **Ingeniero ambiental** — es literalmente lo que el Microbiólogo ya recomendó en una corrida real contra Helios (balance de masa/energía, biorreactor), no una elección en abstracto. Agrónomo queda para si aparece un caso real que lo pida (mismo criterio, `PROPUESTA_DESTINO.md` §11: "no diseñar el patrón en abstracto hasta que aparezca uno"). | 2026-08-16 |
| C | ¿Tool set? | Solo las 4 genéricas / sumar algo de dominio (ingeniería de procesos) | **Solo las 4 genéricas** — mismo criterio que el Microbiólogo en v1: nada de dominio-específico hasta que una corrida real muestre el hueco. | 2026-08-16 |
| D | ¿Schema de `submit_evaluacion_tecnica`? | Nuevo, específico de ingeniería / Reusar el del Microbiólogo | **Reusar tal cual** — decisión E del Design Gate del Microbiólogo ya lo anticipó explícitamente ("mismo schema se reusa para el ingeniero ambiental"). | 2026-08-16 |
| E | Etapa 10 (2026-08-16) — mismo pedido de Sebas que recibió el Microbiólogo: chat directo, no solo vía el Conductor. | Mismo patrón que `microbiologo_agent.py` (decisión H de ese gate) / uno propio | **Mismo patrón, sin variación.** `_despachar_tool` extraído de `_run_loop`, `TOOLS_CHAT = TOOLS - {submit_evaluacion_tecnica}`, `iniciar_sesion(frente_id)` + `enviar_mensaje(messages, texto, frente_id)`. No hay tools de dominio propias acá (decisión C) así que el dispatch extraído es más chico que el del Microbiólogo, pero la forma es idéntica — mismo razonamiento: la evaluación formal persistida sigue siendo exclusiva de la corrida de un turno vía la costura. | 2026-08-16 |

---

## 6. Estado del gate

**Estado actual:** ✅ LISTO

Decisiones A-E cerradas, ninguna abierta. Segundo consumidor del patrón validado en la Etapa 1 y
probado en uso real durante las Etapas 4-6 — no hay diseño nuevo de fondo.

**Deuda intencional documentada:**
- Camino `oportunidad_id` → no planeado, ver decisión A
- Persistencia de lecciones de caso → backlog, misma deuda que Microbiólogo
- Tools de dominio específicas → solo si una corrida real las requiere
- El chat (decisión E) no escribe lecciones al cierre (a diferencia del Conductor, Etapa 9) —
  mismo backlog que "persistencia de lecciones de caso"
