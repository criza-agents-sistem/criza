# Design Gate — Especialista Ingeniero Agrónomo

**Versión:** 1.0
**Fecha:** 2026-08-16
**Módulo:** `criza/agronomo_agent/`
**Capa:** 2 (instancia CRIZA)
**Estado:** ✅ LISTO

---

## 1. Identidad

| Pregunta | Respuesta |
|---|---|
| ¿Qué es? | Tercer especialista de la "biblioteca de especialistas" (`docs/PROPUESTA_DESTINO.md` §5) — evalúa el **uso agronómico** de un producto/enfoque ya identificado por otros especialistas: ¿sirve de verdad como insumo agrícola/ganadero? Dosis, compatibilidad de cultivo/suelo, manejo en campo, marco normativo de aplicación. Distinto del Microbiólogo (madurez biológica/química) y del Ingeniero Ambiental (factibilidad de ingeniería de planta) — este especialista responde "¿esto funciona como insumo en producción real?", no "¿es biológicamente viable?" ni "¿se puede construir?". |
| ¿Qué problema resuelve en una oración? | Sebas confirmó una necesidad real y concreta: en Helios hay que encontrar un destino para el efluente, y es muy probable que ese destino sea el sector agropecuario — hace falta quien evalúe, confirme y asesore sobre eso específicamente. |
| ¿Quién lo usa? | Sebas, directo o vía el Conductor (`correr_especialista`, ya generalizado en la Etapa 7 — sumar este especialista es una línea en `_ESPECIALISTAS_CASOS`, no tocar el Conductor). |
| ¿De qué depende? | Mismas dependencias que `ingeniero_ambiental_agent` — `utils/ai_client.py`, `utils/corpus.py`, `km_tools/search.py`, `utils/openalex.py`, `utils/agrovoc.py`, `utils/casos.py`, `knowledge_module.preflight`, `knowledge_module.aprendizaje`. |
| ¿Qué depende de él? | El Conductor, vía `correr_especialista`. |
| ¿Milestone? | Extensión de la Etapa 7 del plan (segundo/tercer especialista), pedida explícitamente por Sebas el mismo día. |

---

## 2. Trazabilidad diseño → implementación

### Por qué este especialista, ahora — señal real, no elección en abstracto

`docs/PROPUESTA_DESTINO.md` §11 y el Design Gate del Ingeniero Ambiental (decisión B) dejaron
explícito que el Agrónomo "queda para si aparece un caso real que lo pida" — no se construye
especulativamente. Antes de construirlo se le preguntó a Sebas explícitamente si había una
necesidad real (mismo patrón que ya funcionó con las tools bioquímicas del Microbiólogo: no
asumir, preguntar, y si hay señal real, construir con confianza). Respuesta: **"En Helios tenemos
que encontrar un uso para los efluentes y es muy probable que un destino sea el sector
agropecuario, necesitamos un ingeniero agrónomo para evaluar, confirmar, asesorar."** — señal
real y concreta, no especulación.

### Clonado de `ingeniero_ambiental_agent.py`, mismo patrón, mismas simplificaciones

Tercer consumidor del template validado en la Etapa 1 (Microbiólogo) y confirmado en la Etapa 7
(Ingeniero Ambiental) — sin diseño nuevo de fondo. Mismas decisiones ya tomadas para el Ingeniero
Ambiental, por la misma razón (ver ese Design Gate):
- **Solo `frente_id`** (modelo `casos.yaml`), no `oportunidad_id` — ningún caller real necesitaría
  el modelo viejo para un especialista construido hoy.
- **Mismas 4 tools genéricas de corpus** (`search_literature`, `buscar_corpus_cientifico`,
  `search_corpus_inta`, `expand_agrovoc`) — sin tools de dominio específicas (ej. bases de datos
  de normativa fitosanitaria) hasta que una corrida real muestre el hueco.
- **Mismo schema exacto de `submit_evaluacion_tecnica`** que Microbiólogo/Ingeniero Ambiental —
  el shape ya se diseñó para reusarse entre especialistas (decisión E, Design Gate del
  Microbiólogo).

### Entidades

| Entidad | Descripción | Estado |
|---|---|---|
| `search_literature` / `buscar_corpus_cientifico` / `search_corpus_inta` / `expand_agrovoc` | Mismas 4 tools genéricas — `search_corpus_inta` es especialmente relevante acá (`search_corpus_inta` cubre "producción agropecuaria argentina" en su propia descripción). | ✅ construido |
| `submit_evaluacion_tecnica` | Mismo schema. | ✅ construido |

### Contrato SEB-115

```python
INPUT_CONTRACT  = {"agent": "agronomo", "version": "1.0",
                   "fields": {caso, tarea, contexto, conocimiento: {"frente_id": str}, herramientas}}
OUTPUT_CONTRACT = {"agent": "agronomo", "version": "1.0",
                   "km_escribe": ["documento_caso conectado vía frente_produce_documento"],
                   "fields": {análisis, nivel_confianza, recomendaciones, próximo_agente, nuevo_conocimiento}}
```

