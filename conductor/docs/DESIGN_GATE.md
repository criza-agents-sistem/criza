# Design Gate — Conductor

**Versión:** 1.0
**Fecha:** 2026-08-16
**Módulo:** `criza/conductor/`
**Capa:** 2 (instancia CRIZA)
**Estado:** ✅ LISTO

---

## 1. Identidad

| Pregunta | Respuesta |
|---|---|
| ¿Qué es? | Agente conversacional — el punto de entrada con el que Sebas decide qué hacer a continuación sobre un caso. Lee el estado real, arma el briefing (`docs/PROTOCOLO_LECTURA_CONDUCTOR.md`, Etapa 3), invoca especialistas cuando se le pide, registra qué se decidió. |
| ¿Qué problema resuelve en una oración? | Que Sebas no tenga que reconstruir el contexto de un caso a mano cada vez (`PROPUESTA_CONDUCTOR.md` §3 — el rol ya se ejerció a mano el 22/07, esto lo hace repetible). |
| ¿Quién lo usa? | Sebas, directo — es el primer consumidor real del protocolo de la Etapa 3 y las primitivas de la Etapa 2. |
| ¿De qué depende? | `orquestador/invocador.py` (la costura, nunca la bypasea), `utils/casos.py`, `orquestador/registry.py`, `scripts/km_decisiones.py`, `knowledge_module.aprendizaje`, `utils/ai_client.py`. |
| ¿Qué depende de él? | Nada todavía — es el punto de entrada final del sistema, no una pieza que otro componente consuma. |
| ¿Milestone? | Etapa 5 del plan de construcción del nuevo sistema de agentes (`docs/progress/2026-08-16.md`). |

---

## 2. Trazabilidad diseño → implementación

### Por qué es arquitectónicamente distinto a los demás agentes

Todos los agentes de CRIZA hasta hoy (`market_agent`, `evidence_generalista`,
`investigacion_amplia`, `armador`, `microbiologo_agent`) son **de un solo turno**: reciben un
`contract_input`, corren un loop de tools hasta llamar su `submit_*`, devuelven un resultado
estructurado (contrato SEB-115). El Conductor **no encaja en ese molde** — es conversacional,
multi-turno: Sebas manda un mensaje, el Conductor responde (usando tools si hace falta), la
conversación sigue. Forzarlo al contrato SEB-115 (`run(contract_input) -> dict` de una sola
llamada) rompería exactamente lo que lo hace útil. Por eso **no tiene `INPUT_CONTRACT`/
`OUTPUT_CONTRACT` ni se registra en `orquestador/agents_registry.yaml`** — no es un agente que
el Motor invoque dentro de un flow, es el cliente conversacional que decide cuándo invocar a los
demás.

### Qué modelo de datos lee — casos.yaml, no oportunidad+flow

`docs/PROTOCOLO_LECTURA_CONDUCTOR.md` (Etapa 3) diseñó el protocolo de lectura asumiendo
`inspeccionar_caso`/`estimar_costo` (Etapa 2) como las primitivas de "qué falta" — esas
funciones están acotadas al modelo `oportunidad_id` + flow YAML. Pero la Etapa 4 (mismo día)
conectó al primer especialista (Microbiólogo) al modelo de `casos.yaml` (`frente_id`), que es
el modelo real que usa Helios hoy — **no una oportunidad con un flow**. El Conductor v1 se
construye contra el modelo que existe de verdad para el caso real (`casos.yaml`), no contra el
modelo que las primitivas de Etapa 2 asumían — se agregaron 2 funciones chicas a `utils/casos.py`
(`obtener_frentes_de_caso`, `obtener_documentos_de_frente`) para completar el paralelo de "¿qué
falta?" en el modelo de casos, análogo a lo que `inspeccionar_caso` hace para oportunidad+flow.
`inspeccionar_caso`/`estimar_costo`/`reanudar_desde` (Etapa 2) siguen existiendo para cuando un
caso use el modelo viejo — el Conductor no las descarta, hoy no las necesita porque Helios/
MicroBigs no tienen ninguna oportunidad asociada.

