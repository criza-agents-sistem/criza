# Protocolo de lectura del Conductor

**Estado:** diseño cerrado, sin código — prerrequisito de la Etapa 5 (construir el Conductor).
**Fecha:** 2026-08-16
**Resuelve:** el "Caso B" pendiente de `docs/PROPUESTA_DESTINO.md` §11 — "definir qué consulta,
en qué orden, y cómo arma contexto antes de responder [el Conductor] — no asumir que 'estar bien
estructurado en el KM' es suficiente."

---

## 1. Por qué esto es un documento aparte y no se resuelve "en el aire"

`PROPUESTA_CONDUCTOR.md` §4.1 ya mostró, con un caso real (22/07), que un KM bien diseñado no es
contexto suficiente: el prop de Mercado existía en el código pero nunca llegó a persistirse, y un
Conductor leyendo el KM ese día habría concluido "mercado no corrió" — falso, y caro (la reacción
natural es volver a correrlo, re-pagando tokens ya gastados).

Ese bug puntual ya está resuelto (la costura persiste siempre, `orquestador/invocador.py`,
2026-08-15). Pero la lección generaliza: **"el dato está en el KM" y "el Conductor lo leyó
correctamente en el orden correcto" son dos cosas distintas.** Este documento fija la segunda,
para que la Etapa 5 no tenga que inventar su propio protocolo de lectura sobre la marcha.

---

## 2. Principios que este protocolo tiene que respetar (ya decididos, no se reabren acá)

- **Dos puertas de entrada** (`PROPUESTA_CONDUCTOR.md` §3.1) — el Conductor no media la
  invocación, la observa. Todo lo que lee acá ya es visible para cualquiera con acceso directo al
  KM; el Conductor no tiene datos privilegiados, tiene el trabajo de armarlos en un mismo lugar.
- **La atención de Sebas es el recurso escaso** (§3.2) — el Conductor tiene que llegar con la
  decisión masticada: qué falta, qué cuesta, qué riesgo hay. Un protocolo que solo junta datos
  crudos y se los pasa a Sebas sin destilar traslada el trabajo en vez de sacarlo.
- **Derivado, nunca cacheado en prosa** (§4.3) — cada vez que el Conductor "se despierta" sobre un
  caso, deriva el estado desde las fuentes reales (KM, tests, histórico de tokens). Nunca lee un
  resumen previo como si fuera la verdad actual — un resumen puede haber quedado desactualizado
  desde que se escribió.
- **Veracidad por dato** (`CLAUDE.md`) — un step marcado `"status": "completo"` en
  `pipeline_status` no es, por sí solo, evidencia de que el resultado tiene contenido útil. El
  protocolo verifica que `props[prop_key]` no esté vacío antes de darlo por bueno — la misma
  clase de bug que causó el problema del 22/07 (algo "corrió" pero no dejó nada real) puede
  repetirse de otra forma si no se chequea.

---

## 3. El protocolo — qué consulta, en qué orden

Cuando el Conductor recibe un `oportunidad_id` (o, después de la Etapa 4, un `caso_id`) y necesita
armar contexto antes de responder, ejecuta estos pasos en este orden. Cada paso ya tiene una
función real que lo resuelve — ninguna es nueva, la Etapa 3 no inventa mecanismo, ordena el que
ya existe (la mayoría, construido en la Etapa 2 de este mismo plan):

