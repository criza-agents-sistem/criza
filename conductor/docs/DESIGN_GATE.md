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
| `correr_especialista` | Invoca a un especialista de la biblioteca (por nombre) contra un frente, vía la costura (`invocar_agente(..., frente_id=...)`) — nunca corre el agente directo, siempre por el mismo camino que cualquier otro invocador (`PROPUESTA_CONDUCTOR.md` §3.1, "otra puerta de entrada, nunca un bypass"). **Generalizado en la Etapa 7** (era `correr_microbiologo`, hardcodeado a un solo especialista) — al sumar el Ingeniero Ambiental como segundo especialista casos.yaml-conectado, hardcodear un tool por especialista dejó de escalar. Ahora valida contra `_ESPECIALISTAS_CASOS` (lista explícita en `conductor.py`, no inferida del registry — los 4 agentes viejos, oportunidad_id-only, no deben poder invocarse desde acá). Sumar un especialista nuevo de acá en más = agregar una entrada a esa lista, sin tocar `TOOLS` ni el dispatch. | ✅ construido, generalizado 2026-08-16 |
| `ver_documento` | Lee el contenido completo de un `documento_caso` puntual — para cuando Sebas quiere profundizar en algo que `ver_caso` solo resumió. | ✅ construido |

**No incluido en v1** (ver §4): `estimar_costo`/`inspeccionar_caso`/`reanudar_desde` de Etapa 2
(el modelo `oportunidad`+flow no tiene ningún caso real activo hoy — se conectan cuando haga
falta), persistencia de qué se decidió en la conversación (ver §4 y `PROPUESTA_CONDUCTOR.md` §9
decisión 4, sigue abierta).

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
| **Resultado de especialista** | El Conductor no escribe ningún resultado de especialista propio — lee, y cuando invoca al Microbiólogo, la costura persiste el resultado del Microbiólogo (no del Conductor). | — | — | ✅ por diseño, no hay nada que construir acá |
| **Historial de la sesión (raw)** | Cada turno del chat, sin destilar — `role`/`content` completo, serializado con `conductor.py::serializar_mensajes`. **Sumado 2026-08-16**: Sebas preguntó explícitamente por qué se perdían al reiniciar `api/run.py`; antes vivía en un dict en memoria del proceso de `api/main.py`. | área `conductor_sesiones`, tipo `sesion` (`config/plantillas/conductor_sesiones.yaml`) | `motor_api.guardar_ficha` al crear la sesión (`POST /conductor/sesiones`), `motor_api.actualizar_props` en cada turno (`POST /conductor/sesiones/{id}/mensajes`) — ambos en `api/main.py`, no en `conductor.py` (el Conductor en sí sigue sin saber de KM, igual que antes; quien lo envuelve para servirlo por HTTP es quien decide cómo persistir la sesión) | ✅ resuelto — verificado con una corrida real: sesión creada, mensaje enviado, proceso matado (`taskkill /F`, no shutdown limpio), proceso nuevo levantado, segundo mensaje a la misma sesión recordó correctamente el primero (leído directo del KM: 6 mensajes, tool-use incluido, serializados bien) |
| **Lección destilada (no raw)** — automática | Ej. "chequear demanda de calor local antes de proponer generación eléctrica" — un patrón reusable, destilado del historial completo al cerrar la sesión, no una transcripción | área `lecciones`, tipo `leccion_caso`, `agente="conductor"`, `fuente="agente_auto"` (`knowledge_module/aprendizaje.py::guardar_leccion_caso`, SEB-156) | `conductor.py::cerrar_sesion(messages)` — llamado desde `run.py` al salir del REPL (CLI) y desde `POST /conductor/sesiones/{id}/cerrar` (web, botón "Nueva conversación" + `beforeunload` best-effort) | ✅ resuelto (Etapa 9, 2026-08-16) — verificado real: guardó una lección genuina, dijo "no" correctamente en una conversación de solo-lectura, y reconoció como "ya cubierta" una lección repetida (anti-duplicación) |
| **Lección destilada (no raw)** — explícita | Sebas dice "anotá esto" en cualquier momento del chat | área `lecciones`, tipo `leccion_caso`, `agente="conductor"`, `fuente="humano"` | tool `anotar_leccion` → `_tool_anotar_leccion` → `guardar_leccion_caso` | ✅ resuelto (Etapa 9, 2026-08-16) — verificado real, 3 lecciones guardadas en corridas reales contra el modelo real |
| **Caso nuevo** | Sebas describe un caso nuevo y confirma que quiere darlo de alta | área `casos`, tipo `caso` (`config/plantillas/casos.yaml`) | tool `crear_caso` → `_tool_crear_caso` → `utils/casos.py::crear_caso` — misma función que usa `POST /casos` de la web, sin duplicar lógica | ✅ resuelto (Etapa 13, 2026-08-17) — verificado real contra staging (creación real, campos correctos, `texto_busqueda` computado) y real contra el server de producción (una conversación real pidió confirmación antes de crear, sin llamar la tool, confirmado que no se creó nada) |

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
- [x] Bug real encontrado y arreglado (2026-08-17, verificando la Etapa 17 de `web/`, adjuntar
      archivos): `_tool_ver_documento` no capturaba un `documento_id` inválido (el modelo llamó la
      tool con `"Frente técnico"`, un nombre, no un UUID, sin llamar `ver_caso` primero) — la
      query cruda del KM reventaba con un `DataError` de asyncpg sin capturar, tirando abajo todo
      el turno (500, tokens del turno gastados, cero respuesta). Corregido con el mismo patrón
      `try/except` que ya usa `_resolver_caso()` para el mismo problema. Test nuevo:
      `test_tool_ver_documento_id_invalido_no_revienta_el_turno`.

