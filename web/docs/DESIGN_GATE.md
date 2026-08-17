# Design Gate — App web (api/ + web/)

**Versión:** 1.0
**Fecha:** 2026-08-16
**Módulo:** `criza/api/` (backend) + `criza/web/` (frontend) — un solo Design Gate para los dos,
se entregan juntos, uno no tiene sentido sin el otro.
**Capa:** 2 (instancia CRIZA)
**Estado:** ✅ LISTO

---

## 1. Identidad

| Pregunta | Respuesta |
|---|---|
| ¿Qué es? | El scaffold real de la app confirmada en `docs/PROPUESTA_DESTINO.md` §7 — Next.js 15 (App Router, TS, Tailwind) + una API en FastAPI. Alcance v1 (Etapa 6): páginas de solo lectura — lista de casos, detalle de un caso, ver un documento. **v1.2 adelantada el mismo día** (Sebas: "no le encuentro mucha utilidad a lo que hay ahora" tras ver solo las páginas de lectura) — chat del Conductor en `/conductor`. |
| ¿Qué problema resuelve en una oración? | Que Sebas pueda ver el estado real de un caso y los documentos que los especialistas ya produjeron sin tener que leer el KM a mano o pedirle al Conductor. |
| ¿Quién lo usa? | Sebas — sin login (`config/plantillas/usuarios.yaml`, decisión ya tomada: sin login real por ahora, un solo usuario). |
| ¿De qué depende? | `api/` depende de `knowledge_module`/`utils/casos.py` (mismas funciones que ya usan `microbiologo_agent`/`conductor` — cero lógica de queries nueva). `web/` depende solo de `api/` vía HTTP — no toca Postgres directo. |
| ¿Qué depende de él? | Nadie todavía — es la superficie final para Sebas, no una pieza que otro componente consuma. |
| ¿Milestone? | Etapa 6 del plan de construcción del nuevo sistema de agentes (`docs/progress/2026-08-16.md`). |

---

## 2. Trazabilidad diseño → implementación

### Decisión de arquitectura: API Python delgada, no Next.js conectado directo a Postgres

Pregunta explícita a Sebas antes de escribir código (fork real, no decidido en ningún documento
previo): ¿Next.js habla directo con Neon (cliente TS) o pasa por una API Python? **Elegido: API
Python delgada (FastAPI)** — reusa `knowledge_module`/`utils/casos.py` tal cual (mismo
`tenant_id` scoping, mismas funciones que ya usan `microbiologo_agent`/`conductor`, cero SQL
duplicado en TypeScript). Costo: un proceso más para correr en dev (`api/run.py` puerto 8000 +
`web/` puerto 3000) — aceptado a cambio de no arriesgar que la lógica de acceso a datos diverja
entre dos lenguajes.

**No es una extensión de `plataforma/control_panel/`** (FastAPI+Jinja2, panel de auditoría
interno) — `docs/PROPUESTA_DESTINO.md` §7 ya lo descartó explícitamente. `api/` es un servicio
nuevo, propio de CRIZA, solo GET.

### Por qué lee de producción y no de staging

A diferencia de la Etapa 4 (agentes escribiendo contra `casos.yaml`, con riesgo real sobre datos
de casos reales), `api/` es **estrictamente de solo lectura** — no hay ningún riesgo de escritura
que staging tenga que absorber. Lee `DATABASE_URL` (producción) directo, mismo patrón que
cualquier corrida de verificación de esta sesión contra el KM real.

### Entidades — `api/main.py` (5 endpoints)