### Entidades

| Entidad | Descripción | Estado |
|---|---|---|
| `listar_casos` | Lista los casos existentes (`utils/casos.py::listar_casos`) — para no requerir que Sebas sepa IDs de antemano. | ✅ construido |
| `ver_caso` | El briefing completo de un caso — identidad, frentes (con si cada uno ya tiene `documento_caso` o no), pendientes abiertos, lecciones relevantes, decisiones de sistema vigentes. Implementa el protocolo de la Etapa 3, adaptado al modelo real (`casos.yaml`). | ✅ construido |
| `correr_microbiologo` | Invoca al Especialista Microbiólogo contra un frente, vía la costura (`invocar_agente(..., frente_id=...)`) — nunca corre el agente directo, siempre por el mismo camino que cualquier otro invocador (`PROPUESTA_CONDUCTOR.md` §3.1, "otra puerta de entrada, nunca un bypass"). | ✅ construido |
| `ver_documento` | Lee el contenido completo de un `documento_caso` puntual — para cuando Sebas quiere profundizar en algo que `ver_caso` solo resumió. | ✅ construido |

**No incluido en v1** (ver §4): invocar otros especialistas (solo existe el Microbiólogo hoy —
Etapa 7 suma el segundo), `estimar_costo`/`inspeccionar_caso`/`reanudar_desde` de Etapa 2 (el
modelo `oportunidad`+flow no tiene ningún caso real activo hoy — se conectan cuando haga falta),
persistencia de qué se decidió en la conversación (ver §4 y `PROPUESTA_CONDUCTOR.md` §9 decisión
4, sigue abierta).

### El loop conversacional — por qué no es el loop de los otros agentes

Los agentes de un turno corren `while True: llamar modelo → si tool_use, despachar → si
submit_*, terminar`. El Conductor corre `while True: leer mensaje de Sebas → llamar modelo (con
historial completo) → si tool_use, despachar y seguir en el mismo turno → mostrar la respuesta de
texto → volver a esperar el próximo mensaje de Sebas`. La diferencia central: los agentes de un
turno tienen un criterio de fin explícito (`submit_*` llamado); el Conductor no — termina cuando
Sebas lo corta (`salir`/Ctrl+C), no cuando "terminó de pensar".

### KM write — Conductor

| Tipo de output | Qué contiene | Key en KM | Cómo | Estado |
|---|---|---|---|---|
| **Ninguno propio** | El Conductor no escribe ningún resultado propio — lee, y cuando invoca al Microbiólogo, la costura persiste el resultado del Microbiólogo (no del Conductor). | — | — | ✅ por diseño, no hay nada que construir acá |
| **Captura de qué se decidió en la conversación** | Ej. "descartamos microalgas por costo de escalado" | — | — | 🔵 **no resuelto** — mismo gap que `docs/PROTOCOLO_LECTURA_CONDUCTOR.md` §5 ya declaró explícitamente: decisiones de negocio dentro de un caso no tienen hoy un lugar dedicado. El Conductor v1 no lo resuelve — conversa, no persiste el resultado de la conversación. |

---

## 3. Checklist del playbook

### Seguridad Nivel 1

- [x] Credenciales en `.env` propio del módulo, nunca en código
- [x] `.env.example` completo
- [x] Sin credenciales en historial de git

### Estructura de archivos

- [x] `conductor.py` — SYSTEM_PROMPT + TOOLS + loop conversacional
- [x] `run.py` — REPL interactivo
- [x] `docs/DESIGN_GATE.md` — este archivo
- [x] `.env.example`
- [x] `tests/`

### Testing

- [x] Test: `TOOLS` tiene las 4 entidades de §2
- [x] Test: `ver_caso` arma el briefing con frentes + estado de documentos + pendientes
- [x] Test: `correr_microbiologo` pasa por `invocar_agente` con `frente_id`, nunca llama al
      agente directo
- [x] Test: el loop conversacional mantiene historial entre turnos (mensaje 2 puede referirse a
      algo dicho en el mensaje 1)