---

## 4. Scope explícito por versión

| Feature | Versión | Razón |
|---|---|---|
| Invocar otros especialistas además del Microbiólogo | ✅ hecho (Etapa 7, 2026-08-16) | `correr_especialista` generalizado — ver decisión E abajo. |
| Primitivas de Etapa 2 (`inspeccionar_caso`/`estimar_costo`/`reanudar_desde`, modelo `oportunidad`+flow) | v2, si aparece un caso real en ese modelo | Ningún caso real activo usa ese modelo hoy (Helios/MicroBigs son `casos.yaml`) — conectarlas ahora sería diseño especulativo. |
| Captura de qué se decidió en la conversación | Backlog, sin resolver | Mismo gap declarado en `docs/PROTOCOLO_LECTURA_CONDUCTOR.md` §5 — no se inventa un mecanismo sin un caso real que fuerce la forma correcta. |
| Consola web (`PROPUESTA_CONDUCTOR.md` §7) | ✅ hecho (Etapa 6, `web/` + `api/`) | El Conductor sigue siendo CLI (`run.py`) — la consola web (Etapa 6) es solo-lectura, no conversacional todavía. |

---

## 5. Decisiones requeridas antes de arrancar

| # | Pregunta | Opciones | Decisión tomada | Fecha |
|---|---|---|---|---|
| A | ¿Contrato SEB-115 (`run(contract_input)`) o loop conversacional propio? | SEB-115 / Loop propio | **Loop propio.** El contrato SEB-115 asume una sola llamada con un resultado final estructurado — el Conductor es multi-turno por diseño, forzarlo rompería lo que lo hace útil. No se registra en `agents_registry.yaml` (no es un step de flow). | 2026-08-16 |
| B | ¿Contra qué modelo de datos arma el briefing — `oportunidad`+flow (Etapa 2) o `casos.yaml` (Etapa 4)? | Etapa 2 (primitivas ya construidas) / Etapa 4 (modelo real de Helios hoy) | **`casos.yaml`** — es el modelo que el caso real (Helios) usa hoy. Las primitivas de Etapa 2 quedan disponibles para cuando un caso real las necesite, no se descartan, no se usan todavía. | 2026-08-16 |
| C | ¿Qué agentes puede invocar en v1? | Solo Microbiólogo / Los 4 agentes viejos también | **Solo Microbiólogo** — es el único conectado al modelo `casos.yaml` (Etapa 4). Los 4 agentes viejos siguen sin tocarse (`PROPUESTA_DESTINO.md` §6, decisión ya tomada, no se reabre acá). | 2026-08-16 |
| D | ¿Persiste qué se decidió en la conversación? | Sí, mecanismo nuevo / No, gap conocido | **No en v1, revisado el mismo día.** El historial crudo de la conversación sí quedó resuelto horas después (ver `web/docs/DESIGN_GATE.md` decisión E — Sebas preguntó por qué se perdía al reiniciar el server). Persistir una lección *destilada* de la conversación es un problema distinto — ver decisión F. | 2026-08-16 |
| E | Al sumar el segundo especialista (Etapa 7), ¿un tool nuevo (`correr_ingeniero_ambiental`) o generalizar el existente? | Tool nuevo por especialista / Generalizar `correr_microbiologo` → `correr_especialista` | **Generalizar.** Con 2 especialistas ya era visible que un tool por especialista no escala (cada uno nuevo hubiera exigido tocar `TOOLS` + `_despachar_tool` + el SYSTEM_PROMPT). `correr_especialista(especialista, caso, frente, ...)` valida contra `_ESPECIALISTAS_CASOS` (lista explícita, no inferida del registry completo — los 4 agentes viejos no deben ser invocables desde acá). Sumar un especialista nuevo de acá en más es una línea en esa lista. | 2026-08-16 |
| F | Etapa 9 — el Conductor solo leía lecciones (`ver_caso` → `leer_lecciones_caso`), nunca escribía ninguna. ¿Cuándo escribe una lección nueva? | Solo automático al cerrar sesión / Solo explícito a pedido de Sebas / Ambos | **Ambos**, confirmado por Sebas ante la pregunta explícita. Automático: `cerrar_sesion(messages)` — un juez de una sola llamada (tool `submit_leccion`, sin forzar `tool_choice`, mismo patrón `submit_*` que ya usan los especialistas) evalúa el transcript completo contra las lecciones ya existentes (`leer_lecciones_caso`) y guarda solo si hay algo genuinamente nuevo (`fuente="agente_auto"`). Explícito: tool nueva `anotar_leccion` (`fuente="humano"`), para cuando Sebas dice "anotá esto". Verificado real, no solo con mocks: el trigger explícito guardó 3 lecciones reales bien formadas; el automático correctamente dijo "no" en una conversación de solo-lectura y correctamente reconoció como "ya cubierta" una lección que el propio trigger explícito ya había guardado en la misma sesión (anti-duplicación funcionando). Observación real, no un bug: el modelo tendió a invocar `anotar_leccion` por su cuenta ante afirmaciones sustanciales aunque el prompt le pide no hacerlo sin pedido explícito — deja la rama "automático, positivo, sin pedido previo" cubierta solo por tests con mock en esta sesión, no por una corrida real (documentado como observación, no urgente de corregir). | 2026-08-16 |
| G | Etapa 13 (2026-08-17) — Sebas: "¿cómo abro un caso nuevo? ¿solo con el Conductor?" — hasta acá NINGÚN camino creaba casos, ni la web ni el Conductor. ¿El Conductor gana una tool `crear_caso`, y con qué salvaguarda? | Crear apenas se menciona un caso nuevo / Confirmar antes de crear | **Confirmar antes de crear, siempre.** Mismo criterio que ya rige `correr_especialista` (gasta tokens/escribe al KM, no se llama sin pedido explícito) — acá el riesgo es peor porque un caso mal armado (nombre/descripción pobres) queda mal desde el arranque, sin un paso de corrección todavía (esa es la Etapa 14, sin resolver hoy). El `SYSTEM_PROMPT` instruye explícitamente: resumir nombre+descripción de vuelta y esperar confirmación antes de llamar la tool. Verificado real, no solo con mocks: una conversación real describiendo un caso nuevo hizo que el Conductor pidiera más detalles y prometiera confirmar antes de crear, sin llamar la tool — confirmado leyendo `/casos` después que no se creó nada. | 2026-08-17 |