| # | Qué | Cómo (función real) | Por qué en este orden |
|---|---|---|---|
| 1 | **Identidad del caso** | `motor_api.obtener(oportunidad_id, tenant)` | Sin esto no hay nada más que consultar — falla rápido y explícito si el id no existe, en vez de que un paso posterior falle con un error confuso. |
| 2 | **Qué está completo y qué falta** | `orquestador.motor.inspeccionar_caso(flow, oportunidad_id, tenant, registry)` | Es la pregunta que más rápido cambia la respuesta que da el Conductor — "¿qué le falta a esto?" es literalmente la primitiva que la Etapa 2 construyó para esto. No se infiere mirando `pipeline_status` a mano — eso es exactamente el tipo de derivación manual que un bug futuro puede hacer mal. **Nota verificada en vivo (2026-08-16):** `inspeccionar_caso` está acotado al `flow` que se le pasa — un especialista invocado directo (fuera de cualquier flow, ej. el Microbiólogo hoy) no aparece en `completos`/`pendientes` aunque su prop exista en el KM. El paso 1 (identidad, `props` completo) es la fuente que sí ve cualquier prop sin importar si vino de un flow o de una invocación directa — el Conductor no puede asumir que `inspeccionar_caso` de un solo flow es la vista completa del caso. |
| 3 | **Sanity check de lo "completo"** | Para cada step en `inspeccion.completos`: `bool(props.get(prop_key))` ya no alcanza (`inspeccionar_caso` ya lo exige) — pero además chequear que `props[prop_key].get("informe_completo")` no esté vacío. Un prop presente con `informe_completo=""` es la versión moderna del bug del 22/07: el paso corrió, escribió *algo*, pero no dejó nada usable. | Evita que el Conductor le diga a Sebas "esto ya está" sobre un resultado vacío o truncado. |
| 4 | **Costo ya gastado + costo de lo que falta** | Gastado: `props.token_usage` (ya está en el prop de identidad del paso 1). Falta: `orquestador.motor.estimar_costo(flow, oportunidad_id, tenant, registry)` | El Conductor necesita los dos números juntos para la pregunta real de Sebas: "¿vale la pena seguir?" — no alcanza con saber cuánto se gastó, hace falta saber cuánto falta. |
| 5 | **Lecciones relevantes** | `aprendizaje.leer_lecciones_caso(consulta=descripcion_del_caso, agente=None, tenant=...)` (búsqueda semántica — mismo patrón que ya usa `bloque_lecciones_para_prompt` en cada agente) + `aprendizaje.leer_lecciones_proceso(agente=...)` para cada agente en `inspeccion.pendientes` | Antes de recomendar correr un agente, el Conductor debería saber si ya hay una lección de proceso conocida sobre ese agente (ej. "buscar 'organic load' en vez de 'organic matter'", del Microbiólogo) — evita repetir un error ya documentado. |
| 6 | **Decisiones de sistema vigentes que puedan afectar la interpretación** | `scripts.km_decisiones.listar_decisiones_vigentes()` (sin filtro de componente, o filtrado por los componentes relevantes al caso) | Una decisión de arquitectura reciente (ej. "Mercado usa Anthropic-only") puede cambiar cómo interpretar por qué un resultado se ve de cierta forma — el Conductor no debería sorprenderse por algo que el sistema ya decidió a propósito. |
| 7 | **Inconsistencias entre agentes — lo que SOLO el Conductor puede ver** (`PROPUESTA_CONDUCTOR.md` §3.1) | Comparar, para cada step ya completo, su `próximo_agente` (guardado en `pipeline_status.steps.<id>`) contra si el step siguiente del flow realmente lo tuvo en cuenta (¿el `routing` lo enrutó, o el agente recomendado está en `no_disponible` y se saltó en silencio?). | Este es el hallazgo central de §3.1: "el 22/07, solo el Conductor notó que Evidencia pidió un especialista y el pipeline lo salteó". `inspeccionar_caso` ya expone `no_disponibles` — este paso cruza esa lista contra los `próximo_agente` pedidos para detectar el patrón, no solo reportar cada dato por separado. |

**Paso opcional 8 — solo si el caso ya está conectado a `casos.yaml` (post Etapa 4):** agregar
`motor_api.conexiones_de(caso_id, tipo_conexion="tiene_pendiente")` y `"tiene_frente"` para traer
pendientes/frentes del modelo de casos. Mismo principio (derivar, no cachear) — se agrega como
paso adicional, no reemplaza los pasos 1-7, porque `oportunidad` (discovery) y `caso` (el caso que
CRIZA acompaña) son conceptos relacionados pero no fusionados hoy (ver `casos.yaml`, nota de
diseño: "no hay conexión formal caso↔oportunidad todavía").

