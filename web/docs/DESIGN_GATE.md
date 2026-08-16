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
| ¿Qué es? | El scaffold real de la app confirmada en `docs/PROPUESTA_DESTINO.md` §7 — Next.js 15 (App Router, TS, Tailwind) + una API de solo lectura en FastAPI. Alcance v1 de esta etapa (Etapa 6 del plan): páginas de solo lectura — lista de casos, detalle de un caso, ver un documento. |
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

### Entidades — `api/main.py` (3 endpoints)

| Endpoint | Descripción | Estado |
|---|---|---|
| `GET /casos` | Lista de casos (id, nombre, descripción, estadío) — `utils/casos.py::listar_casos` | ✅ construido |
| `GET /casos/{id}` | Detalle completo: identidad + frentes (con documentos y artefactos externos de cada uno) + pendientes | ✅ construido |
| `GET /documentos/{id}` | Contenido completo de un `documento_caso` puntual | ✅ construido |

### Páginas — `web/app/`

| Página | Descripción | Estado |
|---|---|---|
| `/` | Lista de casos, tarjetas con nombre/estadío/descripción | ✅ construido |
| `/casos/[id]` | Detalle: frentes (con estado de documentos — "sin documentos producidos todavía" si no hay ninguno), pendientes (abiertos/resueltos visualmente distintos), artefactos externos | ✅ construido |
| `/documentos/[id]` | Contenido completo de un documento, **renderizado como markdown real** (`react-markdown` + `remark-gfm` + `@tailwindcss/typography`) — no como texto plano con `##`/`**` literales | ✅ construido |

Server Components (Next.js App Router) con `fetch()` directo a la API — sin capa de estado
cliente (Redux/Zustand/etc.), no hace falta para páginas de solo lectura sin interacción.

### KM write — ninguna

Este módulo no escribe nada al KM — es estrictamente de lectura, por diseño. No aplica tabla de
KM write.

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

---

## 4. Scope explícito por versión

| Feature | Versión | Razón |
|---|---|---|
| **Gasto de tokens visible en la web** | v1.1, explícitamente anotado desde el arranque de la sesión (no se pierde como ítem) | El dato ya existe (`utils/token_tracker.py`, `props.token_usage`) — falta solo superficie en `/casos/[id]` o una vista `/equipo`. No entra en el alcance v1 confirmado por Sebas. |
| Chat con cada agente (`PROPUESTA_DESTINO.md` §7, alcance v1 confirmado) | v1.2 | Etapa 6 se acotó a solo-lectura primero, per el plan ("páginas de solo-lectura primero, después modo chat/documento") — el Conductor (Etapa 5) ya es conversacional por CLI, falta la superficie web. |
| Entrada por voz, modo documento coautoría, extracción de datos estructurados, vincular artefactos nuevos, dashboard | v2+ | `PROPUESTA_DESTINO.md` §7 los confirma como parte de la visión completa, pero son ideas para sumar al alcance, no lo mínimo de esta etapa. |
| Autenticación / login real | No planeado todavía | `usuarios.yaml` — decisión ya tomada, sin login real por ahora, un solo usuario (Sebas). |

---

## 5. Decisiones requeridas antes de arrancar

| # | Pregunta | Opciones | Decisión tomada | Fecha |
|---|---|---|---|---|
| A | ¿Cómo accede Next.js a los datos del KM? | API Python delgada (FastAPI) / Next.js conecta directo a Postgres (cliente TS) | **API Python delgada.** Reusa `knowledge_module`/`utils/casos.py` sin duplicar lógica de queries en TypeScript — el costo (un proceso más en dev) se acepta a cambio de no arriesgar que la lógica diverja entre dos lenguajes. | 2026-08-16 |
| B | ¿La API lee de producción o de staging? | Producción / Staging | **Producción** — es estrictamente de solo lectura, sin ningún riesgo de escritura que staging deba absorber (a diferencia de la Etapa 4). | 2026-08-16 |
| C | ¿Cómo se renderiza el contenido de un `documento_caso` (es markdown)? | Texto plano (`whitespace-pre-wrap`) / Markdown real | **Markdown real** (`react-markdown`+`remark-gfm`+`@tailwindcss/typography`) — encontrado al verificar en navegador que el texto plano mostraba `##`/`**` literales, ilegible para el caso de uso central de esta etapa ("ver los documentos que se generen", `PROPUESTA_DESTINO.md` §7). | 2026-08-16 |

---

## 6. Estado del gate

**Estado actual:** ✅ LISTO

Decisiones A-C cerradas, ninguna abierta.

**Deuda intencional documentada:**
- Gasto de tokens visible en la web → v1.1, anotado explícitamente para no perderse
- Chat con cada agente vía web → v1.2
- Entrada por voz, modo documento, extracción de datos, dashboard → v2+
- Login real → no planeado todavía