---

| H | Etapa 17 (2026-08-17) — bug real encontrado al verificar "adjuntar archivo" en `web/`: ¿por qué `_tool_ver_documento` tiraba abajo todo el turno con un `documento_id` inválido? | Capturar el error y tratarlo como "no encontrado" / dejar el 500 tal cual | **Capturar**, mismo patrón que ya usaba `_resolver_caso()` para el mismo problema (un `identificador` que no es UUID válido). No hay ninguna razón para que un ID mal formado por el modelo cueste el turno completo — se trata igual que "no se encontró ese documento", el modelo puede reintentar o pedirle a Sebas el id correcto en el mismo turno. | 2026-08-17 |
| I | Etapa 19 (2026-08-18) — Sebas le preguntó al Conductor "necesito descargar los últimos informes de cada agente ... cómo se cuáles son?" y no pudo responder con ids reales — el briefing de `ver_caso` solo exponía el conteo y el título del último documento del frente, sin ordenar por fecha ni distinguir por especialista. ¿Detalle completo en `ver_caso` (más tokens) o una tool nueva bajo demanda? | Detalle completo en `ver_caso` / tool nueva `listar_documentos_de_frente` | **Detalle completo en `ver_caso`** (`documentos_producidos_detalle`: id + título + agente + fecha, por frente) — el Conductor ya llama `ver_caso` como primer paso casi siempre, una tool aparte hubiera sido una llamada extra evitable. Requirió arreglar la fuente primero: `utils/casos.py::obtener_documentos_de_frente` no ordenaba ni exponía `created_at` (delegaba en `motor_api.conexiones_de`, genérico, sin esa info) — sin orden confiable, `docs[-1]` (lo que ya se usaba para "último documento") no era realmente el más reciente. Ahora arma su propia consulta con `ORDER BY created_at ASC` — anotado como candidato a promover a `knowledge_module.motor.api.conexiones_de` si otra instancia lo necesita, no antes. Verificado real contra Helios: `ver_caso("Helios")` identificó los 4 últimos informes reales del Frente técnico (uno por especialista, de 13 totales), mismos ids que una consulta directa a la base. | 2026-08-18 |

## 6. Estado del gate

**Estado actual:** ✅ LISTO

Decisiones A-I cerradas, ninguna abierta.

**Deuda intencional documentada:**
- Primitivas de Etapa 2 (`oportunidad`+flow) → v2, si aparece un caso real en ese modelo
- Captura de decisiones de negocio de la conversación como algo distinto de una lección de
  dominio (ver decisión F) → backlog, gap conocido y declarado
- Rama "lección automática, positiva, sin pedido explícito" de `cerrar_sesion()` → cubierta por
  tests con mock, no por una corrida real todavía (ver decisión F, observación)
- Conductor conversacional en la web (más allá de las páginas de solo lectura de Etapa 6) → ✅ hecho
