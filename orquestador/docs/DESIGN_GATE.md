# Design Gate — Orquestador

**Versión:** 1.2
**Fecha:** 2026-08-16
**Módulo:** `criza/orquestador/`
**Capa:** 2 (instancia CRIZA)
**Estado:** ✅ LISTO (Motor v2) — ⚠️ ver nota de staleness abajo

> **Nota de staleness (2026-08-16):** las §1-6 originales de este gate (versión 1.1, 2026-06-16)
> describen el **Orquestador v1 — LLM-driven** (`SYSTEM_PROMPT` + `TOOLS`, `correr_divergente`,
> `correr_evidence_especialista` como tool). Ese diseño quedó reemplazado por el **Motor v2 —
> flows YAML declarativos** (`orquestador/motor.py`, sin LLM, ver
> `docs/DISEÑO_MOTOR_ORQUESTADOR.md`, SEB-152 ✅ 2026-06-27) — el código real de
> `orquestador/motor.py` ya no tiene nada de lo que describen §1-6 (no hay `SYSTEM_PROMPT`, no
> hay `TOOLS`, no hay Divergente). Reescribir el gate completo para reflejar Motor v2 es deuda
> aparte, no se hace en esta sesión — acá solo se agrega §7 (nuevo) para las 3 primitivas de
> Etapa 2, que sí son código real de hoy.

---

## 1. Identidad

| Pregunta | Respuesta |
|---|---|
| ¿Qué es? | Motor dirigido por objetivo: recibe un pedido humano de cualquier tipo, elige qué agentes correr y en qué orden, coordina el pipeline hasta producir el expediente. Embrión del CEO de la empresa agéntica. |
| ¿Qué problema resuelve? | Sin Orquestador, el pipeline depende del humano en cada paso: qué agente correr, en qué orden, qué hacer con el output. |
| ¿Quién lo activa? | Sebas — con cualquier tipo de pedido (ver §2 Tipos de entrada) |
| ¿De qué depende? | `divergent_agent`, `market_agent`, `evidence_generalista`, `evidence_especialista_*`, `armador`, `motor_api` (KM), `aprendizaje` |
| ¿Qué depende de él? | Nadie — es el punto de entrada del sistema |
| ¿Milestone? | M1 — Base sólida. Sin Orquestador no hay pipeline completo testeable. |

---

## 2. Trazabilidad diseño → implementación

### Tipos de entrada — el Orquestador como punto de entrada único

El Orquestador no recibe solo un `oportunidad_id`. Recibe un pedido de cualquier tipo y decide qué agentes activar:

| Tipo de entrada | Payload | Primer agente que corre | Gate humano |
|---|---|---|---|
| `blue_ocean` | `{tipo: "blue_ocean", sector: "...", contexto: "..."}` | Divergente (modo C — abierto) | Sebas elige candidato del divergente |
| `dolor` | `{tipo: "dolor", descripcion: "...", mercado_objetivo: "..."}` | Market agent directamente (salteando divergente) | Sebas aprueba entrada |
| `tecnologia` | `{tipo: "tecnologia", descripcion: "...", empresa: "..."}` | Divergente (modo A — tecnología fijada) | Sebas elige candidato del divergente |
| `investigacion` | `{tipo: "investigacion", resumen: "...", fuente: "..."}` | Evidence generalista directamente | Sebas aprueba entrada |
| `oportunidad_id` | `{tipo: "oportunidad_id", id: "uuid-xxx"}` | Lee KM → continúa desde donde estaba | Ninguno — retoma pipeline |

**Gates humanos en el pipeline:**
1. Sebas envía el pedido inicial (primer gate)
2. Si el pipeline pasó por el divergente → Sebas elige el candidato antes de que siga
3. Sebas recibe el expediente (gate final)

No hay aprobaciones en pasos intermedios (market → evidence → armador corren automáticamente).

### Entidades / tools del Orquestador