### KM write

| Tipo de output | Qué contiene | Key en KM | Cómo | Estado |
|---|---|---|---|---|
| **Resultado estructurado + informe** | Mismo shape que los otros 2 especialistas | `documento_caso` conectado vía `frente_produce_documento` | La costura, no el agente | ✅ construido |
| **Token usage** | Tokens consumidos | `props.token_usage.agronomo` del **frente** | El agente escribe esto directo — mismo patrón | ✅ construido |
| **Aprendizaje** | Lecciones del caso | área `lecciones` | 🔵 pendiente — misma deuda intencional que los otros 2 | — |

---

## 3. Checklist del playbook

### Estructura de archivos

- [x] `agronomo_agent.py` — SYSTEM_PROMPT + TOOLS + `run_agent_desde_frente()` + `run()`
- [x] `run.py`
- [x] `docs/DESIGN_GATE.md` — este archivo
- [x] `.env.example`
- [x] `tests/`

### Testing

- [x] Test: `TOOLS` tiene exactamente 5 tools
- [x] **Test explícito del checklist anti-sesgo: `SYSTEM_PROMPT` no contiene ninguna de las
      strings "Helios", "biogás", "biodigestor", "Mateo", "Andrés"** — mismo control que los
      otros 2 especialistas.
- [x] Test: `run()` requiere `frente_id`, no acepta `oportunidad_id`
- [x] Test: `run_agent_desde_frente` mock captura `submit_evaluacion_tecnica`
- [x] Al menos 1 integration test real **vía la costura** (`invocar_agente`, no el agente
      directo — la lección de la Etapa 7 se aplica desde el arranque acá) contra un frente real
      (staging, no producción)

---

## 4. Scope explícito por versión

| Feature | Versión | Razón |
|---|---|---|
| Camino `oportunidad_id` | No planeado | Mismo criterio que Ingeniero Ambiental. |
| Tools de dominio específicas (normativa fitosanitaria, bases de datos de suelos/cultivos) | v2, si hace falta | No se identificó ninguna necesidad concreta todavía — mismo criterio de siempre. |
| Persistencia de lecciones de caso | backlog | Misma deuda intencional. |

---

## 5. Decisiones requeridas antes de arrancar

| # | Pregunta | Opciones | Decisión tomada | Fecha |
|---|---|---|---|---|
| A | ¿Hay necesidad real que justifique este especialista ahora? | Sí, señal concreta / No, esperar | **Sí** — Sebas confirmó explícitamente: Helios necesita destino para su efluente, el sector agropecuario es un destino probable, hace falta quien lo evalúe. No se construyó por completar el trío de `PROPUESTA_DESTINO.md` §5, se construyó porque había señal real. | 2026-08-16 |
| B | ¿Rol exacto — evalúa producción agrícola en general, o el uso agronómico de un producto/enfoque ya identificado? | General / Uso agronómico de un enfoque ya identificado | **Uso agronómico de un enfoque ya identificado** — mismo patrón que Microbiólogo (biología) e Ingeniero Ambiental (ingeniería): cada especialista evalúa una DIMENSIÓN de un enfoque que ya existe, no arranca de cero. Acá la dimensión es: ¿funciona como insumo agrícola/ganadero real? | 2026-08-16 |
| C | ¿Tool set y schema? | Nuevos / Reusar los de Ingeniero Ambiental | **Reusar tal cual** — mismo criterio ya aplicado dos veces, sin razón para desviarse. | 2026-08-16 |
| D | Etapa 10 (2026-08-16) — mismo pedido de Sebas: chat directo con el especialista. | Mismo patrón que `microbiologo_agent.py`/`ingeniero_ambiental_agent.py` / uno propio | **Mismo patrón, sin variación** — tercer consumidor del patrón conversacional (`_despachar_tool` extraído, `TOOLS_CHAT`, `iniciar_sesion`/`enviar_mensaje`), mismo razonamiento de las otras dos: la evaluación formal persistida sigue siendo exclusiva de la corrida de un turno vía la costura. | 2026-08-16 |

---

## 6. Estado del gate

**Estado actual:** ✅ LISTO

Decisiones A-D cerradas, ninguna abierta. Tercer consumidor del patrón — sin diseño nuevo de
fondo, la única decisión real de esta ronda fue confirmar que había señal real antes de construir
(decisión A).

**Deuda intencional documentada:**
- Camino `oportunidad_id` → no planeado
- Tools de dominio específicas → solo si una corrida real las requiere
- Persistencia de lecciones de caso → backlog
- El chat (decisión D) no escribe lecciones al cierre (a diferencia del Conductor, Etapa 9) —
  mismo backlog
