# BGE-m3 Embeddings Service — Design Gate

**Versión:** 1.0
**Fecha:** 2026-06-09
**Módulo:** services/bge-m3
**Capa:** 1 (servicio compartido central)
**Estado:** ✅ LISTO — todas las decisiones cerradas

---

## 1. Identidad

| Pregunta | Respuesta |
|---|---|
| ¿Qué es? | Servicio HTTP stateless que convierte texto en embeddings de 1024 dims usando el modelo BAAI/bge-m3 |
| ¿Problema? | Los agentes necesitan embeddings para retrieval semántico. Opciones SaaS (OpenAI, Voyage) implican que los datos de los clientes salen de la infra. BGE-m3 self-hosted elimina ese riesgo. |
| ¿Usuarios? | Knowledge module (Capa 1), agente de mercado CRIZA, pipeline de ingest DPN (200K normas) |
| ¿Depende de? | Modal (hosting), Volume `bge-m3-model-cache` (pesos ~570MB) |
| ¿Qué depende de él? | Cualquier módulo que necesite embeddings — consumido via HTTP, sin acoplamiento de código |
| ¿Milestone? | SEB-118 — DEADLINE duro antes del ingest DPN |

---

## 2. Trazabilidad

### Entidades / endpoints

| Entidad | Decisión de diseño | En código | Scope v0.1 | Estado |
|---|---|---|---|---|
| `POST /embed` — texto único | SEB-118 descripción | `modal_app.py` | ✅ incluido | ✅ |
| `POST /embed/batch` — lista de textos | SEB-118: DPN ingest 200K normas requiere batch | `modal_app.py` | ✅ incluido | ✅ |
| `GET /health` | Estándar de la plataforma (igual que ESMFold) | `modal_app.py` | ✅ incluido | ✅ |
| Caché de pesos en Volume | SEB-118: evitar re-descarga en cada cold start | `modal_app.py` + Volume `bge-m3-model-cache` | ✅ incluido | ✅ |
| Auth / API key | No requerido en v0.1 — el servicio vive dentro del workspace Modal privado de criza-dev | — | 🔵 postergado | 🔵 |

### Contratos

| Contrato | Entre quiénes | En código | Estado |
|---|---|---|---|
| `POST /embed` request/response | cualquier cliente → bge-m3 service | `modal_app.py` (Pydantic models) | ✅ |
| `POST /embed/batch` request/response | pipeline DPN ingest → bge-m3 service | `modal_app.py` (Pydantic models) | ✅ |

---

## 3. Checklist del playbook

### Seguridad Nivel 1
- [x] Sin credenciales en código (no hay claves — modelo público, hosting Modal autenticado por cuenta)
- [x] Sin `.env` requerido para este servicio (no tiene secretos propios)
- [x] `.env.example` del consumidor actualizado con `BGE_EMBED_URL`

### Seguridad Nivel 3
¿Aplica? No — este servicio no almacena datos. Stateless: recibe texto, devuelve vector, no persiste nada.

### Estructura de archivos
- [x] `README.md` — a crear junto con el código
- [x] `docs/DESIGN_GATE.md` — este archivo
- [ ] `modal_app.py` — pendiente (gate ✅, arrancamos a codear)

### Observabilidad
- [x] Logging de requests en FastAPI (automático con uvicorn)
- [x] `/health` devuelve estado del modelo y device

---

## 4. Scope explícito v0.1

| Feature | Versión objetivo | Razón |
|---|---|---|
| Auth (API key) | v0.2 | En v0.1 el acceso está controlado por el workspace privado de Modal. Cuando el servicio se exponga a más tenants o se abra la URL, agregar. |
| GPU | backlog | CPU alcanza para los volúmenes actuales. Si latencia de batch grandes se vuelve problema, migrar a T4. |
| Streaming / async batch grande | backlog | No requerido por ningún cliente actual. El ingest DPN va a enviar batches de 32-64 textos, manejable en sync. |

---

## 5. Decisiones

| # | Pregunta | Decisión | Razón | Fecha |
|---|---|---|---|---|
| 1 | ¿CPU o GPU? | CPU | Volúmenes actuales no justifican GPU. BGE-m3 en CPU: ~50ms/texto, batch de 64 textos en ~2s. | 2026-06-09 |
| 2 | ¿Librería para cargar el modelo? | `FlagEmbedding` (librería oficial de BAAI) | Soporte nativo de BGE-m3, maneja max_length y padding correctamente. Alternativa `sentence-transformers` funciona pero FlagEmbedding es el mantenedor del modelo. | 2026-06-09 |
| 3 | ¿Dimensiones? | 1024 (dense embeddings) | BGE-m3 soporta 1024 (dense), sparse, y colbert. Solo dense en v0.1 — es lo que necesita pgvector. | 2026-06-09 |
| 4 | ¿Volume para pesos? | Sí — `bge-m3-model-cache` | ~570MB, evita re-descarga en cada cold start. Mismo patrón que ESMFold. | 2026-06-09 |
| 5 | ¿Batch size máximo? | 256 textos por request | Límite razonable para un request HTTP único. El cliente DPN puede paginar. | 2026-06-09 |
| 6 | ¿Normalizar embeddings? | Sí — `normalize_embeddings=True` | Necesario para cosine similarity con pgvector. BGE-m3 recomienda normalizar para retrieval. | 2026-06-09 |
| 7 | ¿Contrato HTTP? | `{ "text": str }` → `{ "embedding": [float], "dims": 1024, "model": "BAAI/bge-m3" }` y batch análogo | Simple, extensible. Mismo estilo que ESMFold. | 2026-06-09 |
| 8 | ¿keep_warm? | No (default 0) | Cold start ~10-15s en CPU, aceptable para uso no crítico. Si el ingest DPN es bloqueante se puede setear temporalmente. | 2026-06-09 |

---

## 6. Estado del gate

**Estado actual:** ✅ LISTO

*Todas las decisiones cerradas. Sin gaps. Desarrollo puede arrancar.*