| Entidad | Descripción | Scope v1 | Estado |
|---|---|---|---|
| `leer_estado_oportunidad` | Lee el KM: qué props existen, qué agentes ya corrieron | ✅ incluido | ✅ construido |
| `crear_oportunidad` | Crea ficha en área `descubrimiento/solucion` a partir de dolor/investigacion; agrega nombre/descripcion en props | ✅ incluido | ✅ construido |
| `correr_market_agent` | Llama `market_agent.run_agent(oportunidad_id)` vía lazy import | ✅ incluido | ✅ construido |
| `correr_evidence_generalista` | Llama `evidence_generalista.run_agent(oportunidad_id)` vía lazy import | ✅ incluido | ✅ construido |
| `correr_evidence_especialista` | Stub v1: retorna disponible=false, continuar al armador sin error | ✅ incluido | ✅ construido (stub) |
| `correr_armador` | Llama `armador.run_agent(oportunidad_id)` vía lazy import | ✅ incluido | ✅ construido |
| `submit_pipeline_completo` | Escribe `props.pipeline_status` en KM; status: completo/error/esperando_humano | ✅ incluido | ✅ construido |
| `correr_divergente` | — | blue_ocean/tecnologia no soportados en v1 (SEB-147) | Fuera de scope v1 — SYSTEM_PROMPT lo maneja como STOP |

### Contrato de interfaz — todos los agentes que el Orquestador llama

El Orquestador espera que cada agente exponga exactamente esta interfaz:

```python
async def run_agent(oportunidad_id: str, verbose: bool = False) -> tuple[str, dict, list[str]]:
    """Retorna (informe_markdown, datos_estructurados, lecciones_caso)"""
```

Cada agente es responsable de:
- Leer lo que necesita del KM (`motor_api.obtener`)
- Hacer su trabajo
- Escribir su output al KM (`motor_api.actualizar_props`)
- Retornar el tuple estándar

El Orquestador no interpreta el output — solo ejecuta y pasa al siguiente paso.

### KM write — Orquestador

| Tipo de output | Qué contiene | Key en KM | Cómo | Estado |
|---|---|---|---|---|
| **Resultado estructurado** | Estado del pipeline: qué agentes corrieron, cuándo, estado | `props.pipeline_status` | `motor_api.actualizar_props` | ⚠️ por construir |
| **Informe narrativo completo** | No aplica — el informe es el expediente del Armador | — | Decisión A: el Armador es el informe | ✅ decisión documentada |
| **Aprendizaje** | Lecciones sobre el pipeline (routing, gaps, decisiones) | área `lecciones` | `aprendizaje.guardar_leccion_caso` | ⚠️ por construir |

---

## 3. Checklist del playbook

### Seguridad Nivel 1

- [ ] Credenciales en `.env`, nunca en código
- [ ] `.env` en `.gitignore`
- [ ] `.env.example` completo
- [ ] Sin credenciales en historial de git

### Estructura de archivos

- [ ] `orquestador.py` — SYSTEM_PROMPT + TOOLS + run_agent()
- [ ] `run.py` — runner interactivo (recibe oportunidad_id)
- [ ] `docs/DESIGN_GATE.md` — este archivo
- [ ] `.env.example`
- [ ] `tests/`

### Testing

- [x] Test: leer_estado_oportunidad con props vacíos → market_agent en pendientes
- [x] Test: leer_estado_oportunidad con mercado completo → evidence_generalista en pendientes
- [x] Test: generalista recomienda especialista → evidence_especialista en pendientes
- [x] Test: todos los cruces completos → armador en completados
- [x] Test: agente no llama su submit_* → tool retorna success=false + STOP
- [x] Test: tool_especialista_v1 → disponible=false, success=true (no bloquea)
- [x] Test: run_agent mock → llama submit_pipeline_completo, retorna status y oportunidad_id

---

## 4. Scope explícito por versión