| Endpoint | Descripción | Estado |
|---|---|---|
| `GET /casos` | Lista de casos (id, nombre, descripción, estadío) — `utils/casos.py::listar_casos` | ✅ construido |
| `POST /casos` | Crea un caso nuevo (Etapa 13, 2026-08-17) — `nombre`/`descripcion` obligatorios (400 si faltan), el resto opcional. Escribe directo a producción, sin staging intermedio (mismo criterio que `/conductor/*` y `/especialistas/*` — Sebas es dueño de qué se crea). | ✅ construido (Etapa 13, 2026-08-17) |
| `GET /casos/{id}` | Detalle completo: identidad + frentes (con documentos y artefactos externos de cada uno) + pendientes | ✅ construido |
| `GET /documentos/{id}` | Contenido completo de un `documento_caso` puntual | ✅ construido |
| `GET /documentos/{id}/descargar` | Descarga el contenido como archivo `.md` (Etapa 14, 2026-08-17) — `Content-Disposition: attachment`, nombre de archivo derivado del título. | ✅ construido (Etapa 14, 2026-08-17) |
| `POST /conductor/sesiones` | Crea una sesión de chat nueva — la ficha creada en el KM (área `conductor_sesiones`) *es* el `session_id`, no hay un id separado que mantener sincronizado. | ✅ construido (v1.2, mismo día; persistencia al KM sumada el mismo día tras la pregunta de Sebas) |
| `POST /conductor/sesiones/{id}/mensajes` | Un turno de conversación — envuelve `conductor.enviar_mensaje()` tal cual, misma función que usa `run.py` (CLI). | ✅ construido (v1.2, mismo día) |
| `POST /conductor/sesiones/{id}/cerrar` | Evalúa si la sesión dejó una lección de dominio nueva y, si sí, la guarda al KM (`conductor.cerrar_sesion()`, Etapa 9). Llamado por el botón "Nueva conversación" (awaited) y por `beforeunload` vía `navigator.sendBeacon` (best-effort, sin esperar respuesta). | ✅ construido (Etapa 9, 2026-08-16) |
| `POST /especialistas/{nombre}/sesiones` | Crea una sesión de chat directo con un especialista (`microbiologo`/`ingeniero_ambiental`/`agronomo`). Con `frente_id`: arma el primer mensaje con `<especialista>.iniciar_sesion()` (mismo contexto que una corrida formal), 404 si el frente no existe. Sin `frente_id` (Etapa 12, "consulta libre"): sesión arranca vacía, sin ese contexto que armar. 404 si el nombre no es un especialista válido. | ✅ construido (Etapa 10 + Etapa 12, 2026-08-16) |
| `POST /especialistas/sesiones/{id}/mensajes` | Un turno de chat — envuelve `<especialista>.enviar_mensaje()`, que usa `TOOLS_CHAT` (todas las tools del especialista MENOS `submit_evaluacion_tecnica`, a propósito: el chat no produce un documento persistido). | ✅ construido (Etapa 10, 2026-08-16) |
| `GET /agentes/{nombre}` | Características de un agente (`conductor`/`microbiologo`/`ingeniero_ambiental`/`agronomo`) — `SYSTEM_PROMPT` y `TOOLS` leídos EN VIVO del módulo del agente (no una copia), con `disponible_en_chat` marcando qué tools son exclusivas de la corrida formal (`submit_evaluacion_tecnica`). | ✅ construido (Etapa 11, 2026-08-16) |
| `GET /modelos` | Lista curada de modelos elegibles por sesión de chat (Etapa 15, 2026-08-17) — `utils/ai_client.py::MODELOS_DISPONIBLES`, única fuente (no la duplica). `POST /conductor/sesiones` y `POST /especialistas/{nombre}/sesiones` aceptan un campo opcional `modelo` en el body — se persiste en la ficha de sesión (`campos.modelo`) y se pasa como `model=` a `enviar_mensaje()` en cada turno subsiguiente; `null`/ausente = default del agente (env var propia). | ✅ construido (Etapa 15, 2026-08-17) |
| `GET /conductor/sesiones` | Historial de conversaciones con el Conductor (Etapa 16, 2026-08-17) — lista todas las sesiones con al menos un turno visible (excluye las abandonadas antes del primer mensaje), con preview del primer mensaje, fecha y modelo. Reconstruye los turnos visibles desde los `mensajes` crudos guardados vía `_mensajes_a_turnos()` (filtra pasos intermedios de tool-use/tool-result). | ✅ construido (Etapa 16, 2026-08-17) |
| `GET /conductor/sesiones/{id}` | Detalle completo de una sesión — `modelo` + `turnos` reconstruidos, para hidratar el chat al volver a una conversación anterior. | ✅ construido (Etapa 16, 2026-08-17) |
| `GET /especialistas/sesiones?especialista={nombre}` | Historial de conversaciones con un especialista puntual (Etapa 16) — mismo criterio que la versión del Conductor, incluye `frente_id` de cada sesión (`null` = consulta libre). | ✅ construido (Etapa 16, 2026-08-17) |
| `GET /especialistas/sesiones/{id}` | Detalle completo de una sesión de especialista — `especialista`/`frente_id`/`modelo`/`turnos`. | ✅ construido (Etapa 16, 2026-08-17) |

### Páginas — `web/app/`

| Página | Descripción | Estado |
|---|---|---|
| `/` | Lista de casos, tarjetas con nombre/estadío/descripción. Link "+ Nuevo caso" (Etapa 13). | ✅ construido |
| `/casos/nuevo` | Formulario de alta de caso (Etapa 13, 2026-08-17) — client component, nombre/descripción obligatorios, estadío/notas opcionales. Redirige a `/casos/{id}` al crear. | ✅ construido (Etapa 13, 2026-08-17) |
| `/casos/[id]` | Detalle: frentes (con estado de documentos — "sin documentos producidos todavía" si no hay ninguno), pendientes (abiertos/resueltos visualmente distintos), artefactos externos | ✅ construido |
| `/documentos/[id]` | Contenido completo de un documento, **renderizado como markdown real** (`react-markdown` + `remark-gfm` + `@tailwindcss/typography`) — no como texto plano con `##`/`**` literales | ✅ construido |
| `/conductor` | Chat con el Conductor — único **client component** de la app (los otros 3 son Server Components, esta necesita estado de React porque es interactiva). Botón "Nueva conversación" (Etapa 9): cierra la sesión actual (evalúa lección, muestra un aviso en el chat si guardó una) y crea una sesión nueva vacía. Selector de modelo (Etapa 15) junto al botón. Botón "🕘 Historial" (Etapa 16) — ver Decisión L abajo: lista las conversaciones pasadas y permite reabrir cualquiera; la sesión activa se recuerda entre cargas de página vía `localStorage`. | ✅ construido (v1.2 + Etapa 9 + Etapa 15 + Etapa 16, 2026-08-16/17) |
| `/especialistas/[nombre]` | Chat directo con un especialista puntual (Etapa 10) — toma `frente` como query param (`?frente=<id>`). **Sin `frente` (Etapa 12): "consulta libre"**, sin caso, más barata en tokens — la página lo indica explícitamente y sugiere entrar desde un caso si la pregunta termina siendo sobre uno real. Links "💬 &lt;Especialista&gt;" agregados por frente en `/casos/[id]`. Aviso explícito: esto NO produce un documento persistido (a diferencia de pedirle al Conductor que corra al especialista). Selector de modelo (Etapa 15) y "🕘 Historial" (Etapa 16) junto a "ℹ️ Características" — misma sesión activa recordada por `localStorage`, con clave por `(especialista, frente)`. | ✅ construido (Etapa 10 + Etapa 12 + Etapa 15 + Etapa 16, 2026-08-16/17) |
| `/especialistas` | Listado de los 3 especialistas — link a "💬 Consulta libre" (Etapa 12) y "ℹ️ Características" por cada uno. Agregado al nav global (antes solo se llegaba a un especialista desde dentro de un caso — Sebas: "no se ven los otros agentes"). | ✅ construido (Etapa 12, 2026-08-16) |
| `/agentes/[nombre]` | Panel de características de un agente (Etapa 11) — herramientas (con descripción y si están disponibles en chat o solo en la corrida formal) + el `SYSTEM_PROMPT` completo. Server Component de solo lectura, sin interacción. Link "ℹ️ Características" en `/conductor` y en `/especialistas/[nombre]`, abre en pestaña nueva (`target="_blank"` — Sebas pidió "puede ser con un acceso a otra ventana"). | ✅ construido (Etapa 11, 2026-08-16) |