---

## 4. Cómo arma contexto antes de responder

El output de los 7 (u 8) pasos no se le pasa a Sebas crudo — el Conductor arma un **briefing
estructurado**, no una prosa libre, con esta forma (esto es lo que la Etapa 5 implementa como el
"contexto" que arma antes de generar su respuesta conversacional):

```
BriefingCaso:
  identidad: {nombre, descripcion, estadio}
  completo: [step_id, ...]          # con sanity check pasado (paso 3)
  pendiente: [step_id, ...]
  no_disponible: [step_id, ...]     # agentes inactivos/no registrados
  costo_gastado: int
  costo_estimado_restante: int | None   # None si falta histórico — nunca inventado
  lecciones_aplicables: [{agente, leccion}, ...]
  decisiones_de_sistema_relevantes: [{titulo, decision, fecha}, ...]
  inconsistencias: [{step_id, próximo_agente_pedido, qué_pasó}, ...]   # el hallazgo del §3.1
```

Sobre esta estructura, y solo sobre ella, el Conductor (Etapa 5) genera la respuesta
conversacional — la "decisión masticada" que pide §3.2: la pregunta, las opciones, el costo. El
briefing es determinístico (mismo caso, mismo estado del KM → mismo briefing); la conversación
sobre el briefing es donde entra el LLM.

---

## 5. Qué NO resuelve este protocolo (honestidad explícita, no se inventa)

- **Decisiones de negocio dentro de un caso** (ej. "descartamos el enfoque de microalgas porque
  el costo de escalado no cierra") no tienen hoy un lugar dedicado donde vivir — `pipeline_status`
  + `props` registran *qué corrió*, no *qué se decidió y por qué* sobre el contenido. Esto es
  distinto de `decisiones_sistema` (que es sobre arquitectura de CRIZA, no sobre un caso
  puntual). **Gap conocido, no resuelto en esta etapa** — si se vuelve un problema real de uso
  (Sebas necesita que el Conductor recuerde una decisión de negocio pasada sobre un caso), hace
  falta una nueva área KM o un campo dedicado — no se diseña en abstracto sin un caso real que lo
  pida, mismo criterio que el resto de esta sesión.
- **No decide qué hacer con las inconsistencias que detecta** (paso 7) — igual que
  `PROPUESTA_CONDUCTOR.md` §9 decisión 6 (abierta): el Conductor las marca y las registra, no las
  bloquea ni las resuelve solo. Eso lo decide Sebas en la conversación, no el protocolo de lectura.
- **No agrega ninguna primitiva de escritura** — es un protocolo de lectura. Invocar un agente
  (escribir al KM) sigue pasando por la costura existente, sin cambios.

---

## 6. Verificación de este diseño

Al no ser código, la verificación es distinta a la del resto del proyecto: se corrieron los 7
pasos del protocolo **de verdad**, en orden, contra un caso real del KM (`oportunidad_id` de una
de las corridas de verificación de Etapa 1) — no se citó ninguna función en este documento sin
haberla ejecutado primero. Confirmado: identidad (paso 1), `inspeccionar_caso` (paso 2, resultado
real: `pendientes=['market','evidence','armador']`, `no_disponibles=['especialista']`),
`estimar_costo` (paso 4, `estimado restante: 546054` tokens, basado en histórico real), 4
lecciones de caso + lecciones de proceso reales encontradas (paso 5), 18 decisiones de sistema
vigentes leídas (paso 6), chequeo de inconsistencias corrido sin error (paso 7). La corrida real
fue lo que encontró el matiz de scoping documentado arriba en el paso 2 (`inspeccionar_caso` está
acotado a un `flow`) — no se habría detectado solo leyendo el código.