| Feature | Versión | Razón del postergue |
|---|---|---|
| Ejecución paralela market + generalista | v1.1 | Simplifica v1; el gain de velocidad no es crítico para M1 |
| Múltiples especialistas simultáneos | v1.1 | Solo existe un especialista en v1 |
| Drill-down / "más info sobre X" | v2 | Requiere motor v2 |
| Motor v2 (flujos declarados YAML) | v2.0+ | Diseño completo en `docs/DISEÑO_MOTOR_ORQUESTADOR.md` (SEB-152 ✅ 2026-06-27) |
| Autonomía sin gate humano inicial | v2 | Gate en el inicio (Sebas da el oportunidad_id) se mantiene siempre |
| Loop de mejora del expediente | v2 | Si el Armador detecta gaps críticos, volver a correr agentes |

---

## 5. Decisiones requeridas antes de arrancar

| # | Pregunta | Opciones | Decisión | Fecha |
|---|---|---|---|---|
| A | ¿Qué hace el Orquestador si un agente falla? | A: STOP y notifica / B: continúa con gap | **Depende del tipo de falla**: si el agente no llamó su `submit_*` → STOP y notifica a Sebas (falla real, seguir quema tokens sin sentido). Si el agente llamó `submit_*` pero con datos parciales → continúa (el Armador maneja `a-confirmar`). | 2026-06-16 |
| B | ¿Ejecución paralela market + generalista en v1? | Paralela / Secuencial | **Secuencial** en v1. Paralela en v1.1. | 2026-06-16 |
| C | ¿Cómo sabe el Orquestador qué especialistas están disponibles? | Registry en código / Descubrimiento dinámico | **Registry en código** (`dict` slug→módulo). El LLM razona sobre las opciones disponibles. | 2026-06-16 |
| D | ¿El Orquestador escribe estado propio en KM (`props.pipeline_status`)? | Sí / No | **Sí** — permite recovery si se interrumpe y da trazabilidad del pipeline. | 2026-06-16 |
| E | ¿El generalista puede recomendar "ningún especialista"? | Sí / No | **Sí** — si la evidencia de literatura es suficiente para cruce 2, no hay necesidad de especialista. | 2026-06-16 |
| F | ¿Orquestador híbrido (determinístico para decisiones obvias) o LLM puro? | Híbrido / LLM puro | **LLM puro en v1.** Se analizó la opción híbrida (reducir tokens en decisiones obvias) pero introduce complejidad sin datos de uso real que justifiquen la inversión. Revisar después de correr el pipeline completo 5-10 veces y ver los token_usage reales. | 2026-06-16 |

---

## 6. Estado del gate

**Estado actual:** ✅ LISTO — 20/20 tests pasando

**Deuda intencional documentada:**
- Ejecución paralela → v1.1
- Múltiples especialistas → v1.1
- Drill-down → v2
- `correr_divergente` (blue_ocean/tecnologia) → requiere SEB-147 formalizar divergente
- `correr_evidence_especialista` real → requiere refactor scientific_agent (SEB-149)
- **Reescribir §1-6 para reflejar Motor v2** (ver nota de staleness al inicio del documento) —
  deuda documentada, no crítica (el código funciona y está testeado, el gate describe una
  generación anterior del diseño)

---

## 7. Primitivas de invocación del Motor v2 (Etapa 2, 2026-08-16)

Del plan de construcción del nuevo sistema de agentes (`C:\Users\sebab\.claude\plans\
greedy-cooking-llama.md`, Etapa 2): `PROPUESTA_CONDUCTOR.md` §5 pide 5 primitivas de invocación
para que el Conductor (Etapa 5) pueda operar sobre un caso sin bypasear la costura. Diagnóstico
del 2026-08-16: correr un agente ✅ y invocar con tarea/contexto propios ✅ ya estaban resueltos
(`ejecutar()`, `contract_input`). Faltaban 3: "ver qué le falta a un caso" (existía solo como
excepción bloqueante en `armador.py::_validar_cobertura_upstream`, específica a mercado/evidencia),
"estimar costo antes de correr" (no existía), y `reanudar()` generalizado (solo servía para
retomar justo después de un gate humano, atado al `gate_data` en memoria del `MotorResult`
anterior — se perdía si la sesión que disparó el gate ya no existía).

