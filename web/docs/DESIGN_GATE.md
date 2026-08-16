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
| `GET /casos/{id}` | Detalle completo: identidad + frentes (con documentos y artefactos externos de cada uno) + pendientes | ✅ construido |
| `GET /documentos/{id}` | Contenido completo de un `documento_caso` puntual | ✅ construido |
| `POST /conductor/sesiones` | Crea una sesión de chat nueva (`session_id`), estado en memoria del proceso. | ✅ construido (v1.2, mismo día) |
| `POST /conductor/sesiones/{id}/mensajes` | Un turno de conversación — envuelve `conductor.enviar_mensaje()` tal cual, misma función que usa `run.py` (CLI). | ✅ construido (v1.2, mismo día) |

### Páginas — `web/app/`

| Página | Descripción | Estado |
|---|---|---|
| `/` | Lista de casos, tarjetas con nombre/estadío/descripción | ✅ construido |
| `/casos/[id]` | Detalle: frentes (con estado de documentos — "sin documentos producidos todavía" si no hay ninguno), pendientes (abiertos/resueltos visualmente distintos), artefactos externos | ✅ construido |
| `/documentos/[id]` | Contenido completo de un documento, **renderizado como markdown real** (`react-markdown` + `remark-gfm` + `@tailwindcss/typography`) — no como texto plano con `##`/`**` literales | ✅ construido |
| `/conductor` | Chat con el Conductor — único **client component** de la app (los otros 3 son Server Components, esta necesita estado de React porque es interactiva). | ✅ construido (v1.2, mismo día) |

Server Components (Next.js App Router) con `fetch()` directo a la API para las 3 páginas de
lectura — sin capa de estado cliente, no hace falta para páginas sin interacción. `/conductor`
es la excepción deliberada: necesita mantener el historial visible y el estado de "enviando", eso
exige un client component (`"use client"`).

### El chat del Conductor — sesiones en memoria, no un store persistente

`enviar_mensaje()` (`conductor/conductor.py`) muta y devuelve una lista `messages` que mezcla
dicts planos y objetos del SDK de Anthropic (bloques `ContentBlock` para turnos del asistente) —
no es serializable a JSON tal cual para que el cliente la sostenga entre requests HTTP (a
diferencia de `/casos`, que si es stateless). Solución: `_sesiones_conductor` (dict en memoria
del proceso de `api/main.py`, `session_id -> messages`) — el browser solo manda `session_id` +
texto, el estado real de la conversación (incluidos los bloques del SDK) nunca sale del proceso
Python. Suficiente para un solo usuario local (Sebas) — se pierde si se reinicia el server, límite
aceptado de v1, no un caso de uso real que lo necesite hoy.

**Import fix real, no cosmético:** `api/main.py` importaba `from conductor.conductor import
enviar_mensaje` (calificado por paquete) — eso cachea el PAQUETE `conductor/__init__.py` (vacío)
en `sys.modules["conductor"]`, lo que rompe `import conductor as cond` de
`conductor/tests/test_conductor.py` cuando ambas suites de tests corren en el mismo proceso
pytest (17 tests de `conductor/tests` fallaban solo en la regresión combinada, no corriendo cada
suite por separado). Corregido insertando `conductor/` al frente del `sys.path` de `api/main.py`
e importando bare (`from conductor import enviar_mensaje`) — mismo truco que ya usa
`conductor/run.py`.

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

---

## 4. Scope explícito por versión

| Feature | Versión | Razón |
|---|---|---|
| **Gasto de tokens visible en la web** | v1.1, explícitamente anotado desde el arranque de la sesión (no se pierde como ítem) | El dato ya existe (`utils/token_tracker.py`, `props.token_usage`) — falta solo superficie en `/casos/[id]` o una vista `/equipo`. No entra en el alcance v1 confirmado por Sebas. |
| Chat con el Conductor vía web | ✅ hecho (v1.2 adelantada, mismo día) | Sebas: "no le encuentro mucha utilidad a lo que hay ahora" al ver solo las páginas de lectura — v1.2 se adelantó en la misma sesión en vez de quedar pendiente. |
| Chat con cada especialista por separado (no solo con el Conductor) | v2, si hace falta | Hoy la única superficie conversacional es el Conductor — invocar un especialista puntual sigue siendo indirecto (pedírselo al Conductor), no un chat propio por especialista. |
| Entrada por voz, modo documento coautoría, extracción de datos estructurados, vincular artefactos nuevos, dashboard | v2+ | `PROPUESTA_DESTINO.md` §7 los confirma como parte de la visión completa, pero son ideas para sumar al alcance, no lo mínimo de esta etapa. |
| Autenticación / login real | No planeado todavía | `usuarios.yaml` — decisión ya tomada, sin login real por ahora, un solo usuario (Sebas). |

---

## 5. Decisiones requeridas antes de arrancar

| # | Pregunta | Opciones | Decisión tomada | Fecha |
|---|---|---|---|---|
| A | ¿Cómo accede Next.js a los datos del KM? | API Python delgada (FastAPI) / Next.js conecta directo a Postgres (cliente TS) | **API Python delgada.** Reusa `knowledge_module`/`utils/casos.py` sin duplicar lógica de queries en TypeScript — el costo (un proceso más en dev) se acepta a cambio de no arriesgar que la lógica diverja entre dos lenguajes. | 2026-08-16 |
| B | ¿La API lee de producción o de staging? | Producción / Staging | **Producción** — es estrictamente de solo lectura, sin ningún riesgo de escritura que staging deba absorber (a diferencia de la Etapa 4). | 2026-08-16 |
| C | ¿Cómo se renderiza el contenido de un `documento_caso` (es markdown)? | Texto plano (`whitespace-pre-wrap`) / Markdown real | **Markdown real** (`react-markdown`+`remark-gfm`+`@tailwindcss/typography`) — encontrado al verificar en navegador que el texto plano mostraba `##`/`**` literales, ilegible para el caso de uso central de esta etapa ("ver los documentos que se generen", `PROPUESTA_DESTINO.md` §7). | 2026-08-16 |
| D | ¿Cómo mantiene el chat del Conductor memoria conversacional entre requests HTTP (stateless por naturaleza)? | Cliente sostiene el historial serializado / Sesión en memoria del server | **Sesión en memoria del server** (`_sesiones_conductor`, dict `session_id -> messages`) — `messages` mezcla dicts planos y objetos del SDK de Anthropic no serializables a JSON, hacer que el cliente los sostenga hubiera exigido convertir y reconstruir bloques del SDK en cada ida y vuelta. Válido porque es un solo usuario local — no es la respuesta correcta si esto se vuelve multi-usuario. | 2026-08-16 |

---

## 6. Estado del gate

**Estado actual:** ✅ LISTO

Decisiones A-D cerradas, ninguna abierta.

**Deuda intencional documentada:**
- Gasto de tokens visible en la web → v1.1, anotado explícitamente para no perderse
- Chat con cada especialista por separado (no solo el Conductor) → v2, si hace falta
- Entrada por voz, modo documento, extracción de datos, dashboard → v2+
- Login real → no planeado todavía
- Sesiones del Conductor en memoria (se pierden al reiniciar el server, no sirven para
  multi-usuario) → aceptado para v1, un solo usuario local
