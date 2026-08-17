# agents.md — CRIZA-biotech

> Contexto activo para Claude. Máximo ~200 líneas.
> Detalle técnico profundo → `ROADMAP.md` de cada componente.
> Arquitectura de plataforma → `KRIZA_Foundation_Document.md` en el repo `EMPRESAS-IA/docs/`
> (plataforma, repo separado — no hay path relativo válido entre `criza/` y `EMPRESAS-IA/` desde
> que CRIZA es su propio repo)

---

## Qué es CRIZA

Primera empresa agéntica de la plataforma EMPRESAS-IA (Capa 2). Sistema de transferencia de tecnología
ciencia-industria, foco biotech agro argentino. **Diseño vigente:** múltiples puertas de entrada →
Orquestador (motor dirigido por objetivo) → agentes investigadores → Armador → **expediente de decisión** →
el humano decide. El pipeline viejo Scout→Especialista→Mercado quedó superado (rethink cerrado a nivel
diseño 2026-06-13, `docs/architecture.md` decisiones D1–D10). **Redefinición en curso desde 2026-08-14**
de qué es CRIZA de acá en más — ver "Estado operativo" abajo y `docs/PROPUESTA_DESTINO.md`.

---

## Agentes activos

> Generado por `python scripts/generar_agents_md.py` — no editar a mano entre los marcadores.
> Fuente: `orquestador/agents_registry.yaml` + suite de tests real + última decisión vigente en
> `decisiones_sistema` (KM) para ese componente.

<!-- GENERADO:AGENTES_ACTIVOS:INICIO -->
| Agente | Módulo | Tests | Registrado | Última decisión |
|---|---|---|---|---|
| Mercado | `market_agent/` | 67/67 ✅ (+6 integration) | ✅ activo, DESIGN_GATE.md ✅ | — |
| Evidence Generalista | `evidence_generalista/` | 48/48 ✅ (+1 integration) | ✅ activo, DESIGN_GATE.md ✅ | — |
| Investigación Amplia | `investigacion_amplia/` | 39/39 ✅ (+1 integration) | ✅ activo, DESIGN_GATE.md ✅ | — |
| Armador | `armador/` | 31/31 ✅ (+1 integration) | ✅ activo, DESIGN_GATE.md ✅ | — |
| Especialista Proteínas | `scientific_agent/` | sin tests unit (todos integration/deselected) | 🟡 registrado, inactivo, sin DESIGN_GATE.md | — |
| Especialista Microbiólogo | `microbiologo_agent/` | 50/50 ✅ (+2 integration) | ✅ activo, DESIGN_GATE.md ✅ | [2026-08-16] Etapa 4 (parte 2) del plan — Microbiólogo conectado al modelo de casos.yaml |
| Especialista Ingeniero Ambiental | `ingeniero_ambiental_agent/` | 22/22 ✅ (+1 integration) | ✅ activo, DESIGN_GATE.md ✅ | [2026-08-16] Etapa 7 del plan — segundo especialista, Ingeniero Ambiental |
| Especialista Ingeniero Agrónomo | `agronomo_agent/` | 22/22 ✅ (+1 integration) | ✅ activo, DESIGN_GATE.md ✅ | [2026-08-16] Tercer especialista — Ingeniero Agrónomo, pedido explícito de Sebas con señal real |
<!-- GENERADO:AGENTES_ACTIVOS:FIN -->

## Borrado (histórico)

Movido a `criza/_archivo_temporal/` el 2026-07-01, confirmado sin referencias vivas (grep en todo
el repo) y **borrado definitivamente el 2026-07-02**. Ya no existe en el filesystem.

| Qué era | Por qué se borró |
|---|---|
| `divergent_agent/` | Reemplazado por Investigación Amplia. Sus assets vigentes (marco_blue_ocean, metodologia_busqueda) están en `docs/`. |
| `convergent_agent/` | Reemplazado por Mercado + Evidence + Armador. Paradigma distinto (converger a 1 → el sistema elige), reemplazado por expediente donde el humano elige. |
| `orquestador_v1.py` + `run.py` | Orquestador v1 LLM puro, reemplazado por Motor v2 YAML. |
| `scout.py` + `run_scouting.py` | Scout jubilado, marcado JUBILADO en agents.md. |
| `metodologia_convergente_AGENTE.md` | Metodología del convergente muerto. |