### Entidades nuevas

| Entidad | Descripción | Estado |
|---|---|---|
| `inspeccionar_caso(flow, oportunidad_id, tenant, registry)` | "¿Qué le falta a este caso?" — generaliza `armador._validar_cobertura_upstream` (hardcodeado a mercado/evidencia) a cualquier step `type: agent` de cualquier flow: por cada step, ¿ya existe `props[prop_key]`? Solo lee, no ejecuta nada, no lanza excepción — devuelve `InspeccionResult` con `completos`/`pendientes`/`no_disponibles`. | ✅ construido |
| `estimar_costo(flow, oportunidad_id, tenant, registry)` | Estima tokens de los steps pendientes (según `inspeccionar_caso`) promediando `props.token_usage.<agente>` real de otras oportunidades ya corridas (`utils/token_tracker.py` es la fuente — nunca un número inventado). Sin histórico para un agente, ese paso queda `tokens_estimados=None` (a-confirmar), no un cero encubierto — y el total agregado también queda `None` si falta algún dato, en vez de sumar parcial y aparentar certeza que no hay. | ✅ construido |
| `reanudar_desde(flow, oportunidad_id, desde_step, tenant, registry, entry=None)` | Generaliza `reanudar()`: reconstruye `steps_output`/`pipeline_status` **únicamente desde lo que ya está persistido en el KM** (`props.pipeline_status.steps` + `props[prop_key]` por step) — no depende del `gate_data` en memoria de un `MotorResult` anterior. Es la primitiva real detrás de "otra puerta de entrada, nunca un bypass" (`PROPUESTA_CONDUCTOR.md` §3.1): el Conductor puede retomar un caso sin haber sido quien lo pausó. `reanudar()` (post-gate-humano) queda intacto, sin cambios — `reanudar_desde` es una primitiva nueva, más general, no un reemplazo. | ✅ construido |

**Decisión de diseño:** `entry` (los campos originales del pedido humano — `descripcion`,
`sector`, etc.) no se persiste hoy en `props.pipeline_status` (solo vive en el `state` en memoria
de una corrida activa) — `reanudar_desde` lo recibe como parámetro opcional en vez de intentar
reconstruirlo desde el KM. Si algún step posterior al punto de reanudación necesita `{entry.*}`
y no se pasa `entry`, el template queda sin resolver (comportamiento ya existente de `_resolve()`,
no un crash) — persistir `entry` en el KM es deuda de una etapa futura si se vuelve un problema
real de uso, no algo a resolver por anticipado acá.

### Tests

- [x] `inspeccionar_caso`: step con prop presente → `completo`; prop ausente → `pendiente`;
      agente inactivo/no registrado → `no_disponible`
- [x] `inspeccionar_caso`: solo considera steps `type: agent` (ignora `km_write`/`gate_humano`)
- [x] `estimar_costo`: con histórico real → promedio correcto, `basado_en` = cantidad de muestras
- [x] `estimar_costo`: sin histórico para un agente → `tokens_estimados=None`, total agregado
      también `None` (no aparenta certeza que no hay)
- [x] `estimar_costo`: sin steps pendientes → `total_estimado=0`, lista de pasos vacía
- [x] `reanudar_desde`: reconstruye `steps_output` desde `props[prop_key]` + `pipeline_status` del
      KM, sin usar `gate_data` en memoria
- [x] `reanudar_desde`: step inexistente en el flow → `ValueError` explícito
- [x] Al menos 1 test que reanude un flow parcial real (integration) sin re-pagar los pasos ya
      corridos (verificación explícita del plan, Etapa 2)
