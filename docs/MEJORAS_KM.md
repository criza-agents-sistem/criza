# Oportunidades de mejora para el Knowledge Module (Capa 1)

> Hallazgos reales, encontrados usando el KM desde CRIZA — no ideas en abstracto. Cada entrada
> nace de un problema concreto que apareció construyendo algo real, con la fecha y el contexto
> en que se encontró. Vive en `criza/docs/` (el consumidor que lo descubre) porque el código del
> motor está en el repo separado `github.com/sebasbizzi/km-knowledge-module` — cuando alguien
> trabaje una de estas, se traslada el hallazgo a ese repo o se resuelve desde ahí.
>
> **No son bugs** (el motor funciona como está documentado) — son límites de diseño que no se
> habían probado hasta que un caso de uso real los tocó. Ninguna se resuelve sin decidirlo con
> Sebas primero — mismo criterio que el resto del proyecto.

> **Evaluado el 2026-08-15: ninguna de las dos bloquea nada hoy.** Ambas se esquivaron con un
> workaround que funciona bien (participantes embebidos en `props` en vez de conexión tipada;
> `dedup_por: null` en vez de declarar algo que no deduplica). Queda para la próxima
> planificación, cuando aparezca una necesidad real que las requiera — no antes. Decisión
> `componente=infra` en `decisiones_sistema`.

---

## 1. Las conexiones tipadas (`tipo_conexion`) no pueden cruzar áreas

**Encontrado:** 2026-08-15, dos veces en la misma sesión — al diseñar `usuarios.yaml` (ítem 4,
`PROPUESTA_DESTINO.md` §9) y de nuevo al diseñar `casos.yaml` (ítem 3, §7).

**El problema, concreto:** `knowledge_module/motor/loader.py::load_plantilla` valida que
`desde`/`hacia` de una `tipo_conexion` sean nombres de `tipo_ficha` **declarados en la misma
plantilla YAML que se está cargando** (`tipos_validos = {tf["nombre"] for tf in
spec.get("tipos_ficha", [])}`, construido solo a partir del spec actual, no contra el registro
global de tipos en la DB). Esto significa que no hay forma de declarar una conexión tipada entre
una ficha de un área y una ficha de otra área — por ejemplo, `usuario` (área `usuarios`) →
`caso` (área `casos`) no se puede declarar como conexión tipada, aunque ambas áreas y ambos
tipos existan y estén cargados correctamente en la DB.

**Nota aparte:** a nivel de datos, `guardar_conexion()` (en `motor/api.py`) sí inserta el edge
entre dos IDs de ficha cualesquiera sin verificar que coincidan con el `tipo_ficha_id` real de
esas fichas — la restricción es solo del *loader* al declarar el tipo de conexión, no del motor
de escritura. Es decir, el motor **podría** soportar conexiones cross-área si el loader
validara contra el registro global (`tipo_ficha` de la DB) en vez de contra el spec local.

**Impacto real, hoy:** la relación "quién participa en qué caso" (`participa_en`, pensada al
diseñar el ítem 4) tuvo que resolverse embebiendo una lista de participantes en
`caso.props.participantes` en vez de como conexión tipada — funciona para lo que hace falta hoy
(saber quién participa en qué caso), pero pierde la trazabilidad de grafo (no se puede hacer un
join tipo "todos los casos donde participa Pablo" sin recorrer `props` a mano, y no hay
integridad referencial sobre esos IDs de usuario embebidos).

**Posible arreglo (no evaluado en profundidad, no decidido):** que `load_plantilla` valide
`desde`/`hacia` contra el registro global de `tipo_ficha` de ese `tenant` en la DB (cualquier
área), no solo contra el spec que se está cargando — permitiría declarar conexiones cross-área
siempre que ambos tipos ya existan (cargados en cualquier orden, con una validación clara si
falta uno). Impacto en otras instancias: cualquiera que modele "usuarios" y "entidades del
dominio" como áreas separadas (patrón razonable, no específico de CRIZA) se topa con esto.

**Prioridad sugerida:** baja-media. No bloquea nada hoy (el workaround de props funciona), pero
si más instancias empiezan a modelar usuarios/accesos con el motor genérico, va a repetirse.

---

## 2. `dedup_por` exige que sea el mismo campo que `vectorizar` — y sin `vectorizar` no dedup nada

**Encontrado:** 2026-08-15, al cargar `casos.yaml` — `guardar_ficha()` explota con
`"dedup_por ('nombre') debe coincidir con vectorizar ('texto_busqueda') — caso distinto no
soportado aún"` (mensaje real del motor, `motor/api.py` línea ~57) cuando se declara
`dedup_por` distinto de `vectorizar`.

**El problema, concreto:** la deduplicación por similitud (`guardar_ficha`) solo puede
comparar el campo que ya se vectorizó — no hay forma de deduplicar por un campo A mientras se
vectoriza (para búsqueda semántica) un campo B distinto, aunque sea razonable querer las dos
cosas (ej. "buscar semánticamente por descripción, pero deduplicar por nombre exacto"). Además,
declarar `dedup_por` en un tipo que tiene `vectorizar: null` **no falla, pero tampoco hace
nada** — el chequeo de dedup solo corre si hay un `embedding` calculado, así que un
`dedup_por` sin `vectorizar` es una declaración silenciosamente inerte, no un error. Las dos
plantillas de hoy (`casos.yaml`) terminaron con `dedup_por: null` en los tipos que lo hubieran
necesitado (`caso`, `artefacto_externo`) para evitar ambos problemas.

**Posible arreglo (no evaluado, no decidido):** o bien permitir vectorizar y deduplicar por
campos distintos (calculando un embedding separado solo para dedup si hace falta), o al menos
que el loader rechace a tiempo de carga un `dedup_por` declarado sin `vectorizar` — hoy falla
en silencio en vez de avisar que no va a hacer nada.

**Prioridad sugerida:** baja. Es más una aspereza de la API que un bloqueador — una vez que se
sabe la regla, es fácil evitarla (como se hizo hoy).