> **Replanteo 2026-06-02:** el descubrimiento pasa de **supply-first** (scout: "¿qué podemos
> producir?") a **demand-first** ("¿dónde hay demanda reprimida que el biotech destrabaría?").
> El scout se jubila; sus partes buenas se absorben en el agente divergente nuevo. Diverge y
> converge son dos agentes especializados acoplados por un **artefacto con schema definido**
> (no comunicación en vivo). Detalle y trazabilidad completa en `docs/architecture.md`.
>
> **Principio de veracidad (obligatorio en ambos agentes nuevos):** datos comprobados, no
> suposiciones. El output alimenta una decisión de inversión real. Todo dato lleva etiqueta
> [VERIFICADO]/[ESTIMADO]/[INFERIDO] + fuente. Gap declarado > inferencia disfrazada de hecho.

Movido a `criza/_archivo_temporal/` el 2026-08-15, confirmado sin referencias vivas (grep en
todo el repo + smoke test de imports) y **borrado definitivamente el 2026-08-15**. Ya no existe
en el filesystem. Detalle completo: `docs/progress/2026-08-15.md`, decisión `componente=infra`
en `decisiones_sistema`.

| Qué era | Por qué se borró |
|---|---|
| `server.py` | MCP server legacy — 6 de 7 tools exponían el esquema corrida/oportunidad/aprendizaje del agente divergente/convergente, sin consumidor real desde su borrado (02/07). |
| `ingest_corrida.py` | Su punto de invocación automática (`divergent_agent/test_metodologia.py`) ya no existía desde el 02/07. |
| `ingest_historico.py` | Script de backfill histórico de una sola vez, dependía exclusivamente de `ingest_corrida.py`. |
| `km_tools/retrieve.py` | Sus dos funciones (`get_opportunity_history`, `update_opportunity`) eran 100% del mismo pipeline muerto. |
| `store_corrida`/`store_opportunity`/`store_document`/`store_learning`/`_link_corrida` (`km_tools/store.py`) | Ídem — quedan `store_fuente_externa`/`batch_store_fuentes_externas` (vivas). |
| `search_knowledge` (`km_tools/search.py`) | Ídem — quedan `get_sector_corpus`/`search_fuentes_externas`/`get_paper_full_text`/`get_ficha_full_text` (vivas). |
| `Corrida`/`Oportunidad`/`Aprendizaje`/`CorridaOportunidad`/`CorridaDocumento` (`km_models.py`) | Ídem — queda solo `Documento`. Las tablas en Neon no se tocaron, solo el código. |

---

## Stack activo

- **Modelos:** SCOUT_MODEL · SPECIALIST_MODEL · MARKET_MODEL — configurables en `.env` de cada componente
- **Default:** `claude-sonnet-4-6` para todos. Cambiar a Opus para análisis profundos.
- **Proveedor de modelo por agente (2026-08-15):** `utils/ai_client.py` — `complete()`/
  `complete_streaming()` sobre LiteLLM. `resolver_modelo("claude-sonnet-4-6")` →
  `"anthropic/claude-sonnet-4-6"` por default, sin tocar ningún `.env`. Evidence Generalista,
  Investigación Amplia y Armador migrados; Mercado excluido (tool nativa `web_search`, ver
  decisión `componente=ai_client` en `decisiones_sistema`).
- **`requirements.txt`** (raíz, nuevo 2026-08-15) — no existía; las dependencias se instalaban
  a mano sin manifiesto. Armado desde un escaneo real de imports (no de memoria). No incluye
  `torch`/`esm`/`fastapi`/`uvicorn` (solo usadas en `scientific_agent/pod_server.py`, RunPod ya
  reemplazado por Modal) ni `FlagEmbedding` (corre dentro del contenedor de Modal). Encontrado
  de paso, y llevó al archivado de abajo: `server.py` importaba `mcp`, no instalado — estaba
  roto antes de eso.
- **Pipeline scout/divergente/convergente, archivado 2026-08-15** (`_archivo_temporal/`):
  `server.py`, `ingest_corrida.py`, `ingest_historico.py`, `km_tools/retrieve.py` +
  `store_corrida`/`store_opportunity`/`store_document`/`store_learning`/`search_knowledge` de
  `km_tools/`. Sin consumidor real desde que `divergent_agent/` se borró el 02/07 — nunca se
  había limpiado lo que lo alimentaba/consumía. Tablas en Neon sin tocar, solo el código. Ver
  decisión `componente=infra` en `decisiones_sistema`.
- **Literatura:** OpenAlex API (250M+ papers, sin key) — fallback Semantic Scholar
- **INTA Digital:** OAI-PMH (`repositorio.inta.gob.ar/oai/request`) + discover scraping — `criza/utils/inta.py`; AGROVOC tesauro — `criza/utils/agrovoc.py`
- **CONICET Digital:** OAI-PMH genérico — `utils/oai_pmh.py` (`OAIPMHHarvester`) +
  `ingest/harvest_conicet.py` (driver, antes `knowledge_module.ingesta.ingest_corpus`) +
  `config/connectors/conicet.yaml`. Movidos de `knowledge_module/` a acá el 2026-08-14 — código
  genérico sin hardcodeo de CRIZA, pero único consumidor real siempre fue CONICET/CRIZA.
- **Document Store (Capa 1):** `knowledge_module.document_store.store` (parte del paquete pip
  desde 2026-07-22, antes vivía en `plataforma/document_store/`) — descarga PDFs + extrae texto
  (pypdf). Datos propios de CRIZA en `document_store_data/` (raíz de este repo, gitignored,
  `KM_DOCUMENT_STORE_DIR` en `.env`) — movidos acá el 2026-08-14 desde
  `EMPRESAS-IA/plataforma/document_store/data/criza/`, donde habían quedado huérfanos (1.455
  PDFs) desde antes de la migración del código al paquete.
- **GPU / Compute (`services/`):** Modal serverless, apps propias de CRIZA (workspace
  `criza-dev`) — `services/esmfold/` (app `criza-esmfold`) y `services/bge-m3/` (app
  `criza-bge-m3`). Movidos de `EMPRESAS-IA/services/` acá el 2026-08-14 (mismo motivo que
  CONICET arriba: nada corre compartido en runtime, cada instancia despliega lo suyo). Mismos
  nombres de app y workspace → mismas URLs, sin cambios en `.env`. DPN sigue apuntando a
  `criza-bge-m3` por ahora (pendiente de su propio deploy — ver
  `EMPRESAS-IA/docs/km-aislamiento-diagnostico.md` §12.2-12.5, fuera de esta sesión). Cualquier
  agente puede conectarse a cualquier servicio — son hermanos, no están anidados en ningún
  agente.
- **RunPod:** pod `qruo50jffhrgze` (H200 SXM) — **REEMPLAZADO por Modal. Mantener apagado.**
- **Tests:** pytest con markers `unit` / `integration`

---

## Linear

- **Proyecto:** CRIZA | **Equipo:** Sebabizz._dev
- **Cycle activo:** ver Linear directamente (no hardcodeado acá — mismo motivo que la sección de arriba)

---

## Estado operativo — ver Linear

El estado de tareas (qué está Done/In Progress/Todo, en qué orden) vive en **Linear**
(proyecto CRIZA, equipo Sebabizz._dev) — es la fuente de verdad según la tabla de este mismo
CLAUDE.md, no este archivo. Este archivo no duplica esa lista: la duplicación es lo que hizo
que este archivo se desactualizara (alguien actualiza Linear, se olvida de actualizar acá, o
viceversa) y creciera muy por encima de su propio límite de ~200 líneas.

Bloqueadores estructurales que **no** tienen equivalente en Linear (decisiones de arquitectura
pendientes, no tareas ejecutables) — generado desde `decisiones_sistema` (KM), todas con
`estado=vigente`. Una decisión resuelta o superada deja de aparecer acá — el historial completo
sigue en el KM (`scripts/km_decisiones.listar_decisiones_vigentes` solo trae las vigentes) y en
`docs/progress/*.md`. Fases D-G del plan de independización (2026-08-14) y la reestructuración
del KM (2026-07-24) ya cerraron y por eso no se migraron acá — su detalle completo sigue en
`docs/progress/2026-08-14.md` y `knowledge_module/docs/KM_MOTOR_GENERICO_GATE.md`.

<!-- GENERADO:ESTADO_OPERATIVO:INICIO -->
- [ ] **Etapa 16 (bug real) — historial de conversaciones + recordar sesión activa** (2026-08-17, Sebas + Claude). Bug reportado por Sebas: una respuesta del Conductor 'se perdió' al volver más tarde a /conductor. Investigado antes de tocar código: el dato NUNCA se perdió -- seguía intacto en el KM (conductor_sesiones), se le mostró de vuelta completo. La causa real: /conductor y /especialistas/[nombre] creaban una sesión nueva en cada carga de página y nunca guardaban el session_id en ningún lado del browser, así que volver más tarde siempre arrancaba una conversación vacía nueva, dejando la anterior huérfana (pero intacta) en el KM -- confirmado con 48 sesiones de Conductor creadas ese día, la mayoría vacías. Fix en dos piezas, ambas elegidas explícitamente por Sebas entre 3 opciones ('localStorage solo' / 'historial solo' / 'los dos'): (1) localStorage guarda el session_id activo (clave por página en el Conductor, clave por especialista+frente en el chat de especialistas) -- al montar, si hay uno guardado, hidrata el chat desde el KM en vez de crear uno nuevo; (2) botón 'Historial' en ambas páginas -- 4 endpoints GET nuevos en api/main.py (/conductor/sesiones, /conductor/sesiones/{id}, /especialistas/sesiones?especialista=, /especialistas/sesiones/{id}), reconstruyen los turnos visibles vía _mensajes_a_turnos() (filtra pasos intermedios de tool-use/tool-result) sin campo nuevo en el KM -- la misma fuente que ya se guardaba alcanza. 12 tests nuevos, 474/474 unit en verde, auditor sin hallazgos nuevos. Verificado real: con el session_id de la conversación reportada como perdida en localStorage, recargar /conductor la restauró completa (mismo texto, mismos 5 vectores blue ocean); el panel de Historial listó las 8 conversaciones reales del Conductor en orden correcto por fecha, reabrir una distinta funcionó; repetido en /especialistas/microbiologo con 7 sesiones reales y la etiqueta correcta (consulta libre / sobre un frente). **Motivo:** Sebas: 'tenemos un problema, le hice una pregunta al conductor, me respondió, cuando quise volver al rato, se había borrado lo que me respondió y se perdió eso, gasté tokens, perdí la información, no quedó registrada en ningún lugar visible.' **Alternativas consideradas:** Solo localStorage (sin historial completo) -- descartada explícitamente por Sebas: no cubre cambiar de navegador/dispositivo ni un localStorage borrado.; Solo historial completo (sin localStorage) -- descartada explícitamente por Sebas: no evita que una simple recarga de página arranque una sesión nueva por default.
- [ ] **Etapa 15 — elegir modelo de IA por sesión de chat desde la web** (2026-08-17, Sebas + Claude). Granularidad: por sesión de chat, no global ni por agente -- las sesiones ya son la unidad natural del sistema (cada una su propia ficha KM), así que no hizo falta persistencia nueva, solo sumar un campo `modelo` a conductor_sesiones.yaml y especialista_sesiones.yaml y pasarlo como model= a enviar_mensaje() (ya aceptaba ese kwarg desde utils/ai_client.py, 2026-08-15). Lista curada, no texto libre: utils/ai_client.py::MODELOS_DISPONIBLES (4 modelos Anthropic) es la única fuente -- GET /modelos la expone tal cual. Lista curada en vez de texto libre porque hoy solo hay ANTHROPIC_API_KEY configurada (verificado en .env); ofrecer proveedores sin credenciales rompería al elegirlos. El modelo queda fijado al crear la sesión -- el selector se deshabilita apenas hay un turno, cambiarlo antes del primer mensaje recrea la sesión con el modelo nuevo. 12 tests nuevos, 464/464 unit en verde, auditor sin hallazgos nuevos. Verificado real (no solo tests): desde el navegador, elegido Haiku 4.5 en /conductor, mensaje real enviado, confirmado leyendo la ficha del KM que props.modelo == claude-haiku-4-5-20251001 y el turno quedó persistido; repetido en /especialistas/microbiologo con Opus 5, misma confirmación. **Motivo:** Sebas pidió poder elegir qué modelo de IA usa una conversación desde la web, sin reiniciar el server con otra env var -- la abstracción de backend (utils/ai_client.py::resolver_modelo, PROPUESTA_DESTINO.md §8) ya existía y estaba verificada desde el 2026-08-15, pero no había ninguna superficie para elegirlo en runtime. **Alternativas consideradas:** Selección global (una env var por deployment) -- descartada: ya era el estado actual, no resuelve el pedido de elegir por conversación.; Selección por agente (fija para todas las sesiones de un mismo especialista) -- descartada: menos flexible que por sesión sin ahorrar complejidad real.; Texto libre para el modelo (cualquier string de LiteLLM) -- descartada: hoy solo hay credenciales de Anthropic, texto libre permitiría elegir un proveedor que rompe al usarlo.
- [ ] **Etapa 14 (arranque) — descarga de informes en Markdown** (2026-08-17, Sebas + Claude). GET /documentos/{id}/descargar en api/main.py -- Content-Disposition: attachment, nombre de archivo derivado del título vía _slug_archivo() (normaliza acentos/símbolos con unicodedata, no depende de que el header HTTP maneje bien UTF-8 en el filename). Link <a href> directo en /documentos/[id] y en la lista de documentos de /casos/[id] -- sin JS del lado del cliente, el navegador dispara la descarga solo por el header. Formato elegido explícitamente por Sebas: Markdown (el contenido ya está guardado así, sin conversión) en vez de PDF o Word. 5 tests nuevos, 456/456 unit en verde, auditor sin hallazgos nuevos. Verificado real contra el server de producción: descarga completa de un informe real de Helios (105 líneas, contenido íntegro), verificado por curl y en el navegador en ambos lugares donde aparece el link. Además, se usó la Etapa 12 (consulta libre) tal cual ya estaba construida para responder dos preguntas reales de composición química que Sebas quería hacerle al Microbiólogo sin el sesgo de los 3 documentos ya existentes de Helios -- confirma que el diseño de consulta libre cumple lo que promete, sin necesitar ningún cambio. **Motivo:** Sebas, al arrancar la Etapa 14 (corregir/reiniciar un caso mal encarado): antes de diseñar, se le preguntó qué específicamente sentía mal encarado en Helios. Su respuesta reencuadró el problema (no es un dato mal cargado, es un ángulo de abordaje distinto) y de paso pidió, sobre la marcha, poder descargar los informes. **Alternativas consideradas:** PDF o Word (.docx) para la descarga -- descartados: Sebas eligió explícitamente Markdown para arrancar, más simple y sin necesitar una librería de conversión nueva.
- [ ] **Etapa 13 — crear casos nuevos desde la web y el Conductor** (2026-08-17, Sebas + Claude). utils/casos.py::crear_caso(nombre, descripcion, tenant, estadio=None, fecha_inicio=None, participantes=None, notas=None) -- función base compartida, computa texto_busqueda (campo vectorizado de casos.yaml) a partir de nombre+descripción. Un caso puede crearse sin frentes (ya permitido explícitamente por casos.yaml). POST /casos en api/main.py -- nombre/descripcion obligatorios (400 si faltan), resto opcional, escribe directo a producción (primera excepción deliberada a '/casos es solo lectura', mismo criterio que /conductor/* y /especialistas/*). web/app/casos/nuevo/page.tsx -- formulario, redirige a /casos/{id} al crear; link '+ Nuevo caso' en /. Tool crear_caso del Conductor llama la misma utils/casos.py::crear_caso -- SYSTEM_PROMPT instruye confirmar (resumir nombre+descripción) antes de llamarla, mismo criterio que correr_especialista, más importante acá porque no hay forma de corregir un caso mal armado todavía (Etapa 14, sin resolver). 10 tests nuevos (2 utils, 4 api, 4 conductor), 451/451 unit en verde, auditor sin hallazgos nuevos. Verificación real con decisión explícita de Sebas sobre cómo hacerla (el endpoint no tiene staging intermedio): contra staging, no producción -- crear_caso() real, campos correctos, aparece en listar_casos. Contra el server de producción, sin escribir nada de prueba: página /casos/nuevo renderiza y valida bien, conversación real con el Conductor describiendo un caso nuevo pidió confirmación y no llamó la tool -- confirmado que /casos seguía teniendo los mismos 2 casos reales de siempre. **Motivo:** Sebas, el 16/08: '¿cómo abro un caso nuevo? ¿solo con el Conductor?' -- se le respondió con honestidad que no había ningún camino, ni web ni Conductor. Agendado para retomar ('dejemos agendado para mañana') y resuelto al continuar la sesión, primero de 3 ítems en el orden acordado. **Alternativas consideradas:** Solo formulario web o solo tool del Conductor -- descartado: Sebas eligió explícitamente los dos (pregunta directa antes de codear), reusando la misma función base para no duplicar la lógica de creación entre las dos superficies.; Verificar contra producción con un caso de prueba y borrarlo después -- descartado: Sebas eligió explícitamente verificar solo contra staging para no tocar producción en absoluto, ni siquiera de forma reversible.
- [ ] **Etapa 12 — consulta libre a un especialista, sin necesitar un caso** (2026-08-16, Sebas + Claude). frente_id: str | None = None en enviar_mensaje() de los 3 especialistas. Sin frente_id: no se llama obtener_frente_con_caso (cero queries de más), y la consulta de lecciones usa el texto de la pregunta en vez de una descripción de caso que no existe -- más preciso, no un downgrade. Resultado neto: la consulta libre es MÁS barata en tokens que el modo con caso, no una alternativa degradada. api/main.py: frente_id opcional en POST /especialistas/{nombre}/sesiones -- sin él, la sesión arranca vacía sin llamar iniciar_sesion. web/app/especialistas/[nombre]/page.tsx sin ?frente= entra en modo libre automáticamente (antes mostraba un error). web/app/especialistas/page.tsx (listado) suma link 'Consulta libre' por especialista. 4 tests nuevos, 441/441 unit en verde, auditor sin hallazgos nuevos. Verificado real: sesión libre con el Microbiólogo respondida correctamente sin ningún caso de por medio, confirmado leyendo el KM que la ficha quedó con frente_id: None. **Motivo:** Sebas, mirando el chat de un especialista recién construido, preguntó tres cosas de una: por qué el chat requería un frente ('¿no puedo hacerles preguntas que no sean en el marco de un caso?'), le preocupaba el consumo de tokens para una consulta simple, y preguntó cómo abrir un caso nuevo. Se le respondió con honestidad que hoy NINGÚN camino (ni la web ni el Conductor) permite crear un caso -- gap real, no resuelto, anotado como Etapa 13 aparte. Eligió resolver primero la consulta libre (su necesidad inmediata) y dejar crear-casos para después. **Alternativas consideradas:** Dejar frente_id obligatorio y decirle a Sebas que siempre tiene que crear un caso primero -- descartado: no resolvía su necesidad real (consulta rápida antes de decidir si vale la pena abrir un caso) y hubiera significado gastar tokens en armar un caso para una pregunta que quizás no lo amerita.
- [ ] **Etapa 11 — panel de características por agente, leído en vivo del código** (2026-08-16, Sebas + Claude). GET /agentes/{nombre} en api/main.py -- devuelve system_prompt y tools (name/description/disponible_en_chat) leídos directo de los objetos de módulo ya cargados en la Etapa 10 (_mod_conductor/_mod_microbiologo/_mod_ingeniero_ambiental/_mod_agronomo) -- no hay copia ni doc paralelo que se desincronice, es la misma lista que el agente usa para operar. disponible_en_chat se deriva comparando contra TOOLS_CHAT (Etapa 10) para marcar qué tools son exclusivas de la corrida formal (submit_evaluacion_tecnica). Página /agentes/[nombre] (Server Component, solo lectura) con las tools y el prompt completo. Link 'ℹ️ Características' en /conductor y en /especialistas/[nombre], target=_blank -- Sebas pidió explícitamente 'puede ser con un acceso a otra ventana'. 3 tests nuevos, 439/439 unit en verde, auditor sin hallazgos nuevos. Verificado real contra el servidor corriendo: GET /agentes/conductor (5 tools reales) y GET /agentes/microbiologo (9 tools reales, incluidas las 4 bioquímicas, submit_evaluacion_tecnica correctamente marcada como solo-corrida-formal). Página verificada en el navegador con get_page_text. **Motivo:** Tercer y último pedido de Sebas en el mismo hilo donde se resolvió la persistencia de sesiones del Conductor (junto con lecciones -- Etapa 9 -- y chat por especialista -- Etapa 10): 'que en la ventana de cada agente figure, puede ser con un acceso a otra ventana, las características del agente, qué puede hacer y a qué herramientas está conectado, con una descripción de cada herramienta y que esto se actualice cuando hay cambios de características o de herramientas a las que está conectado'. **Alternativas consideradas:** Documento Markdown mantenido a mano por agente -- descartado de entrada: es exactamente el tipo de desincronización silenciosa que CLAUDE.md ya identificó como causa raíz de deuda documental en este proyecto (ver decisión del 15/08 sobre agents.md generado). El pedido explícito de Sebas ('que se actualice solo') excluía esta opción directamente.
- [ ] **Etapa 10 — chat directo con cada especialista (no solo con el Conductor)** (2026-08-16, Sebas + Claude). Mismo patrón en los 3 especialistas (microbiologo_agent.py, ingeniero_ambiental_agent.py, agronomo_agent.py): el dispatch de tools que vivía inline en el if/elif de _run_loop se extrajo a _despachar_tool() propia (refactor behavior-preserving, verificado corriendo los tests existentes sin cambios antes de sumar nada nuevo) para que el chat la reuse sin duplicar ~170 líneas por agente. iniciar_sesion(frente_id) arma el primer mensaje con el mismo contexto que la corrida formal; enviar_mensaje(messages, texto, frente_id) es un loop conversacional tipo conductor.enviar_mensaje(). TOOLS_CHAT excluye submit_evaluacion_tecnica a propósito: el chat da acceso al mismo conocimiento pero la evaluación formal persistida sigue siendo exclusiva del camino de un turno vía la costura -- mismo principio de 'nunca bypasear la costura' que ya rige el Conductor. api/main.py sumó POST /especialistas/{nombre}/sesiones y POST /especialistas/sesiones/{id}/mensajes, área nueva especialista_sesiones en el KM. Web: web/app/especialistas/[nombre]/page.tsx (client component, scoped a frente vía ?frente=<id>) + links por frente en /casos/[id]. Hallazgo real no cosmético: conectar api/main.py a los 3 especialistas rompió la regresión combinada -- los 3 agentes tienen DOS consumidores incompatibles en el mismo proceso (orquestador/registry.py::get_registry(), package-qualificado y perezoso; el conftest.py/run.py de cada agente, bare) -- cualquiera de los dos estilos que tocara primero sys.modules[nombre] rompía al otro, y el propio archivo del agente inserta su carpeta al frente de sys.path como efecto de lado al cargar, lo que por sí solo ya alcanza para romper una resolución posterior. Resuelto con importlib.util.spec_from_file_location bajo una clave propia (_api_<nombre>), restaurando sys.path después de cada carga -- verificado que get_registry() sigue funcionando después. 11 tests nuevos en los 3 agentes + 6 en api/tests, 436/436 unit en verde, auditor sin hallazgos nuevos. Verificado real: sesión de chat real con el Microbiólogo sobre el Frente técnico de Helios, respuesta sustancial con fuentes reales -- confirmado leyendo el KM que NO se creó un 4to documento_caso (seguían siendo los mismos 3 de las corridas formales), la separación chat/persistencia formal funciona como se diseñó. **Motivo:** Sebas, en el mismo hilo donde se confirmó la persistencia de sesiones del Conductor: pidió explícitamente poder hablar con cada especialista, no solo con el Conductor, junto con el panel de características (Etapa 11) y que el Conductor escriba lecciones (Etapa 9, ya resuelta). **Alternativas consideradas:** Reemplazar run() por un loop conversacional en cada especialista -- descartado: run() (contrato SEB-115, de un turno) sigue siendo lo que usa el Motor/la costura para la evaluación formal; forzar todo a un loop conversacional hubiera roto ese contrato sin necesidad.; Bare import o package-qualificado para que api/main.py acceda a los 3 especialistas -- ambos descartados tras confirmar en vivo que cualquiera de los dos colisiona con el otro consumidor real (get_registry() vs. los propios tests/run.py de cada agente) en el mismo proceso del server.
- [ ] **Etapa 9 — el Conductor escribe lecciones al KM (automático al cerrar sesión + explícito a pedido)** (2026-08-16, Sebas + Claude). conductor.py sumó cerrar_sesion(messages, *, tenant, verbose=False): corta si hay menos de 2 turnos reales; si no, lee lecciones ya existentes sobre temas análogos (aprendizaje.leer_lecciones_caso) y le pasa el transcript completo a un juez de una sola llamada (tool submit_leccion, sin forzar tool_choice, mismo patrón submit_* sin forzado que ya usan los especialistas) que decide hay_leccion_nueva; si true y no cubierta, guarda con fuente=agente_auto. Tool nueva anotar_leccion para el trigger explícito (fuente=humano), misma guardar_leccion_caso que ya usa el resto del sistema (SEB-156) -- nada nuevo del lado de persistencia. CLI (run.py) llama cerrar_sesion al salir (punto de cierre natural). Web: nuevo endpoint POST /conductor/sesiones/{id}/cerrar, botón 'Nueva conversación' en /conductor lo llama awaited antes de crear sesión nueva, más beforeunload+sendBeacon como red de contención best-effort. SYSTEM_PROMPT corregido -- ya no dice que el Conductor no persiste nada de la conversación (desactualizado apenas se resolvió la persistencia de sesiones horas antes el mismo día). 11 tests nuevos (8 conductor + 3 api), 419/419 unit activos en verde, auditor sin hallazgos nuevos. Verificado real (no solo mocks): trigger explícito guardó 3 lecciones reales bien formadas contra el modelo real; trigger automático dijo 'no' correctamente en una conversación de solo-lectura; anti-duplicación confirmada (reconoció como 'ya cubierta' una lección que el trigger explícito ya había guardado en la misma sesión). Observación real, no bug: el modelo tendió a invocar anotar_leccion por su cuenta ante afirmaciones sustanciales aunque el prompt pide no hacerlo sin pedido explícito -- deja la rama 'automático positivo sin pedido previo' cubierta solo por tests con mock en esta sesión, documentado como observación no urgente en el Design Gate. **Motivo:** Al confirmar la persistencia de sesiones del chat, Sebas aclaró una confusión real: pensaba que el Conductor ya escribía al KM una parte de 'aprender de la experiencia' -- el área lecciones (SEB-156) ya existe y el Conductor ya la lee (ver_caso -> leer_lecciones_caso), pero nunca escribía ninguna. Trigger confirmado por Sebas ante pregunta explícita: ambos (automático al cerrar sesión + explícito a pedido) -- cierra el loop de aprendizaje transversal que CLAUDE.md exige para todo agente ('leer lecciones análogas antes de actuar, escribir después'), del que el Conductor era el único agente que solo leía. **Alternativas consideradas:** Forzar tool_choice en la llamada del juez de cierre -- descartado: utils/ai_client.py no expone tool_choice hoy, y el patrón submit_* sin forzado ya es suficientemente confiable en el resto del sistema (verificado en corridas reales de los 3 especialistas) -- no vale la pena el costo de sumar el parámetro para este caso.; Inferir el cierre de sesión por inactividad (con un cron/job periódico) -- descartado: sin infraestructura de scheduled jobs en el proyecto hoy, hubiera sido construir infraestructura nueva especulativa para un caso de uso (Sebas cerrando la pestaña sin avisar) que ya tiene una solución más simple (beforeunload+sendBeacon, best-effort) suficiente para v1.
- [ ] **Sesiones del chat del Conductor persistidas en el KM, no en memoria del proceso** (2026-08-16, Sebas + Claude). Área nueva `conductor_sesiones` (config/plantillas/conductor_sesiones.yaml), tipo `sesion`, sin vectorizar. `session_id` que ve el browser es directamente el id de la ficha — no hay traducción. conductor/conductor.py sumó serializar_mensajes() (convierte ContentBlock a dict plano vía dataclasses.asdict; no hace falta función inversa porque utils/ai_client.py::_mensajes_a_formato_openai ya acepta ContentBlock o dict plano indistintamente al armar la siguiente llamada al modelo). api/main.py reescrito: POST /conductor/sesiones crea la ficha (motor_api.guardar_ficha), POST /conductor/sesiones/{id}/mensajes lee props.mensajes (motor_api.obtener), lo pasa a enviar_mensaje(), reescribe props.mensajes (motor_api.actualizar_props). Eliminado el dict en memoria (_sesiones_conductor) por completo. SYSTEM_PROMPT del Conductor corregido — decía 'no persistís nada de esta conversación', ya no es cierto; ahora distingue historial crudo (sí persiste) de lección destilada (todavía no, Etapa 9). Verificado con el criterio de aceptación real: sesión creada, mensaje respondido, servidor matado con taskkill /F (no shutdown limpio), proceso nuevo levantado, segundo mensaje a la misma sesión recordó el primero — confirmado leyendo la ficha directo del KM (6 mensajes, incluido tool-use, serializados sin pérdida). Encontrado en el camino: api/.env nunca había existido (solo .env.example) — el chat de la Etapa 6 funcionaba porque nadie había reiniciado el server en un proceso fresco sin el entorno ya exportado a mano; corregido copiando .env (root) a api/.env, mismo patrón que ya documentaba api/.env.example. 409/409 unit activos en verde, auditor sin hallazgos nuevos. **Motivo:** Sebas, mirando el chat recién construido en la misma sesión: 'las sesiones del chat viven en memoria del servidor (si reiniciás api/run.py, se pierden), cómo resolvemos esto?' — la deuda que el Design Gate de web/ había documentado como aceptada para v1 dejó de ser aceptable apenas la vio de cerca. Coherente con el principio ya vigente en CLAUDE.md: 'si el output de un agente no está en el KM, no existe para el sistema' — mismo precedente que pipeline_status/token_usage. **Alternativas consideradas:** Archivo JSON local en disco — descartado: invisible para cualquier otra instancia del sistema (Armador, Orquestador, un futuro agente), mismo argumento que ya excluye outputs/ local para cualquier otro agente.; Cliente (browser) sostiene el historial serializado sin sesión en el server — descartado en la decisión original del mismo día (ver decisión previa 'Chat del Conductor en la web'), sigue sin ser la respuesta correcta incluso resuelto el problema de serialización, porque expondría el historial completo de negocio al cliente sin necesidad.
- [ ] **Chat del Conductor en la web — v1.2 adelantada el mismo día, más promoción de staging a producción** (2026-08-16, Sebas + Claude). api/main.py sumó POST /conductor/sesiones y POST /conductor/sesiones/{id}/mensajes, envolviendo conductor.enviar_mensaje() tal cual — misma función que usa el CLI. Sesiones en memoria del proceso (session_id -> messages) porque messages mezcla dicts planos y objetos del SDK de Anthropic no serializables a JSON — válido para un usuario local, no para multi-usuario. web/app/conductor/page.tsx: único client component de la app (los otros 3 son Server Components), interactivo. Corregido en el camino: api/main.py importaba 'from conductor.conductor import enviar_mensaje' (calificado por paquete), lo que cacheaba el paquete vacío en sys.modules['conductor'] y rompía 'import conductor as cond' de conductor/tests/test_conductor.py cuando ambas suites corrían en el mismo proceso pytest (17 tests fallaban solo en la regresión combinada) — corregido insertando conductor/ al frente del sys.path e importando bare, mismo truco de conductor/run.py. Además, promovidos a producción los 3 documento_caso reales (microbiólogo, ingeniero ambiental, agrónomo) que vivían en staging — Sebas eligió explícitamente promoverlos en vez de dejarlos solo en staging o re-correr contra producción. Verificado en el navegador de verdad: conversación real de 2 turnos, el Conductor reportó correctamente los 3 documentos recién promovidos y sintetizó el cuello de botella real del caso (pendientes de negocio, no técnicos). 407/407 unit activos en verde, npm run build sin errores, auditor sin cambios. **Motivo:** Sebas pidió acceso a la web esperando poder hablar con los agentes, no solo navegar en modo lectura — al aclarársele que eso era v1.2 (ya anotado, no v1), respondió 'no le encuentro mucha utilidad a lo que hay ahora, no había entendido eso' y eligió explícitamente adelantar v1.2 en la misma sesión en vez de dejarlo pendiente. **Alternativas consideradas:** Cliente (browser) sostiene el historial de mensajes entre requests, sin sesión en el server — descartado: messages incluye objetos del SDK de Anthropic no serializables a JSON tal cual, hubiera exigido reconstruirlos en cada ida y vuelta sin garantía de que la reconstrucción coincida con lo que utils/ai_client.py espera.; Dejar los 3 documentos solo en staging y no darle acceso a Sebas hasta re-correr contra producción — descartado: Sebas prefirió promover lo ya verificado en vez de re-pagar tokens de una corrida ya probada exitosa.
- [ ] **Etapa 6 del plan — scaffold real de la app web (api/ + web/)** (2026-08-16, Sebas + Claude). Construido api/ (FastAPI, 3 endpoints de solo lectura: GET /casos, GET /casos/{id}, GET /documentos/{id} — reusa knowledge_module/utils/casos.py directo, cero SQL duplicado en TypeScript) + web/ (Next.js 15, App Router, TypeScript, Tailwind — create-next-app real). 3 páginas: / (lista de casos), /casos/[id] (frentes con estado de documentos, pendientes, artefactos externos), /documentos/[id] (contenido completo, renderizado como markdown real con react-markdown+remark-gfm+@tailwindcss/typography, no texto plano). api/ lee de producción (estrictamente de solo lectura, sin el riesgo de escritura que forzó staging en la Etapa 4). 7 unit + 1 integration test (Python), 361/361 activos en verde, auditor sin ALTO/MEDIO nuevos. Verificado en el navegador de verdad (Claude Browser, no solo curl): lista de casos con datos reales, detalle de Helios con frentes/pendientes reales, npm run build sin errores. Encontrado en el camino: el TestClient síncrono de FastAPI rompe con 'Event loop is closed' al hacer 2+ requests en el mismo test contra el engine async de knowledge_module — resuelto con httpx.AsyncClient. **Motivo:** Etapa 6 del plan aprobado el 16/08 — el modelo de datos y las páginas ya estaban diseñados (config/plantillas/casos.yaml, docs/PROPUESTA_DESTINO.md §7), esta etapa era el código en sí. Fork de arquitectura real (cómo Next.js accede a los datos) resuelto con Sebas antes de escribir código, no asumido. **Alternativas consideradas:** Next.js conectado directo a Postgres (cliente TS: postgres.js/drizzle) — descartado por decisión explícita de Sebas: duplicaría en TypeScript la lógica de queries/tenant_id scoping que ya existe en Python, riesgo real de que diverjan.; Mostrar el contenido de documento_caso como texto plano (whitespace-pre-wrap) — descartado tras verificar en navegador que el markdown quedaba ilegible (## y ** literales) para el caso de uso central de la etapa ('ver los documentos que se generen').
- [ ] **Etapa 5 del plan — Conductor conversacional construido** (2026-08-16, Sebas + Claude). Construido conductor/ — arquitectónicamente distinto a los 5 agentes existentes (todos de un solo turno, contrato SEB-115): es conversacional, multi-turno, sin submit_* que marque el final. No se registra en agents_registry.yaml (no es un step de flow). 4 tools, todas mapeadas 1:1 a mecanismo ya construido: listar_casos/ ver_caso (el briefing de docs/PROTOCOLO_LECTURA_CONDUCTOR.md, Etapa 3, adaptado al modelo real de casos.yaml en vez del modelo oportunidad+flow que las primitivas de Etapa 2 asumían) y correr_microbiologo/ver_documento (invoca al especialista vía la costura, nunca directo). Sumadas 2 funciones chicas a utils/casos.py (obtener_frentes_de_caso/obtener_documentos_de_frente) para completar el paralelo de inspeccionar_caso en el modelo de casos.yaml. Resolución de identificadores por nombre/fragmento, no solo UUID. 14 unit + 1 integration test, 354/354 activos en verde, auditor sin ALTO/MEDIO nuevos. Verificado con sesión conversacional real de 3 turnos sobre Helios (no mock): listó los 2 casos reales correctamente, al preguntarle por Helios llamó ver_caso (no inventó el estado), reportó los pendientes reales del caso (reunión con Mateo, supuesto del flete sin confirmar) y recomendó no correr ningún análisis hasta resolver ese bloqueo — comportamiento equivalente al que Sebas ejerció a mano el 22/07. **Motivo:** Primer pedido explícito de Sebas al arrancar el plan de esta sesión: 'el Conductor es clave, no opcional'. Ya tenía sus dos prerrequisitos de diseño/mecanismo resueltos (Etapa 2: primitivas de invocación; Etapa 3: protocolo de lectura) y, tras la Etapa 4 de hoy mismo, un camino real de escritura contra casos.yaml para operar sobre el caso real. **Alternativas consideradas:** Forzar el Conductor al contrato SEB-115 (run(contract_input) -> dict de una sola llamada) — descartado: el contrato asume un resultado final estructurado tras un loop que termina; el Conductor es multi-turno por diseño, forzarlo hubiera roto exactamente lo que lo hace útil (memoria de la conversación).; Construir el Conductor contra el modelo oportunidad+flow (para reusar inspeccionar_caso/estimar_costo de Etapa 2 tal cual, sin funciones nuevas) — descartado: ningún caso real (Helios/MicroBigs) usa ese modelo hoy — hubiera sido diseño especulativo contra datos que no existen, en vez de construir contra el caso real disponible.
- [ ] **Etapa 4 del plan (parte 1) — staging real vía Neon branching** (2026-08-16, Sebas + Claude). Creado el branch 'staging' (copy-on-write de production) en el proyecto de Neon de CRIZA — verificado en vivo con datos idénticos a producción (37.215 fichas tenant_id='criza' + 6 'instancia_test' en ambos). DATABASE_URL_STAGING agregado a .env/.env.example. docs/STAGING.md documenta cuándo usar cada DB y cómo apuntar a staging (DATABASE_URL es lazy, alcanza con la env var + reset_engine() si el proceso ya se conectó). De paso: el proyecto de Neon se llamaba 'empresa-ia' (resabio de antes del 13/08, cuando CRIZA vivía anidada en el código de EMPRESAS-IA) — se renombró a 'criza'. Verificado antes de renombrar que no había mezcla de datos con otras instancias (solo tenant_id='criza' + un tenant de prueba insignificante) — el nombre viejo era un descuido cosmético de infraestructura, no un problema de aislamiento real. **Motivo:** Sebas pidió un ambiente de staging real (no verificación incremental) desde el arranque del plan del 16/08 — 'quiero que sea una copia separada, no solo verificar cada paso'. Se ubicó acá (no antes) porque es el primer momento del plan donde algo empieza a escribir contra el modelo de casos.yaml (Helios/MicroBigs reales) — antes de eso, todo el trabajo (Etapas 0-3) era construir agentes/primitivas nuevos o diseño puro, sin tocar datos de casos reales. **Alternativas consideradas:** Crear el branch vía la consola de Neon (Sebas, manual) — descartado tras encontrar que la cuenta de neonctl autenticada por defecto no tenía acceso a la org correcta; Sebas pidió explícitamente que se resuelva por CLI una vez identificada la cuenta correcta (criza.dev@gmail.com), no que lo haga él a mano.; Dejar el nombre del proyecto de Neon como 'empresa-ia' — descartado: Sebas pidió el rename explícitamente al notar la confusión con la org de EMPRESAS-IA.
- [ ] **Etapa 3 del plan de construcción del nuevo sistema — protocolo de lectura del Conductor (Caso B)** (2026-08-16, Sebas + Claude). Cerrado el diseño del 'Caso B' pendiente de PROPUESTA_DESTINO.md §11 — qué consulta el Conductor, en qué orden, y cómo arma contexto antes de responder cuando 'se despierta' sobre un caso. Documento nuevo: docs/PROTOCOLO_LECTURA_CONDUCTOR.md. 7 pasos en orden: (1) identidad del caso, (2) qué falta vía inspeccionar_caso (Etapa 2), (3) sanity check de que lo 'completo' tiene contenido real (no solo status=completo), (4) costo gastado + estimado restante vía estimar_costo (Etapa 2), (5) lecciones relevantes (aprendizaje.leer_lecciones_caso/proceso), (6) decisiones de sistema vigentes, (7) inconsistencias entre agentes que solo el Conductor puede ver (PROPUESTA_CONDUCTOR.md §3.1). Define también el shape del 'briefing' estructurado que el Conductor arma antes de generar su respuesta conversacional. Verificado corriendo los 7 pasos de verdad contra un caso real del KM (no solo diseñado en el papel) — la corrida real encontró y documentó un matiz genuino: inspeccionar_caso está acotado al flow que se le pasa, un especialista invocado directo (como el Microbiólogo hoy) no aparece ahí aunque su prop exista, el Conductor necesita el paso 1 (identidad completa) para no asumir que inspeccionar_caso de un solo flow es la vista completa. Declara explícitamente qué NO resuelve (decisiones de negocio dentro de un caso siguen sin lugar dedicado — gap conocido, no inventado). PROPUESTA_DESTINO.md §11 actualizado marcando Caso B resuelto. **Motivo:** PROPUESTA_DESTINO.md §11 dejó esto como requisito explícito 'para cuando se diseñe el Conductor (no antes)' — la Etapa 5 (construir el Conductor) no puede empezar sin esto resuelto primero, o se construye adivinando su propio protocolo de lectura, exactamente el riesgo que Sebas nombró al pedir esta etapa ('el Conductor es clave, no opcional'). **Alternativas consideradas:** Diseñar el protocolo dentro de PROPUESTA_CONDUCTOR.md (EMPRESAS-IA) — descartado: ese documento es de plataforma/pre-capa, y el contenido concreto de este protocolo (nombres de props, flows, funciones reales) es específico de CRIZA — va en criza/docs/, mismo criterio que PROPUESTA_DESTINO.md.; Resolver esto dentro de la implementación del Conductor (Etapa 5), sin documento separado — descartado: mezclaría diseño de protocolo con código de un agente conversacional nuevo, y el plan ya identificó esto como prerrequisito de diseño separado, no parte de la construcción.
- [ ] **Etapa 2 del plan de construcción del nuevo sistema — primitivas de invocación del Motor** (2026-08-16, Sebas + Claude). Sumadas 3 primitivas nuevas a orquestador/motor.py: inspeccionar_caso() ('qué le falta a un caso' como consulta explícita, generaliza armador._validar_cobertura_upstream a cualquier step de cualquier flow), estimar_costo() (promedia props.token_usage real de otras oportunidades, nunca inventa un número — sin histórico queda None, no un cero encubierto), y reanudar_desde() (generaliza reanudar(): reconstruye estado solo desde el KM persistido, sin depender del gate_data en memoria de un MotorResult anterior — funciona aunque la sesión que pausó el flow ya no exista, la primitiva real detrás de 'otra puerta de entrada' de PROPUESTA_CONDUCTOR.md §3.1). 21 tests nuevos (18 unit + 1 integration real contra el KM que verifica que reanudar_desde no re-invoca un step ya completo). orquestador/docs/DESIGN_GATE.md actualizado — se agregó §7 para las 3 primitivas nuevas y se documentó explícitamente que §1-6 describen el Orquestador v1 (LLM-driven, reemplazado) y no el Motor v2 real — deuda de reescritura completa anotada, no resuelta hoy. 319/319 tests activos, auditor 68 hallazgos (66 antes + 2 bajo esperados por texto de deuda en el Design Gate, mismo patrón que el resto de la sesión, sin ALTO/MEDIO nuevos). **Motivo:** Sebas: 'El Conductor es clave, no opcional' y sospecha que su ausencia fue parte de problemas previos. PROPUESTA_CONDUCTOR.md §5 exige estas 3 primitivas antes de construir el Conductor (Etapa 5) — construirlo sin ellas significaría adivinar su protocolo de invocación en vez de tenerlo resuelto de antemano. **Alternativas consideradas:** Construir el Conductor directamente y resolver estas primitivas sobre la marcha — descartado: el plan aprobado ya identificó estas 3 como prerrequisito explícito, resolverlas dentro del Conductor mezclaría diseño de infraestructura con diseño conversacional.; estimar_costo() con una tabla de precios fija por agente en vez de histórico real — descartado: viola 'veracidad por dato' (CLAUDE.md) — un número fijo no reflejaría que cada corrida real varía según cuántas tools use el agente.
- [ ] **Mercado es Anthropic-only — excepción permanente, no pendiente de migrar** (2026-08-15, Sebas). Definido con Sebas: Mercado NO se migra al traductor de proveedores (utils/ai_client.py) — queda 100% Anthropic directo, de forma permanente, no 'hasta que haga falta migrarlo'. Depende de la tool nativa `web_search_20250305` (búsqueda del lado del servidor de Anthropic), que no tiene equivalente en el formato de función que el traductor entiende (LiteLLM/formato OpenAI). Comentario agregado en market_agent/market_agent.py explicando la excepción para quien lea el código y se pregunte por qué este agente no sigue el mismo patrón que los otros 4. **Motivo:** Evita dejarlo como pendiente eterno sin resolución clara. La tool nativa es central para el Cruce 3 de Mercado (descubrir competidores/regulación reales) — cambiar de proveedor implicaría perder esa capacidad o reconstruirla distinto por proveedor, sin ningún driver real hoy que lo justifique. **Alternativas consideradas:** Dejarlo como 'pendiente de migrar cuando haga falta' — descartado por Sebas, prefiere una decisión cerrada a un TODO abierto sin fecha.
- [ ] **utils/tests resuelto — no colgaba de verdad, eran llamadas reales no mockeadas** (2026-08-15, Sebas + Claude). El 'cuelga' documentado el 13/08 era utils/tests/test_agrovoc.py haciendo llamadas reales a la API de AGROVOC en 10 tests que debían estar mockeados — parcheaban 'criza.utils.agrovoc._get' (prefijo 'criza.' de antes de la independización del 13/08, cuando el repo vivía anidado en EMPRESAS-IA/criza/), así que el mock no pegaba en el módulo real y corría la función de verdad. Sed reemplazando 'criza.utils.agrovoc.' por 'utils.agrovoc.' — de 16.88s (llamadas reales) a 0.17s. De paso, test_inta.py::test_harvest_con_fecha_filtra asumía que el parámetro from_date (mapea al 'from' de OAI-PMH, filtra por datestamp del repositorio) también filtraba el año de publicación del contenido — no es lo que el protocolo garantiza. Suavizada la aserción a lo que sí es cierto (la corrida no rompe y trae resultados). **Motivo:** utils/tests pasó de 'cuelga, sin investigar' a 30/30 passed (21 unit + 9 integration reales) en 22.94s, sin colgarse. **Alternativas consideradas:** —
- [ ] **Mejoras del motor del KM (docs/MEJORAS_KM.md) — evaluadas, diferidas** (2026-08-15, Sebas + Claude). Los 2 hallazgos de docs/MEJORAS_KM.md (conexiones tipadas no cruzan áreas; dedup_por debe coincidir con vectorizar) no bloquean nada hoy — ambos ya tienen un workaround funcionando en producción (participantes embebidos en props del caso; dedup_por: null donde hacía falta). No se arranca a tocar knowledge_module (Capa 1, compartido con DPN/Conflur/Biodarg) sin una necesidad real que lo justifique. **Motivo:** Pedido explícito de Sebas: evaluar si hace falta ahora antes de arrancar, no asumir que todo hallazgo hay que resolverlo en la misma sesión que se encuentra. Cambiar código de plataforma compartido con otras instancias necesita una razón real, no solo 'ya que estamos'. **Alternativas consideradas:** Arrancar a evaluar/construir el fix de knowledge_module hoy — descartado: sin necesidad real hoy, y es código compartido con otras instancias.
- [ ] **Deuda de tests de km_tools/tests resuelta — 6/28 verde pasó a 22/24 + 2 skips** (2026-08-15, Sebas + Claude). Reabierta la decisión del 13/08 (que la dejaba para sesión dedicada aparte) porque investigar el archivado del pipeline muerto (item 7 de hoy) reveló la causa concreta de la mayoría de las fallas — dejó de ser un misterio grande. Fix 1 (15 fallas): varios tests hacían patch("tools.store...")/patch("tools.search...") con el nombre de módulo previo al rename a km_tools — corregido a km_tools.store/km_tools.search. Fix 2 (2 fallas): 2 tests de integración reusaban una URL fija sin limpiarla, así que la segunda corrida contra el Neon real siempre fallaba (dedup funcionaba bien, el test no era idempotente) — ahora generan un uuid4() por corrida. Fix 3 (4 tests con "Event loop is closed" intermitente): faltaba reset_engine() antes de la primera query async — mismo patrón ya usado en otros tests de integración del repo (armador, market_agent). Fix 4 (2 tests): LocalEmbedder depende de sentence-transformers, que knowledge_module declara como extra OPCIONAL ([local-embeddings]), no dependencia base — CRIZA usa bgem3 en producción. Esos 2 tests ahora hacen pytest.importorskip en vez de fallar en rojo por un extra que nunca se pidió instalar. **Motivo:** km_tools/tests/ pasó de 6/28 verde a 22/24 passed + 2 skipped (justificados). utils/tests (que colgaba) queda fuera de esta resolución, sin investigar hoy. **Alternativas consideradas:** Instalar sentence-transformers para que los últimos 2 tests pasen en vez de saltear — descartado: es un extra opcional pesado (arrastra torch) que la instancia real no usa (EMBEDDING_PROVIDER=bgem3); requirements.txt de hoy ya excluyó torch por el mismo motivo.
- [ ] **Archivado el subsistema muerto del pipeline scout/divergente/convergente** (2026-08-15, Sebas + Claude). Movidos a _archivo_temporal/: server.py (MCP server legacy), ingest_corrida.py, ingest_historico.py, km_tools/retrieve.py. Removidas de km_tools/store.py y search.py las funciones store_corrida/store_opportunity/store_document/store_learning/_link_corrida/search_knowledge — sin consumidor real desde que divergent_agent/ se borró el 2026-07-02. km_models.py quedó solo con la clase Documento (Corrida/Oportunidad/Aprendizaje/CorridaOportunidad/CorridaDocumento archivadas). Las tablas correspondientes en Neon NO se tocaron — solo el código que las escribía/exponía. km_tools/tests/test_tools.py perdió los 4 tests de funciones archivadas, tests/test_ingest.py se archivó completo. **Motivo:** Encontrado al investigar por qué server.py estaba roto (item requirements.txt): sus 6 de 7 tools exponían un pipeline sin ningún consumidor vivo. Rastreado hasta confirmar que ingest_corrida.py e ingest_historico.py también dependían exclusivamente de ese mismo pipeline muerto — todo se originaba en el mismo punto: divergent_agent/ borrado el 02/07 sin limpiar lo que lo alimentaba/consumía. **Alternativas consideradas:** Solo instalar mcp y dejar server.py funcional — descartada por Sebas: quedaría exponiendo un pipeline que nada más usa.; No tocar nada, documentar como hallazgo para otra sesión — descartada por Sebas, eligió 'archivar y confirmar borrado' explícitamente.
- [ ] **requirements.txt en la raíz de criza/ (no existía)** (2026-08-15, Sebas + Claude). Armado a partir de un escaneo real de imports en todo el código: anthropic, litellm, python-dotenv, requests, pyyaml, pydantic, sqlalchemy, asyncpg, pgvector, modal (solo deploy), pytest, pytest-asyncio. Excluidos a propósito: torch/esm/fastapi/uvicorn (solo en scientific_agent/pod_server.py, RunPod ya reemplazado) y FlagEmbedding (corre dentro del contenedor de Modal). Hallazgo de paso sin resolver: server.py (KM legacy MCP server) importa mcp, no instalado — roto tal cual hoy, comentado en el archivo con nota. **Motivo:** Las dependencias se instalaban a mano en el entorno global sin manifiesto que las fijara — riesgo real de que un clon nuevo del repo no supiera qué instalar, más consecuente ahora que litellm es dependencia real de 3 agentes en producción. **Alternativas consideradas:** pip freeze completo del entorno — descartado: el entorno es global (sin venv), captura paquetes de otros proyectos ajenos a CRIZA.
- [ ] **Diseño concreto de la app: modelo de datos de caso + páginas (sin scaffold Next.js todavía)** (2026-08-15, Sebas + Claude). Área KM `casos` (config/plantillas/casos.yaml): tipo_ficha caso (nombre, descripcion, estadio, participantes embebidos), frente, pendiente, artefacto_externo, documento_caso (modo chat/documento — bisagra del §7.3), dato_extraido (contacto/cifra/plazo). 5 conexiones tipadas dentro del área. Páginas propuestas: / (lista de casos), /casos/[id] (frentes/pendientes/artefactos), /casos/[id]/frente/[id] (chat o documento), /casos/nuevo. Cargados los 2 casos reales (Biogás/Helios, MicroBigs) con datos sacados de casos/*.md — no inventados. **Motivo:** PROPUESTA_DESTINO.md §7: 7 ideas ya confirmadas por Sebas a partir de releer los 2 casos reales. El scaffold de Next.js en sí queda para una sesión propia con su Design Gate — esto es la parte de "diseño concreto" verificable hoy sin escribir frontend. **Alternativas consideradas:** Conexión tipada participa_en (usuario -> caso) — descartada otra vez por la misma restricción del loader (ver docs/MEJORAS_KM.md #1): se resuelve con participantes embebido en caso.props.; Construir también el scaffold de Next.js hoy — descartado: módulo nuevo, necesita su propio Design Gate por CLAUDE.md, alcance mucho mayor que una sesión.
- [ ] **Modelo de datos de usuarios/roles (sin auth real todavia)** (2026-08-15, Sebas + Claude). Area KM nueva usuarios (config/plantillas/usuarios.yaml): tipo_ficha usuario (nombre, email, rol_global, estado activo/invitado/inactivo, notas) + tipo_ficha rol (catalogo abierto: admin, colaborador, referente, observador). Sembrado real: Sebas (admin, activo), Pablo y Andres (referente, invitado, sin email — dueños de MicroBigs y Biogas respectivamente, sin acceso directo hoy). **Motivo:** PROPUESTA_DESTINO.md §9: dejar preparado sumar a Pablo/Andres mas adelante sin rediseñar, sin implementar login real todavia (uso actual: solo Sebas). **Alternativas consideradas:** Conexion tipada participa_en (usuario -> caso) en el mismo paso — descartada: el loader del motor exige que ambos extremos de una tipo_conexion se declaren en la misma plantilla, y hoy no existe todavia un nodo real de "caso" (el unico nodo real, oportunidad/descubrimiento, es flaco y de otra area). Se agrega cuando el item 3 (diseño de la app + modelo de datos de caso) defina esa ficha.; Tabla Postgres dedicada en vez de ficha JSONB del motor generico — descartada por ahora: no hay auth real todavia, no hace falta la integridad relacional estricta que pediria eso (unique email, FKs) hasta que se implemente login de verdad.
- [ ] **Registry data-driven + la costura de persistencia al KM** (2026-08-15, Sebas + Claude). orquestador/agents_registry.yaml (nuevo) reemplaza los imports hardcodeados de registry.py. orquestador/invocador.py (nuevo, 'la costura') persiste el resultado de cualquier agente al KM de forma genérica, sin que el agente tenga que acordarse. Los 4 agentes actuales se normalizaron a este contrato. Cerró dos gaps reales: Armador nunca había persistido su propio expediente, e Investigación Amplia duplicaba su informe en dos props. **Motivo:** Persistir el resultado dependía de que cada agente se acordara — causa exacta del bug real del 22/07 (Mercado corrió, costó plata, y su escritura era invisible para el Motor). Sin garantía estructural, cualquier especialista nuevo podía repetir el mismo error. **Alternativas consideradas:** Seguir con imports hardcodeados y persistencia por agente; Solo agregar tests que detecten el bug de nuevo, sin cambiar la arquitectura
- [ ] **Redefinición del objetivo de CRIZA: de blue-ocean-discovery a equipo asesor** (2026-08-14, Sebas). CRIZA deja de tener como propósito central 'encontrar blue oceans' — pasa a ser un equipo de agentes de IA asesores, con blue-ocean-discovery como capacidad invocable cuando el caso la amerita. Ver docs/PROPUESTA_DESTINO.md — borrador todavía sin cerrar, no reemplaza el Norte global de CLAUDE.md hasta que cierre. **Motivo:** El objetivo original ya cumplió su función — de ahí salieron proyectos reales (biogás vía Andrés, MicroBigs vía Pablo) que ahora necesitan acompañamiento continuo, no un expediente de inversión único. **Alternativas consideradas:** Mantener el objetivo original y tratar estos casos como excepción; Redefinir el propósito central del sistema
- [ ] **Rotar password de Neon** (2026-08-13, Sebas). Acción manual pendiente de Sebas — no es una tarea de desarrollo. **Motivo:** Buena práctica de seguridad tras la independización del repo. **Alternativas consideradas:** —
- [ ] **Auditor determinístico — 9 checks contra datos reales del KM y código fuente** (2026-07-22, Sebas + Claude). knowledge_module/auditor/ (Capa 1) + criza/auditor_registry.yaml (Capa 2, config). Verifica población de campos, cobertura de fuentes entre agentes hermanos, sampling no declarado, decisiones diferidas, contrato fuentes_y_cobertura, km_write_ausente, instancias no registradas, contrato_input_no_leido, km_conexion. 32/32 unit tests. **Motivo:** Verificación determinística, no LLM, contra el código y el KM reales — para no depender de que un humano se acuerde de revisar cada conexión a mano. **Alternativas consideradas:** Revisión manual periódica; Verificador determinístico
- [ ] **objetivo del Motor sigue decorativo — depende del diseño del Conductor** (2026-07-22, Sebas + Claude). El campo `objetivo` que arma el Motor al crear una oportunidad se guarda como texto pero no influye en ninguna decisión de ruteo — todo el ruteo real está pre-declarado en el YAML del flow. No se resuelve todavía. **Motivo:** Es la pregunta de fondo del diseño del Conductor (PROPUESTA_CONDUCTOR.md) — resolverla aislada, sin el Conductor definido, sería adivinar la forma final. **Alternativas consideradas:** Resolverlo ahora de forma aislada; Esperar a diseñar el Conductor completo
- [ ] **Auditoría de cumplimiento de plataforma — 51 hallazgos, revisión activa** (2026-07-05, Sebas). Revisión hallazgo por hallazgo en curso con Sebas. Temas 1-2 (git, docs desactualizados) y parte del Tema 3 (tenant hardcodeado) ya resueltos. Hallazgo central: el KM comparte una sola base entre instancias sin RLS (P11) — decidido volver a base separada por instancia. Detalle: EMPRESAS-IA/docs/AUDITORIA_CUMPLIMIENTO_2026-07-05.md. **Motivo:** No resolver nada de esto sin Sebas — varios ítems ya se corrigieron mal una vez por apurar la lectura. **Alternativas consideradas:** Resolver todo de una vez; Revisión hallazgo por hallazgo con Sebas
- [ ] **Renombrar carpeta EMPRESAS-IA/ (hoy KRIZA/ en disco)** (2026-07-01, Sebas). Pendiente — requiere migración de memoria de Claude antes de renombrar. **Motivo:** El nombre de carpeta quedó desactualizado tras sucesivos cambios de naming de la plataforma. **Alternativas consideradas:** —
<!-- GENERADO:ESTADO_OPERATIVO:FIN -->

---

## Knowledge Module — estado rápido

| Capa | Qué hace | Versión | Estado |
|---|---|---|---|
| DB (Neon) | 5 tablas: corrida, oportunidad, aprendizaje, documento, corrida_oportunidad, corrida_documento | v0.7 schema | ✅ live |
| ORM | SQLAlchemy async — solo `Documento` (`km_models.py`). `Corrida`/`Oportunidad`/`Aprendizaje`/`CorridaOportunidad`/`CorridaDocumento` archivadas 2026-08-15 — pipeline scout/agente divergente/convergente, sin consumidor real desde que ese agente se borró (02/07). Tablas en Neon sin tocar, solo el código. | v0.4 | ✅ |
| Ingesta interna | `ingest_corrida.py` — **archivado 2026-08-15** (`_archivo_temporal/`). Su punto de invocación automática (`divergent_agent/test_metodologia.py`) ya no existía desde el 02/07; nadie lo corría. | — | 🗄️ archivado |
| Ingesta externa | `tools/store.py::store_fuente_externa` + `batch_store_fuentes_externas` (ON CONFLICT DO NOTHING, atómico) — dedup por fuente_url, idempotente | v0.2 | ✅ 2026-06-27 |
| Harvest INTA | `criza/ingest/harvest_inta.py`: OAI-PMH → KM, CICVyA completo — **1.643 documentos en DB (`documento`)**. Taxonomía `tipo` corregida 2026-06-30: COLECCION_TIPO (24 col_ID → tipo) + fix bug `institutos` (s.text vs s.attrib). Distribución post-backfill: ~1.088 paper · 168 ponencia · 91 tesis · ~168 reporte · 9 parte_libro · 5 libro · 4 divulgacion · 1 folleto. | v0.2 | ✅ 2026-06-30 |
| Download PDFs INTA | `criza/ingest/download_pdfs.py`: descarga bitstreams open-access + extrae texto → `texto_completo` en KM. `_sanitize()` elimina null bytes y surrogates. **~984 docs con texto completo** (de 1.643; ~610 sin PDF público accesible). | v0.1 | ✅ 2026-06-29 |
| Migración INTA → corpus_cientifico | `criza/ingest/migrate_inta_to_corpus.py`: copia `documento` (agente=harvest) → `ficha/corpus_cientifico` con embeddings BGE-m3, sin tocar `documento`. **1.643/1.643 migrados, 0 errores**. Cierra el gap de búsqueda semántica que INTA no tenía (solo FTS). `documento` queda como fuente de `get_sector_corpus` (FTS exhaustivo); `corpus_cientifico` como fuente de `search_corpus_cientifico` (semántico, filtrable por `repositorio`). Costo Modal: ~$0,003/registro (CPU-only, no GPU). **Gap encontrado 2026-07-02: `_doc_a_campos` migraba metadata pero descartaba `texto_completo` — 1.643/1.643 fichas quedaron con el campo vacío pese a que ~984 lo tenían en `documento`.** Fix: bug corregido en el script (para migraciones futuras) + `criza/ingest/backfill_inta_texto_completo.py` (nuevo) parcheó las 1.643 fichas ya existentes vía `motor_api.actualizar_props` (no re-vectoriza). **Backfill real: 984/1.643 actualizadas, 659 sin match en `documento` (genuinamente sin PDF), 0 errores.** | v1.1 | ✅ 2026-07-02 |
| `oai_pmh.py` — open_access | `knowledge_module/connectors/oai_pmh.py`: detecta `dc:rights` en el harvest OAI-PMH — verificado en vivo contra CONICET (vocabulario eu-repo). Genérico, sirve para cualquier repositorio DSpace (CONICET, INTA si se re-cosecha, futuro). | v1.1 | ✅ 2026-07-02 |
| Full-text CONICET (+genérico) | `knowledge_module/ingesta/download_corpus_pdfs.py`: para fichas `open_access=true` sin `texto_completo`, scrapea la landing page (patrón DSpace bitstream, descarta links `isAllowed=n`), descarga+extrae. Bulk, no bajo demanda — cierra gap de sesgo donde el agente decidía discrecionalmente qué texto leer. `_sanitize()` reusa el fix de null bytes de `download_pdfs.py` (INTA). `find_pdf_access()` distingue 3 estados (no 2): descargable / **requiere_solicitud** (con `solicitud_url` autoservicio "Consultar", o sin ella si es bitstream `isAllowed=n` — hay que pedirlo a mano, ej. contacto CONICET) / nada — declarado siempre, nunca en silencio (verificado a mano por Sebas, 3 casos reales). `get_ficha_full_text` surfacea el estado real en el error, no un "no disponible" genérico. **Backfill final: 430/625 con texto completo (68,8%) · 162/625 requiere solicitud (11 con autoservicio, 151 sin) · 33/625 genuinamente sin nada.** Motivado por auditoría de sesgos 2026-07-02, ver `orchestration-layer.md` Decisión 6. | v1.1 | ✅ 2026-07-02 |
| Chunking corpus_cientifico | `knowledge_module/motor/chunking.py::chunk_texto()` (Capa 1, ~500 tokens/50 overlap, respeta párrafos, 8 unit tests) + `fuente_chunk`/`chunk_de` en `criza/config/plantillas/corpus_cientifico.yaml` (Capa 2, mismo patrón que `norma_chunk`/`chunk_de` de DPN) + `criza/ingest/chunk_corpus.py` (backfill + ingesta). Cierra hallazgo P13 (auditoría 2026-07-05): texto_completo ya no se trunca a 60k chars (cap removido de `download_pdfs.py` y `download_corpus_pdfs.py`) y es buscable por fragmento, no solo por título/abstract. **Completo: 1.414/1.414 fuentes con texto_completo, 34.857 fragmentos, 0 huérfanos.** En el camino: la DB Neon llegó a su límite de 512MB (resuelto con upgrade a plan Launch, ~$2-6/mes real medido) y `asyncio.gather` sin límite al crear conexiones `chunk_de` dejó 1.141 chunks temporalmente sin conexión (agotamiento del pool — fixeado con semáforo de 5, y reparados por matching de contenido normalizado). Se sacó también `texto_vectorizado` de `ficha` (Capa 1 — `migrations/006_drop_texto_vectorizado.sql`, aplicada a CRIZA y DPN): duplicaba `props` sin que nada lo leyera. Detalle completo en `criza/docs/architecture.md` [2026-07-06] y [2026-07-07], `criza/docs/progress/2026-07-06.md` y `2026-07-07.md`. | v1.1 | ✅ |
| FTS | `fts_vector` GENERATED STORED + GIN index; `search_fuentes_externas` (FTS sobre Documento); 8/8 tests `test_batch_store.py` | v0.1 | ✅ 2026-06-27 |
| MCP server | `server.py` — **archivado 2026-08-15** (`_archivo_temporal/`). 6 de sus 7 tools exponían el pipeline scout/divergente/convergente (dead code); además importaba `mcp`, no instalado — ya estaba roto. Si hace falta un MCP server sobre lo que sigue vivo (`search_fuentes_externas`), arrancar de cero, no restaurar este. | — | 🗄️ archivado |
| Embeddings | BGE-m3 self-hosted en Modal, 1024 dims | prod | ✅ SEB-121 — swap completo, 44 filas migradas |
| Pre-flight genérico | `knowledge_module/preflight.py`: `FuenteCheck`/`run_preflight()` — patrón objective-first (bloqueante/advertencia) generalizado de investigacion_amplia a los 4 agentes. Ver `docs/orchestration-layer.md` Decisión 6. | v1.0 | ✅ 2026-07-02 — **6/6 unit tests** |
| Tests | `km_tools/tests/` — 22/24 passed + 2 skipped (justificado, extra opcional sin instalar). Deuda del 13/08 resuelta el 15/08: rename `tools.`→`km_tools.` en patches viejos, `reset_engine()` en tests de integración, URLs únicas en vez de fijas. `utils/tests` (que colgaba) sigue sin investigar. | — | ✅ 2026-08-15 |

---

## Dónde están las cosas

CRIZA es su propio repo (`Plataformas/criza/`), independiente de `EMPRESAS-IA/` (plataforma,
repo separado) y de `knowledge_module` (instalado por pip, no es carpeta hermana — ver
`pip install -e` en la sección de abajo).

```
criza/                          ← este repo: CRIZA-biotech (Capa 2)
    ├── agents.md                ← este archivo
    ├── .env                     ← DATABASE_URL, EMBEDDING_*, ANTHROPIC_API_KEY (propio, no versionado)
    ├── docs/
    │   ├── architecture.md      ← decisiones técnicas del sistema CRIZA
    │   └── progress/            ← logs de sesión (YYYY-MM-DD.md)
    ├── utils/
    │   ├── agrovoc.py           ← cliente AGROVOC (FAO tesauro) — expand_term
    │   ├── inta.py              ← conector INTA Digital (OAI-PMH + discover)
    │   └── openalex.py          ← cliente OpenAlex
    ├── ingest/
    │   └── harvest_inta.py      ← orquestador harvest: OAI-PMH → KM (CICVyA 1640 registros)
    ├── divergent_agent/
    │   └── test_metodologia.py  ← agente divergente + auto-ingesta en KM
    ├── convergent_agent/
    │   ├── convergent_agent.py  ← agente convergente (embudo N→1)
    │   ├── km_selector.py       ← el seam: selección de input desde el KM (Auto/Manual)
    │   ├── run.py               ← runner + ingesta 3 capas
    │   ├── ROADMAP.md · docs/DESIGN_GATE.md
    │   └── tests/               ← 12 unit + 2 integration
    ├── scientific_agent/        ← fusionado el 2026-08-14 (era repo separado, historial preservado)
    │   ├── ROADMAP.md           ← estado del agente científico (fuente de verdad)
    │   ├── specialist_proteins.py · run.py
    │   ├── tools/               ← 9 tools (OpenAlex, UniProt, ESMFold, etc.)
    │   └── tests/               ← 110 unit + 32 integration
    ├── market_agent/
    │   ├── ROADMAP.md · docs/DESIGN_GATE.md
    │   ├── market_agent.py · run.py
    │   ├── tools/               ← 6 tools (corpus CONICET, series, stats, web, email, corpus)
    │   └── tests/               ← 32 unit (8 nuevos v1)
    ├── investigacion_amplia/
    │   ├── investigacion_amplia.py  ← 5 tools; cruce 3 + mapa_candidatos; SEB-146
    │   ├── docs/DESIGN_GATE.md      ← decisiones de diseño, 🟡 Listo con deuda
    │   └── tests/               ← 18 unit tests
    ├── orquestador/
    │   ├── orquestador.py       ← v1 LLM puro (legacy)
    │   ├── motor.py             ← v2 motor YAML declarativo (SEB-197) ✅
    │   ├── registry.py          ← lazy imports de todos los agentes
    │   ├── flows/
    │   │   ├── pipeline_dolor.yaml   ← dolor → market + evidence + armador
    │   │   └── pipeline_sector.yaml  ← sector → IA + gate humano + market + evidence + armador
    │   ├── docs/DESIGN_GATE.md · DISEÑO_MOTOR_ORQUESTADOR.md
    │   └── tests/               ← 28 unit (motor v2)
    ├── armador/
        ├── ROADMAP.md · docs/DESIGN_GATE.md
        ├── armador.py · run.py
        └── tests/               ← 14 unit
    ├── microbiologo_agent/      ← primer especialista de la biblioteca (2026-08-16), casos.yaml-conectado
    │   ├── microbiologo_agent.py · run.py
    │   ├── docs/DESIGN_GATE.md  ← decisiones A-G
    │   └── tests/
    ├── conductor/                ← agente conversacional (2026-08-16) — NO contrato SEB-115, NO en
    │                               agents_registry.yaml (multi-turno, no es step de flow)
    │   ├── conductor.py · run.py (REPL interactivo)
    │   ├── docs/DESIGN_GATE.md  ← decisiones A-D
    │   └── tests/
    └── utils/casos.py            ← helpers del modelo casos.yaml (frente/pendiente/documento_caso),
                                     genérico, usado por microbiologo_agent y conductor

knowledge_module (Capa 1 — memoria semántica compartida): repo propio, `github.com/sebasbizzi/
km-knowledge-module`, instalado por pip en modo editable. Comando exacto verificado post-move
(2026-08-14, `criza/` y `knowledge_module/` ya no son carpetas hermanas):
`pip install -e "C:\Users\sebab\Documents\Plataformas\EMPRESAS-IA\knowledge_module"`. Detalle de
su estructura interna: `knowledge_module/docs/KM_DESIGN_GATE.md` en ese repo, no acá.
```

> Nota: el árbol de arriba (dentro de `criza/`) quedó desactualizado en algunos puntos antes de
> esta migración (menciona `divergent_agent/`, `convergent_agent/` — ya borrados, ver sección
> "Borrado" abajo) — no se resincronizó entero en este cambio, solo se corrigió que `criza/` deje
> de mostrarse como subcarpeta de `EMPRESAS-IA/`.

---

## Convención para agregar un nuevo agente

Seguir esta estructura y checklist exactos para que cualquier agente nuevo sea plug-in.

### Estructura de archivos

```
nuevo_agente/
├── nuevo_agente.py    ← TOOLS + SYSTEM_PROMPT + dispatch_tool() + run_agent()
├── run.py             ← runner interactivo con casos de ejemplo
├── ROADMAP.md         ← versiones, tools activas, estado, próximos pasos
├── .env.example       ← ANTHROPIC_API_KEY + NUEVO_MODEL + keys específicas
├── requirements.txt
├── tools/
│   ├── __init__.py    ← exports de todas las tools
│   └── <tool>.py      ← una tool por archivo, retorna dict estándar
└── tests/
    ├── __init__.py
    ├── conftest.py    ← fixtures + markers (unit / integration)
    └── test_<tool>.py ← un archivo por tool
```

### Contrato estándar de agentes (SEB-115 — obligatorio para todos los agentes nuevos)

Todo agente debe exponer en su módulo principal:

```python
INPUT_CONTRACT  = {"agent": str, "version": str, "fields": {caso, tarea, contexto, conocimiento, herramientas}}
OUTPUT_CONTRACT = {"agent": str, "version": str, "fields": {análisis, nivel_confianza, recomendaciones, próximo_agente, nuevo_conocimiento}}

async def run(contract_input: dict, verbose: bool = False, model: str = DEFAULT_MODEL) -> dict:
    """Interfaz de contrato estándar para el Orquestador. Wraps run_agent()."""
    ...
```

- `próximo_agente`: `None` si el Orquestador decide routing, nombre del agente si el agente mismo sabe (e.g. `"cientifico_especialista"` del Evidence Generalista)
- `nivel_confianza`: `"alto" | "medio" | "bajo"` derivado de los estados epistémicos del output
- `nuevo_conocimiento`: lista de strings → van al loop de aprendizaje

### Contrato de output de tools (obligatorio)

```python
{
    "success": bool,
    "data": ...,           # el resultado útil
    "source": "...",       # "[VERIFICADO]" | "[ESTIMADO, fuente: X]" | "[INFERIDO]"
    "error": str | None,   # None si success=True, mensaje claro si False
}
```

### Checklist de creación (= Definition of Done del agente)

1. Estructura de archivos según template
2. SYSTEM_PROMPT con workflow obligatorio + etiquetas de confianza en output
3. Tools en `tools/` con contrato estándar de output
4. Tests: unit con mocks + al menos 1 integration por tool → todos pasando
5. `.env.example` completo
6. `ROADMAP.md` con versión inicial, tools, próximos pasos
7. Agregar entrada en tabla "Agentes activos" de este `agents.md`
8. Issue en Linear → Done con DoD verificado

---

## REGLAS OPERATIVAS — no modificar, no borrar

> Esta sección se lee en cada sesión y permanece fija durante toda la vida del proyecto.

### Definition of Done

Una tarea de código está Done cuando:

- [ ] El código funciona según lo especificado
- [ ] Tiene tests para funciones críticas
- [ ] No hay credenciales expuestas en el código
- [ ] **Si la tarea generó una decisión de arquitectura/desarrollo de CRIZA → registrada en
      `decisiones_sistema` (KM) vía `scripts/km_decisiones.registrar_decision(...)` y
      `python scripts/generar_agents_md.py` corrido para que "Agentes activos" y "Estado
      operativo" la reflejen. Obligatorio, no discrecional — mismo criterio que
      `architecture.md` ("registrar en el momento de la decisión", no "después"). Esas dos
      secciones **no se editan a mano** (decisión 2026-08-15, ver `docs/progress/2026-08-15.md`
      — la edición manual fue la causa de que se desactualizaran). Si terminaste la sesión y no
      corriste el generador tras una decisión nueva, la sesión no está cerrada.**
- [ ] La sesión está documentada en `docs/progress/YYYY-MM-DD.md`

Verificar esta lista ANTES de mover un issue a Done en Linear.

### SDLC — fases activas

No avanzar a la siguiente fase sin confirmar que la anterior está resuelta:

Planificación → Requerimientos → Diseño → Desarrollo → Testing → Deployment → Mantenimiento

### Seguridad mínima siempre activa

- Nunca hardcodear credenciales. Siempre variables de entorno.
- `.env` siempre en `.gitignore` antes del primer commit.
- Antes de cada commit: verificar que no hay credenciales expuestas.

### Linear — workflow

- Al iniciar tarea → In Progress
- Al completar tarea → verificar DoD → Done → avisar al usuario y esperar instrucción
- Issues no completados al cerrar cycle → vuelven a backlog, no se arrastran solos