Server Components (Next.js App Router) con `fetch()` directo a la API para las 3 páginas de
lectura — sin capa de estado cliente, no hace falta para páginas sin interacción. `/conductor`
es la excepción deliberada: necesita mantener el historial visible y el estado de "enviando", eso
exige un client component (`"use client"`).

### El chat del Conductor — sesiones persistidas en el KM (no en memoria)

`enviar_mensaje()` (`conductor/conductor.py`) muta y devuelve una lista `messages` que mezcla
dicts planos y objetos del SDK de Anthropic (bloques `ContentBlock` para turnos del asistente) —
no es serializable a JSON tal cual para que el cliente la sostenga entre requests HTTP (a
diferencia de `/casos`, que sí es stateless). Primera versión (mismo día, antes de esto):
`_sesiones_conductor`, un dict en memoria del proceso de `api/main.py` — se perdía al reiniciar
`api/run.py`. Sebas preguntó explícitamente por qué (esperaba, con razón, que el chat se
comportara como todo lo demás en el proyecto: "si el output de un agente no está en el KM, no
existe para el sistema", CLAUDE.md).

**Solución (mismo día, después):** área nueva `conductor_sesiones` en el KM
(`config/plantillas/conductor_sesiones.yaml`), una ficha por sesión completa. `POST
/conductor/sesiones` crea la ficha (`motor_api.guardar_ficha`) y devuelve su id como
`session_id` — no hay traducción entre "id que ve el browser" e "id de la ficha", son el mismo.
Cada turno (`POST /conductor/sesiones/{id}/mensajes`) lee `props.mensajes` (`motor_api.obtener`),
se lo pasa tal cual a `enviar_mensaje()`, y reescribe `props.mensajes` con el historial actualizado
(`motor_api.actualizar_props`) — serializado con `conductor.py::serializar_mensajes` (convierte
`ContentBlock` a dict plano vía `dataclasses.asdict`; no hace falta una función inversa porque
`utils/ai_client.py::_mensajes_a_formato_openai` ya acepta indistintamente `ContentBlock` o dict
plano al armar la siguiente llamada al modelo). El browser solo manda `session_id` + texto, igual
que antes — lo único que cambió es dónde vive el estado entre requests.

Verificado con una corrida real, no solo con los tests: sesión creada, primer mensaje respondido,
proceso de `api/run.py` matado con `taskkill /F` (no un shutdown limpio), proceso nuevo levantado,
segundo mensaje a la misma sesión — recordó correctamente el primero. Leyendo la ficha directo del
KM después: 6 mensajes (incluido el tool-use de `listar_casos`), serializados y recuperados bien.

**Import fix real, no cosmético:** `api/main.py` importaba `from conductor.conductor import
enviar_mensaje` (calificado por paquete) — eso cachea el PAQUETE `conductor/__init__.py` (vacío)
en `sys.modules["conductor"]`, lo que rompe `import conductor as cond` de
`conductor/tests/test_conductor.py` cuando ambas suites de tests corren en el mismo proceso
pytest (17 tests de `conductor/tests` fallaban solo en la regresión combinada, no corriendo cada
suite por separado). Corregido insertando `conductor/` al frente del `sys.path` de `api/main.py`
e importando bare (`from conductor import enviar_mensaje`) — mismo truco que ya usa
`conductor/run.py`.

### Decisión K — elegir modelo por sesión de chat (Etapa 15, 2026-08-17)

Pedido de Sebas: poder elegir qué modelo de IA usa una conversación desde la web, sin reiniciar
el server con otra env var. Decisiones tomadas antes de codear:

- **Granularidad: por sesión de chat, no global ni por agente.** Las sesiones ya son la unidad
  natural del sistema (cada una es su propia ficha KM) — no hizo falta un mecanismo de
  persistencia nuevo, solo sumar un campo (`modelo`) a las plantillas que ya existían
  (`conductor_sesiones.yaml`, `especialista_sesiones.yaml`) y pasarlo como `model=` al
  `enviar_mensaje()` de cada agente, que ya aceptaba ese kwarg (`utils/ai_client.py`,
  PROPUESTA_DESTINO.md §8, 2026-08-15).
- **Lista curada, no texto libre.** Hoy solo hay `ANTHROPIC_API_KEY` configurada (verificado en
  `.env`) — aunque `resolver_modelo()` acepta cualquier `"<proveedor>/<modelo>"` de LiteLLM,
  ofrecer proveedores sin credenciales rompería al elegirlos. `utils/ai_client.py::
  MODELOS_DISPONIBLES` es la única fuente (4 modelos Anthropic); `GET /modelos` la expone tal
  cual, la UI la lee de ahí.
- **El modelo queda fijado al crear la sesión, no se puede cambiar a mitad de conversación** — el
  selector (`<select>` en `/conductor` y `/especialistas/[nombre]`) se deshabilita en cuanto hay
  al menos un turno; cambiarlo antes del primer mensaje recrea la sesión con el nuevo modelo
  (mismo patrón que "Nueva conversación").

**Verificación real (no solo tests):** desde el browser, elegido "Haiku 4.5" en `/conductor`,
mandado un mensaje real, confirmado leyendo la ficha del KM (`conductor_sesiones`) que
`props.modelo == "claude-haiku-4-5-20251001"` y que el turno se registró. Repetido en
`/especialistas/microbiologo` con "Opus 5" — misma confirmación contra `especialista_sesiones`.

### Decisión L — historial de conversaciones + recordar la sesión activa (Etapa 16, 2026-08-17)

**Bug real reportado por Sebas:** le hizo una pregunta al Conductor sobre composición química
del efluente de Helios, recibió una respuesta sustancial (varios vectores blue ocean), volvió más
tarde a `/conductor` y la respuesta "se había borrado" — tokens gastados, información
aparentemente perdida.

**Causa raíz, confirmada antes de tocar código:** `/conductor` (y `/especialistas/[nombre]`)
creaban una sesión nueva en **cada carga de página** (`useEffect` al montar) y nunca guardaban el
`session_id` en ningún lado del browser — ni `localStorage` ni la URL. La conversación anterior
seguía **intacta en el KM** (verificado leyendo la ficha directo: la respuesta completa del
Conductor, con los 5 vectores blue ocean, estaba ahí), pero la web no tenía forma de volver a
encontrarla. No era una pérdida de datos — era una pérdida de acceso.

**Fix, dos piezas (ambas pedidas explícitamente por Sebas al elegir entre 3 opciones):**
1. **Recordar la sesión activa** — `localStorage` guarda el `session_id` de la conversación en
   curso (clave `criza_conductor_session_id` para el Conductor; `criza_especialista_session_
   {nombre}_{frente_id ?? "libre"}` por especialista, para no mezclar una consulta libre con una
   conversación sobre un frente puntual). Al montar la página, si hay un id guardado, se hidrata
   el chat desde el KM (`GET /conductor|especialistas/sesiones/{id}`) en vez de crear una sesión
   nueva. Cubre el caso más común (recargar la misma página, cerrar y volver a abrir la pestaña).
2. **Historial completo** — botón "🕘 Historial" en ambas páginas, lista las conversaciones
   pasadas (`GET /conductor/sesiones` y `GET /especialistas/sesiones?especialista={nombre}`) con
   preview del primer mensaje y fecha, click para reabrir cualquiera. Cubre lo que `localStorage`
   no puede (otro navegador, otro dispositivo, `localStorage` borrado) — la fuente de verdad
   siempre es el KM, `localStorage` es solo una conveniencia de "última sesión activa".

**Cómo se reconstruyen los turnos visibles:** los `mensajes` guardados incluyen los pasos
intermedios de tool-use/tool-result que nunca se le mostraron a Sebas en pantalla —
`_mensajes_a_turnos()` (`api/main.py`) los filtra: un mensaje `user` con `content` string es un
turno real (lo que arma cada `enviar_mensaje()`); un mensaje `assistant` es la respuesta final del
turno solo si ningún bloque es `tool_use`. No hizo falta un campo nuevo en el KM para esto — la
misma fuente que ya se guardaba alcanza.

**Se excluyen del historial las sesiones sin ningún turno visible** (creadas por una carga de
página que nunca llegó a mandar un mensaje — había 48 así en el KM al momento de este fix, la
mayoría de pruebas y recargas) — listarlas sería ruido, no ayuda a encontrar nada.

**Verificación real (no solo tests):** se recuperó la conversación exacta que Sebas reportó como
perdida (`d195cb96-9fde-4ca0-95b9-da96352e8fac`, 17/08 ~13:41) leyendo el KM directo — seguía
intacta. Con la sesión guardada en `localStorage`, recargar `/conductor` la hidrató completa (el
mismo texto, los 5 vectores blue ocean, la recomendación final). El panel de Historial listó las
8 conversaciones reales con contenido, en orden correcto por fecha; reabrir una distinta cambió el
chat visible y actualizó `localStorage` a la nueva sesión. Repetido en `/especialistas/microbiologo`:
el historial mostró 7 sesiones reales con la etiqueta correcta ("Consulta libre" / "Sobre un
frente").

### KM write — vía el Conductor, no la API en sí

Los 3 endpoints de lectura no escriben nada. `/conductor/sesiones/{id}/mensajes` **sí puede
escribir** — si el Conductor invoca `correr_especialista`, eso pasa por la costura
(`invocar_agente`) igual que cualquier otra invocación, y escribe un `documento_caso` real. Usa
la misma `DATABASE_URL` que el resto del proceso (producción por default) — Sebas es dueño de
decidir qué corridas promueve, igual que con cualquier otro cliente de la costura.

---

## 3. Checklist del playbook

### Seguridad Nivel 1

- [x] Sin credenciales en el frontend — `api/.env` (backend) es lo único con `DATABASE_URL`, el
      frontend solo conoce la URL pública de la API (`NEXT_PUBLIC_API_URL`)
- [x] `.env*` de `web/` gitignored (default de `create-next-app`)
- [x] `api/.env.example` completo

### Estructura de archivos

- [x] `api/main.py` + `api/run.py` + `api/docs/` (este archivo, compartido) + `api/tests/`
- [x] `web/app/` (páginas) + `web/lib/api.ts` (cliente HTTP) + `web/docs/` (este archivo)

### Testing

- [x] Test: `GET /casos` devuelve la lista formateada
- [x] Test: `GET /casos/{id}` inexistente → 404
- [x] Test: `GET /casos/{id}` arma el detalle completo (frentes + documentos + pendientes)
- [x] Test: `GET /documentos/{id}` inexistente o de otro tipo de ficha → 404 (no filtra datos de
      otro tipo de ficha por error)
- [x] Test: CORS permite `localhost:3000`
- [x] Al menos 1 integration test real contra el KM (`httpx.AsyncClient` — el `TestClient`
      síncrono rompe con "Event loop is closed" al hacer 2+ requests seguidas contra el engine
      async de `knowledge_module`, que cachea un pool atado al loop de la primera request)
- [x] Verificación manual en navegador (Playwright/Claude Browser): lista de casos con datos
      reales, detalle de Helios con frentes/pendientes reales, `npm run build` sin errores de
      tipos
- [x] Test: `POST /conductor/sesiones` crea una sesión nueva
- [x] Test: mandar un mensaje a una sesión inexistente → 404
- [x] Test: mensaje vacío → 400
- [x] Test: el segundo turno de la misma sesión opera sobre los `messages` acumulados del primero
      (memoria conversacional real, no solo un mock que "pasa")
- [x] Verificación manual en navegador, conversación real de 2 turnos: "¿Qué casos tenemos
      activos?" (listó los 2 casos reales) → "Contame cómo viene Helios" (reportó correctamente
      los 3 documentos reales recién promovidos a producción, sintetizó que el frente de
      asociación está vacío y que los 2 pendientes de negocio son el cuello de botella real)
- [x] Test: `POST /conductor/sesiones/{id}/cerrar` de una sesión inexistente → 404; con/sin
      lección guardada devuelve `leccion_guardada` correcto (Etapa 9)
- [x] Verificación real contra el servidor corriendo (no solo tests): sesión real con 2 mensajes
      sobre Helios, `POST .../cerrar` — la lección explícita (`anotar_leccion`, pedida en el chat)
      quedó guardada con `fuente="humano"` en 3 corridas reales distintas; el cierre automático
      dijo correctamente "no hay lección nueva" sobre una conversación de solo-lectura y
      reconoció como "ya cubierta" una lección que el trigger explícito ya había guardado en la
      misma sesión (anti-duplicación funcionando)
- [ ] Verificación visual del botón "Nueva conversación" en el navegador — bloqueada esta sesión:
      el Browser pane no compositó frames (`screenshot` falló explícitamente por eso), así que los
      clicks del tool no llegaban de forma confiable al DOM aunque el código sí es correcto
      (confirmado inspeccionando el input por JS: el estado de React se actualiza bien). Pendiente
      de una verificación visual real en una sesión donde el pane sí componga.
- [x] Test (Etapa 10): `POST /especialistas/{nombre}/sesiones` con nombre inválido → 404; con
      frente inexistente → 404; crea la ficha con `especialista`/`frente_id` correctos
- [x] Test: `POST /especialistas/sesiones/{id}/mensajes` de sesión inexistente → 404; vacío → 400;
      devuelve la respuesta del especialista correcto según `props.especialista` de la sesión
- [x] Verificación real contra el servidor corriendo: sesión de chat real con el Microbiólogo
      sobre el 'Frente técnico' real de Helios, pregunta puntual → respuesta sustancial y bien
      fundamentada (evaluación técnica completa con fuentes reales de `buscar_corpus_cientifico`)
      sin invocar `submit_evaluacion_tecnica` — confirmado leyendo el KM después que NO se creó
      un 4to `documento_caso` sobre ese frente (seguían siendo exactamente los 3 de las corridas
      formales anteriores) — la separación chat/persistencia formal funciona como se diseñó
- [x] `npm run build` sin errores de tipos con las páginas y rutas nuevas
- [x] Página `/especialistas/[nombre]` carga correctamente con un `frente` real (confirmado con
      `get_page_text` — título del especialista, sesión creada, sin errores de consola nuevos) y
      los links "💬 &lt;Especialista&gt;" aparecen en `/casos/[id]` por cada frente
- [x] Test (Etapa 11): `GET /agentes/{nombre}` con nombre inválido → 404; el Conductor devuelve
      todas sus tools con `disponible_en_chat=true`; un especialista marca
      `submit_evaluacion_tecnica` como `disponible_en_chat=false` y el resto como `true`
- [x] Verificación real contra el servidor corriendo: `GET /agentes/conductor` (5 tools reales,
      `SYSTEM_PROMPT` completo) y `GET /agentes/microbiologo` (9 tools reales, incluidas las 4
      bioquímicas — KEGG/Rhea/UniProt/BacDive — y `submit_evaluacion_tecnica` correctamente
      marcada como solo-corrida-formal)
- [x] Página `/agentes/[nombre]` verificada en el navegador con `get_page_text`: título correcto,
      las 9 tools del Microbiólogo con sus descripciones reales renderizadas
- [x] Test (Etapa 12): crear sesión sin `frente_id` no llama `iniciar_sesion` y persiste
      `frente_id: null`
- [x] Verificación real contra el servidor corriendo: sesión "consulta libre" con el
      Microbiólogo, sin ningún caso — pregunta puntual sobre metanogénesis respondida
      correctamente sin tocar `obtener_frente_con_caso`; confirmado leyendo el KM que la ficha
      quedó con `frente_id: None`
- [x] Página `/especialistas/[nombre]` sin `?frente=` verificada en el navegador: entra en modo
      libre automáticamente (sin error), muestra el aviso correcto
- [x] Página `/especialistas` (listado) y link "Especialistas" en el nav global verificados
- [x] Test (Etapa 13): `POST /casos` con nombre/descripción vacíos → 400; éxito devuelve
      `caso_id`; falla del KM → 500
- [x] Test: `utils/casos.py::crear_caso` computa `texto_busqueda` correctamente, propaga error
      del KM
- [x] Test: tool `crear_caso` del Conductor — nombre vacío → error, éxito, falla del KM, dispatch
- [x] Verificación real contra staging (no producción, por decisión explícita de Sebas): caso
      creado de verdad, leído de vuelta con los campos correctos, aparece en `listar_casos`
- [x] Verificación real contra el server de producción SIN escribir datos de prueba: página
      `/casos/nuevo` renderiza bien, botón deshabilitado sin datos completos; "+ Nuevo caso"
      aparece en `/`; una conversación real con el Conductor describiendo un caso nuevo pidió
      confirmación y no llamó `crear_caso` — confirmado leyendo `/casos` después que seguían
      siendo los mismos 2 casos reales, nada de prueba tocó producción
- [x] `npm run build` sin errores de tipos, ruta estática `/casos/nuevo` no colisiona con la
      dinámica `/casos/[id]`
- [x] Test (Etapa 14): `GET /documentos/{id}/descargar` — 200 con `Content-Disposition:
      attachment` y filename correcto; 404 si no existe o es de otro tipo; `_slug_archivo`
      normaliza acentos/símbolos y tiene fallback si el título viene vacío
- [x] Verificación real contra el server de producción: descarga completa de un informe real de
      Helios (105 líneas, contenido íntegro) — link verificado en `/documentos/[id]` y en la
      lista de documentos de `/casos/[id]`
- [x] Test (Etapa 15): `GET /modelos` devuelve la lista curada de 4; crear sesión con `modelo`
      lo persiste (Conductor y especialista); sin `modelo`, queda `None`; `enviar_mensaje_*` pasa
      `model=` al agente solo cuando `props.modelo` está seteado, si no lo omite (el agente usa su
      propio default)
- [x] `npm run build` sin errores de tipos con el selector nuevo en ambas páginas de chat
- [x] Verificación real contra el server de producción y KM real (no solo tests): en `/conductor`,
      elegido "Haiku 4.5", mandado un mensaje real ("Decime en una palabra qué sos" → "Conductor."),
      confirmado leyendo la ficha (`conductor_sesiones`) que `props.modelo ==
      "claude-haiku-4-5-20251001"` y que el turno quedó persistido. Repetido en
      `/especialistas/microbiologo` eligiendo "Opus 5" antes del primer mensaje — confirmado
      `props.modelo == "claude-opus-5"` en `especialista_sesiones`.
- [x] Test (Etapa 16): `_mensajes_a_turnos` filtra pasos intermedios de tool-use/tool-result y
      devuelve lista vacía sin mensajes; `GET /conductor/sesiones` excluye sesiones sin turnos y
      trunca el preview a 140 caracteres; `GET /conductor/sesiones/{id}` devuelve 404 si no
      existe; `GET /especialistas/sesiones` 404 si el nombre no es válido, incluye `frente_id`
      por sesión; `GET /especialistas/sesiones/{id}` devuelve `especialista`/`turnos` correctos
- [x] `npm run build` sin errores de tipos con el botón de historial y la hidratación por
      `localStorage` en ambas páginas de chat
- [x] Verificación real contra el server de producción y el KM real (no solo tests): se recuperó
      la conversación exacta que Sebas reportó como "perdida" leyendo el KM directo — seguía
      intacta. Con el `session_id` en `localStorage`, recargar `/conductor` la hidrató completa
      (mismo texto, mismos 5 vectores blue ocean). El panel de Historial listó las 8
      conversaciones reales del Conductor con contenido en orden correcto por fecha; reabrir una
      distinta actualizó el chat visible y `localStorage`. Repetido en
      `/especialistas/microbiologo`: 7 sesiones reales listadas con la etiqueta correcta
      ("Consulta libre" / "Sobre un frente")

---

## 4. Scope explícito por versión

| Feature | Versión | Razón |
|---|---|---|
| **Gasto de tokens visible en la web** | v1.1, explícitamente anotado desde el arranque de la sesión (no se pierde como ítem) | El dato ya existe (`utils/token_tracker.py`, `props.token_usage`) — falta solo superficie en `/casos/[id]` o una vista `/equipo`. No entra en el alcance v1 confirmado por Sebas. |
| Chat con el Conductor vía web | ✅ hecho (v1.2 adelantada, mismo día) | Sebas: "no le encuentro mucha utilidad a lo que hay ahora" al ver solo las páginas de lectura — v1.2 se adelantó en la misma sesión en vez de quedar pendiente. |
| Chat con cada especialista por separado (no solo con el Conductor) | ✅ hecho (Etapa 10, mismo día) | Pedido explícito de Sebas el mismo día que se resolvió la persistencia de sesiones. |
| Consulta libre a un especialista, sin caso | ✅ hecho (Etapa 12, mismo día) | Sebas: "me preocupa el consumo de tokens, tal vez necesito hacer una consulta simple antes de abrir un caso nuevo." |
| Crear casos nuevos desde la web/Conductor | ✅ hecho (Etapa 13, 2026-08-17) | Gap descubierto por Sebas el 16/08: hoy no existía NINGÚN camino para dar de alta un caso — resuelto con formulario (`/casos/nuevo`) + tool del Conductor, ambos sobre la misma función base (`utils/casos.py::crear_caso`). |
| Descargar informes como `.md` | ✅ hecho (Etapa 14, 2026-08-17) | Sebas: "algo que le agregaría también es la posibilidad de descargar los informes." `GET /documentos/{id}/descargar`, link `<a>` directo — el `Content-Disposition` del server dispara la descarga, sin JS del lado del cliente. |
| Elegir modelo de IA por sesión de chat | ✅ hecho (Etapa 15, 2026-08-17) | La abstracción de backend (`utils/ai_client.py`) ya existía; faltaba la superficie. Selector en `/conductor` y `/especialistas/[nombre]`, lista curada vía `GET /modelos` — ver Decisión K. |
| Historial de conversaciones + recordar sesión activa | ✅ hecho (Etapa 16, 2026-08-17) | Bug real: una respuesta del Conductor "se perdió" desde la perspectiva de Sebas — en realidad seguía intacta en el KM, solo inalcanzable desde la web. Ver Decisión L. |
| Entrada por voz, modo documento coautoría, extracción de datos estructurados, vincular artefactos nuevos, dashboard | v2+ | `PROPUESTA_DESTINO.md` §7 los confirma como parte de la visión completa, pero son ideas para sumar al alcance, no lo mínimo de esta etapa. |
| Autenticación / login real | No planeado todavía | `usuarios.yaml` — decisión ya tomada, sin login real por ahora, un solo usuario (Sebas). |

---

## 5. Decisiones requeridas antes de arrancar

| # | Pregunta | Opciones | Decisión tomada | Fecha |
|---|---|---|---|---|
| A | ¿Cómo accede Next.js a los datos del KM? | API Python delgada (FastAPI) / Next.js conecta directo a Postgres (cliente TS) | **API Python delgada.** Reusa `knowledge_module`/`utils/casos.py` sin duplicar lógica de queries en TypeScript — el costo (un proceso más en dev) se acepta a cambio de no arriesgar que la lógica diverja entre dos lenguajes. | 2026-08-16 |
| B | ¿La API lee de producción o de staging? | Producción / Staging | **Producción** — es estrictamente de solo lectura, sin ningún riesgo de escritura que staging deba absorber (a diferencia de la Etapa 4). | 2026-08-16 |
| C | ¿Cómo se renderiza el contenido de un `documento_caso` (es markdown)? | Texto plano (`whitespace-pre-wrap`) / Markdown real | **Markdown real** (`react-markdown`+`remark-gfm`+`@tailwindcss/typography`) — encontrado al verificar en navegador que el texto plano mostraba `##`/`**` literales, ilegible para el caso de uso central de esta etapa ("ver los documentos que se generen", `PROPUESTA_DESTINO.md` §7). | 2026-08-16 |
| D | ¿Cómo mantiene el chat del Conductor memoria conversacional entre requests HTTP (stateless por naturaleza)? | Cliente sostiene el historial serializado / Sesión en memoria del server / Sesión persistida en el KM | **Sesión en memoria del server** en la primera versión del mismo día (`_sesiones_conductor`, dict `session_id -> messages`) — luego **reemplazada, mismo día**, por sesión persistida en el KM (ver decisión E) al preguntar Sebas por qué se perdía al reiniciar el server. | 2026-08-16 |
| E | ¿Dónde persiste el historial de una sesión de chat para que sobreviva a un reinicio del server? | Archivo local (JSON en disco) / Área nueva en el KM | **Área nueva en el KM** (`conductor_sesiones`) — mismo mecanismo que ya usa todo lo demás del proyecto (`pipeline_status`, `token_usage`), no un archivo local que solo esta instancia vería. `session_id` que ve el browser es directamente el id de la ficha. | 2026-08-16 |
| F | Etapa 10 (2026-08-16) — `api/main.py` necesita las funciones `iniciar_sesion`/`enviar_mensaje` de los 3 especialistas (`microbiologo_agent`, `ingeniero_ambiental_agent`, `agronomo_agent`). ¿Bare import (`from microbiologo_agent import ...`, como `conductor/`) o package-qualificado (`from microbiologo_agent.microbiologo_agent import ...`, como usa `orquestador/registry.py::get_registry()`)? | Bare / package-qualificado / un tercer mecanismo | **Ninguno de los dos — carga por ruta de archivo bajo una clave propia de `sys.modules`** (`importlib.util.spec_from_file_location`, `_api_<nombre>`). Los 3 agentes tienen DOS consumidores reales incompatibles en el mismo proceso del server: `get_registry()` (package-qualificado, perezoso, para cuando el Conductor invoca al especialista) y el propio `conftest.py`/`run.py` de cada agente (bare) — cualquiera de los dos estilos que se usara acá rompía al otro apenas se ejecutaba, confirmado corriendo la regresión combinada y con pruebas reales aisladas. Cargar por ruta de archivo bajo una clave separada no colisiona con ninguno — además hace falta restaurar `sys.path` al estado previo después de cargar cada módulo, porque el archivo del agente inserta su propia carpeta al frente como efecto de lado (eso solo, sin tocar `sys.modules[nombre]`, ya alcanza para romper una resolución package-qualificada posterior si no se deshace). Verificado real: `get_registry()` sigue funcionando después de que `api/main.py` carga los 3 especialistas. | 2026-08-16 |
| G | Etapa 11 (2026-08-16) — Sebas pidió ver, por agente, qué puede hacer y a qué herramientas está conectado, "que se actualice cuando hay cambios de características o de herramientas". ¿Doc mantenido a mano / endpoint que lee `TOOLS`/`SYSTEM_PROMPT` en vivo de cada módulo? | Doc paralelo / lectura en vivo desde el código | **Lectura en vivo** (`GET /agentes/{nombre}`) — cada agente ya declara `TOOLS` (con `description` por tool, el mismo formato que ya consume el modelo para tool-calling) y `SYSTEM_PROMPT` como constantes de código; el endpoint las lee directo del objeto de módulo (los mismos `_mod_microbiologo`/etc. de la decisión F) — no hay copia que pueda desincronizarse, es literalmente la fuente que el agente usa para operar. `disponible_en_chat` se deriva comparando contra `TOOLS_CHAT` (Etapa 10) para marcar qué tools son exclusivas de la corrida formal. | 2026-08-16 |
| H | Etapa 12 (2026-08-16) — Sebas, mirando el chat: "¿no puedo hacerles preguntas que no sean en el marco de un caso? me preocupa el consumo de tokens." ¿`frente_id` sigue obligatorio para hablar con un especialista? | Obligatorio / Opcional ("consulta libre") | **Opcional.** `_CrearSesionEspecialistaIn.frente_id: str \| None = None` — sin él, `POST /especialistas/{nombre}/sesiones` no llama `iniciar_sesion` (nada de contexto de caso que armar), la ficha se crea con `frente_id: null`. `/especialistas/[nombre]` sin `?frente=` entra en este modo automáticamente, en vez de mostrar un error. Resultado: la consulta libre es MÁS barata en tokens que el modo con caso, no una alternativa degradada — resuelve la preocupación de Sebas directamente. En la misma conversación surgió un segundo gap real, distinto de este: no existe ningún camino (ni web ni Conductor) para dar de alta un caso nuevo — anotado como Etapa 13, deuda explícita, no resuelto hoy. | 2026-08-16 |
| I | Etapa 13 (2026-08-17) — ¿cómo se crea un caso: formulario web, Conductor conversacional, o los dos? | Formulario web / Conductor / Los dos | **Los dos**, elegido explícitamente por Sebas. `POST /casos` (`utils/casos.py::crear_caso`) es la base compartida — `/casos/nuevo` (formulario) y la tool `crear_caso` del Conductor (`conductor/docs/DESIGN_GATE.md` decisión G) llaman la misma función, sin duplicar lógica de creación. `nombre`/`descripcion` son los únicos campos obligatorios (son los que arman `texto_busqueda`, el campo vectorizado) — un caso puede crearse sin frentes (`casos.yaml` ya lo permite explícitamente). Verificado real contra staging (creación real, lectura de vuelta correcta, aparece en el listado) — la escritura contra producción vía el server real se verificó indirectamente: la ruta HTTP/validación por tests (mock), y el camino del Conductor con una conversación real que correctamente pidió confirmación sin llegar a escribir nada (decisión explícita de Sebas: no tocar producción con datos de prueba). | 2026-08-17 |
| J | Etapa 14 (2026-08-17) — Sebas pidió poder descargar los informes. ¿Formato? | Markdown (.md) / PDF / Word (.docx) | **Markdown**, elegido explícitamente por Sebas ("recomendado para arrancar" — el contenido ya está guardado en ese formato, sin conversión). Implementado como `GET /documentos/{id}/descargar` con `Content-Disposition: attachment` — un link `<a href>` directo, sin JS ni fetch del lado del cliente; el navegador dispara la descarga solo. `_slug_archivo()` arma el nombre de archivo desde el título (normaliza acentos/símbolos vía `unicodedata`, no depende de que el header HTTP maneje bien UTF-8 en el filename). Verificado real: descarga completa del informe real del Microbiólogo sobre Helios (105 líneas, contenido íntegro). | 2026-08-17 |
| K | Etapa 15 (2026-08-17) — ¿granularidad para elegir modelo de IA (por sesión de chat / por agente / global) y qué modelos ofrecer (lista curada / texto libre)? | Ver detalle en la sección "Decisión K" arriba | **Por sesión de chat, lista curada.** Sesiones ya son la unidad natural del sistema — no hizo falta persistencia nueva, solo un campo (`modelo`) en las plantillas ya existentes. Lista curada porque hoy solo hay `ANTHROPIC_API_KEY` configurada — texto libre ofrecería proveedores que romperían al elegirlos. | 2026-08-17 |
| L | Etapa 16 (2026-08-17) — bug real: una respuesta del Conductor "se perdió" al volver más tarde. ¿Cómo evitar que vuelva a pasar? | `localStorage` solo / historial completo solo / los dos | **Los dos**, elegido explícitamente por Sebas entre 3 opciones. `localStorage` (clave por página/especialista+frente) cubre el caso común (recargar, cerrar/abrir pestaña) sin ningún request extra al montar si ya hay sesión guardada. El historial (`GET /conductor/sesiones`, `GET /especialistas/sesiones?especialista=`) cubre lo que `localStorage` no puede (otro dispositivo/navegador, storage borrado) leyendo directo del KM, que siempre fue la fuente de verdad real — el bug nunca fue de datos, fue de que la web no sabía cómo volver a encontrarlos. | 2026-08-17 |

---

## 6. Estado del gate

**Estado actual:** ✅ LISTO

Decisiones A-L cerradas, ninguna abierta.

**Deuda intencional documentada:**
- Gasto de tokens visible en la web → v1.1, anotado explícitamente para no perderse
- Entrada por voz, modo documento, extracción de datos, dashboard → v2+
- Login real → no planeado todavía
- Historial *destilado* de una sesión de chat con un especialista puntual (a diferencia del
  Conductor, Etapa 9) → no pedido explícitamente, mismo backlog que las lecciones de caso
- Verificación visual completa (click-driven) del botón "Nueva conversación" y del flujo de chat
  con un especialista en el navegador → bloqueada esta sesión por el Browser pane sin compositar
  frames (ver progreso del 16/08) — verificado en cambio por API real (curl) + lectura directa del
  KM + carga de página confirmada (`get_page_text`)