- [x] Al menos 1 sesión conversacional real sobre Helios — corrida real (no mock) verificada:
      "¿Qué casos tenemos?" → `listar_casos` real (2 casos reales, MicroBigs + Helios);
      "Contame cómo viene Helios" → llamó `ver_caso` (no inventó el estado), reportó
      correctamente 0 documentos en ambos frentes, citó los pendientes reales del caso (la
      reunión con Mateo, el supuesto del flete sin confirmar) y recomendó no correr ningún
      especialista hasta resolver el bloqueo de negocio — comportamiento equivalente al que
      Sebas ejerció a mano el 22/07 (leer antes de actuar, no gastar en un análisis que el
      caso no está listo para recibir).

---

## 4. Scope explícito por versión

| Feature | Versión | Razón |
|---|---|---|
| Invocar otros especialistas además del Microbiólogo | v2 (Etapa 7 del plan) | Solo existe un especialista casos.yaml-conectado hoy. |
| Primitivas de Etapa 2 (`inspeccionar_caso`/`estimar_costo`/`reanudar_desde`, modelo `oportunidad`+flow) | v2, si aparece un caso real en ese modelo | Ningún caso real activo usa ese modelo hoy (Helios/MicroBigs son `casos.yaml`) — conectarlas ahora sería diseño especulativo. |
| Captura de qué se decidió en la conversación | Backlog, sin resolver | Mismo gap declarado en `docs/PROTOCOLO_LECTURA_CONDUCTOR.md` §5 — no se inventa un mecanismo sin un caso real que fuerce la forma correcta. |
| Consola web (`PROPUESTA_CONDUCTOR.md` §7) | Etapa 6 del plan | El Conductor v1 es CLI (`run.py`), como todos los agentes hoy. |

---

## 5. Decisiones requeridas antes de arrancar

| # | Pregunta | Opciones | Decisión tomada | Fecha |
|---|---|---|---|---|
| A | ¿Contrato SEB-115 (`run(contract_input)`) o loop conversacional propio? | SEB-115 / Loop propio | **Loop propio.** El contrato SEB-115 asume una sola llamada con un resultado final estructurado — el Conductor es multi-turno por diseño, forzarlo rompería lo que lo hace útil. No se registra en `agents_registry.yaml` (no es un step de flow). | 2026-08-16 |
| B | ¿Contra qué modelo de datos arma el briefing — `oportunidad`+flow (Etapa 2) o `casos.yaml` (Etapa 4)? | Etapa 2 (primitivas ya construidas) / Etapa 4 (modelo real de Helios hoy) | **`casos.yaml`** — es el modelo que el caso real (Helios) usa hoy. Las primitivas de Etapa 2 quedan disponibles para cuando un caso real las necesite, no se descartan, no se usan todavía. | 2026-08-16 |
| C | ¿Qué agentes puede invocar en v1? | Solo Microbiólogo / Los 4 agentes viejos también | **Solo Microbiólogo** — es el único conectado al modelo `casos.yaml` (Etapa 4). Los 4 agentes viejos siguen sin tocarse (`PROPUESTA_DESTINO.md` §6, decisión ya tomada, no se reabre acá). | 2026-08-16 |
| D | ¿Persiste qué se decidió en la conversación? | Sí, mecanismo nuevo / No, gap conocido | **No en v1** — mismo gap ya declarado explícitamente en `docs/PROTOCOLO_LECTURA_CONDUCTOR.md` §5. Inventar el mecanismo sin un caso real que muestre la forma correcta repetiría el error que este proyecto viene evitando toda la sesión. | 2026-08-16 |

---

## 6. Estado del gate

**Estado actual:** ✅ LISTO

Decisiones A-D cerradas, ninguna abierta.

**Deuda intencional documentada:**
- Invocar otros especialistas → Etapa 7 del plan
- Primitivas de Etapa 2 (`oportunidad`+flow) → v2, si aparece un caso real en ese modelo
- Captura de decisiones de la conversación → backlog, gap conocido y declarado
- Consola web → Etapa 6 del plan
