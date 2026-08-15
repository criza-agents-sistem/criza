# Propuesta — Destino de CRIZA (borrador para discutir)

> **Estado:** borrador para discutir, no una decisión cerrada. No reemplaza el Norte global de
> `CLAUDE.md` todavía — se coloca ahí cuando cierre la conversación.
>
> **Origen:** sesión 2026-08-14, inmediatamente después de aislar CRIZA como repo propio y
> relevar su estado real (agentes, servicios, conexiones — ver `docs/progress/2026-08-14.md`).
> Se apoya en `EMPRESAS-IA/docs/PROPUESTA_CONDUCTOR.md` (2026-07-22, nunca implementada) para
> todo lo referido a cómo Sebas interactúa con el sistema — ese diseño ya está resuelto en gran
> parte y no hace falta rehacerlo.
>
> **Casos reales que informan este borrador:** `casos/Efluentes biogas.md` (Andrés) y
> `casos/MICROBIGS 1.md` + `casos/Propuesta de Alianza...md` (Pablo) — no son ejemplos
> ilustrativos, son los dos casos activos hoy.

---

## 1. El giro

CRIZA dejó de tener como propósito central "encontrar blue oceans" (validar demanda no resuelta
+ capacidad + competencia débil + viabilidad, para producir un expediente de decisión de
inversión). Eso ya cumplió su función — de ahí salieron proyectos reales.

**El propósito nuevo: CRIZA es un equipo de agentes de IA especializados que asesoran** a Sebas
y, a través de él, a quien traiga un caso. Blue-ocean-discovery no desaparece — pasa a ser **una
capacidad que el equipo puede invocar cuando el caso la necesita** (ej. una empresa con una
tecnología ociosa buscando un nuevo uso es, literalmente, ese proceso), no el propósito que
organiza a todo el sistema.

---

## 2. A quién servimos

Tres arquetipos de caso. Los dos primeros ya tienen un caso real; el tercero todavía no:

| Arquetipo | Caso real | Qué necesita |
|---|---|---|
| Empresa con una problemática a resolver o una oportunidad a aprovechar | **Efluentes biogás** (Mateo/Helios, vía Andrés) — desde cero | Investigación técnica cruzada entre especialistas + estructuración de cómo asociarse |
| Científico desarrollando un producto que necesita transferencia ciencia→industria | **MicroBigs** (Melina, vía Pablo) — producto ya validado, hay que escalarlo | Regulatorio, formalización de negocio, financiero — casi nada de investigación de fondo |
| Empresa con una tecnología o maquinaria propia buscando un nuevo uso | *(sin caso real todavía)* | A confirmar cuando aparezca uno — no inventar el patrón en abstracto |

Dato importante que ya salió de los casos reales: **el arquetipo de un caso no predice qué tipo
de ayuda necesita.** Biogás es "desde cero" y pide ciencia dura. MicroBigs viene de un científico
transfiriendo su desarrollo, pero hoy casi no necesita ciencia — necesita abogacía regulatoria y
estructura de negocio. La organización del equipo no puede basarse en el arquetipo del caso (ver
§5).

---

## 3. Qué entregamos

No hay un documento único de salida (el "expediente de decisión" de 8 secciones deja de ser LA
salida — pasa a ser una salida posible, para cuando el caso sea de discovery). Lo que hay es
**acompañamiento continuo**, con artefactos que varían según lo que el caso necesite en cada
momento: una síntesis técnica cruzando especialistas, una evaluación regulatoria, un borrador de
estructura de alianza, un modelo financiero, una conexión con una institución o persona concreta.

---

## 4. Cómo interactuás vos (y quién más)

Dos capas distintas, para no confundirlas:

- **Vos y yo (Claude Code)** — seguimos en la capa de *construir* CRIZA: código, agentes,
  infraestructura. Esto no cambia.
- **Vos y el equipo de CRIZA** (Conductor + especialistas) — es la capa nueva, de *usar* CRIZA
  para asesorar casos reales. Acá aplica todo lo que ya definió `PROPUESTA_CONDUCTOR.md`:
  - Hablás con el **Conductor** (un agente conversacional, todavía sin construir) que lee el
    estado real, arma la decisión masticada, y solo invoca especialistas cuando se lo pedís —
    no es autónomo de punta a punta.
  - **Dos puertas de entrada**, ya decidido en esa propuesta: podés hablar con el Conductor o
    directo con un especialista (analogía de empresa: no siempre conviene hablar solo con el
    CEO). El Conductor observa el registro de lo que pasa, no bloquea el acceso directo.

**Abierto — no decidido:** hoy en CRIZA somos tres (Pablo, Andrés, vos) y en los dos casos
reales, quien trajo el caso fue Pablo o Andrés directamente, no vos de intermediario. ¿El sistema
lo usás solo vos, o también Pablo y Andrés interactúan directo con el Conductor/especialistas
para sus propios casos?

---

## 5. Cómo se organiza el equipo — biblioteca de especialistas, no pipeline fijo

Los dos casos reales piden tipos de ayuda tan distintos que organizar el equipo como un pipeline
fijo (como el actual Investigación Amplia → Mercado → Evidencia → Armador) no encaja. Lo que
encaja es lo que ya proponía `PROPUESTA_CONDUCTOR.md` §6: una **biblioteca de especialistas**
que se declaran como configuración, y el Conductor arma para cada caso la combinación que hace
falta — no todos los casos usan a todos los especialistas.

**Candidatos que ya salieron de los casos reales** (no una lista cerrada):

- *Científicos, para síntesis cruzada* (caso Biogás): microbiólogo, ingeniero ambiental, y a
  confirmar un ingeniero agrónomo. La apuesta explícita acá, tuya: la solución puede no estar en
  ninguna bibliografía individual — surge de cruzar lo que dice uno con lo que dice el otro.
- *Negocio, legal, regulatorio, financiero* (caso MicroBigs): estructuración de alianzas y
  contratos, regulatorio (registro de cepas, Tratado de Nagoya, habilitaciones, SAS), financiero
  (cash flow, búsqueda de financiamiento). Hoy **ningún agente de CRIZA cubre esto.**
- *Blue-ocean discovery*, retenida como capacidad invocable, no como el camino por defecto.

---

## 6. Qué pasa con los agentes actuales — a discutir, no decidido

Ninguno de estos cuatro fue diseñado para este modelo. Antes de tocar código hay que decidir
caso por caso:

- **Investigación Amplia** — su motor de mapeo exhaustivo de un sector podría ser lo que
  *alimenta* a los especialistas científicos con el estado del arte antes de que sinteticen, en
  vez de producir un mapa que va directo al Armador.
- **Mercado** — su lógica demand-first podría reorientarse de "¿hay demanda para invertir?" a
  algo más cercano a lo que pide MicroBigs: cómo estructurar la salida al mercado de algo que ya
  existe.
- **Evidence Generalista** — su cruce de factibilidad técnica podría sobrevivir como un primer
  filtro liviano antes de convocar especialistas puntuales (¿hace falta un microbiólogo acá o
  no?).
- **Armador** — ya no hay un expediente fijo de 8 secciones que ensamblar siempre. Pero su
  principio ("ENSAMBLADOR, no investigador — solo sintetiza lo que ya existe") es exactamente el
  rol que describe `PROPUESTA_CONDUCTOR.md` §3.2: alguien tiene que traerte la decisión
  masticada, no cruda.
- **Especialista Proteínas** (`scientific_agent/`) — es, literalmente, el prototipo del tipo de
  especialista científico que ahora hace falta multiplicar (microbiólogo, ambiental, agrónomo).
  Pero hoy arrastra deuda real: sin contrato SEB-115, sin escritura al KM, y — hallazgo de
  `PROPUESTA_CONDUCTOR.md` §6 — su `SYSTEM_PROMPT` sigue clavado a un caso viejo cancelado
  (Andrés / Buenas Maltas, cerrado el 08/07), con restricciones tecnológicas hardcodeadas. Antes
  de clonar el patrón para microbiólogo/ambiental, conviene limpiar el prototipo.

---

## 7. Interacción — web, Next.js

**Confirmado:** Next.js 15 (ya era la decisión de plataforma en `KRIZA_Foundation_Document.md`,
nunca construida para CRIZA). No se extiende `plataforma/control_panel/` (FastAPI + Jinja2, un
panel interno de auditoría) — se arranca la app real de punta a punta.

**Alcance v1, confirmado:** ver los documentos que se generen, tener chats con cada agente,
acceder a los resultados. Sin dashboard todavía — se evalúa más adelante si hace falta.

**Ideas adicionales, confirmadas para sumar al alcance** — ninguna imaginada en abstracto, las
siete salen de releer los dos casos reales con la pregunta "¿qué más necesitamos?":

1. **Entrada por voz.** El caso de biogás entró como una serie de audios transcriptos. La
   entrada de un caso nuevo tiene que poder ser voz (grabar o subir), no solo texto tipeado — es
   literalmente cómo entró el primer caso real.
2. **Un caso tiene varios "frentes" en paralelo, no un solo hilo.** Andrés separó biogás en
   frente técnico y frente de asociación. La vista de un caso necesita mostrar frentes/hilos
   activos a la vez, cada uno posiblemente con su propio especialista conversando.
3. **Modo documento, distinto de modo chat.** El "Acuerdo Marco" de MicroBigs es un contrato con
   placeholders (`[●]`) que se coautoría/negocia en el tiempo, con notas de negociación metidas
   adentro — más parecido a coautoría de documento que a una respuesta de chat. Los especialistas
   que produzcan documentos formales (estructuración de negocio, por ejemplo) necesitan ese modo,
   no solo conversación.
4. **Extraer datos estructurados que hoy quedan enterrados en la prosa.** Contactos puntuales
   (Vicky Arcamone, Miguel Magnasco de la Subsecretaría de Ambiente de Córdoba), cifras (150.000
   litros, dosis de 3ml por animal), plazos — nada los captura estructurados hoy. Mismo patrón
   que ya usa el KM para sacar `props` de un informe narrativo.
5. **Pendientes explícitos, visibles por caso.** El doc de MicroBigs tiene literalmente una
   sección "ENTENDER CON PABLO" con preguntas sin resolver. Una lista liviana de pendientes por
   caso, que cualquier especialista o Sebas pueda agregar.
6. **Vincular artefactos externos al caso.** MicroBigs ya referencia Google Docs/Slides externos
   — el caso no es solo lo que generan los agentes.
7. **Estadío del caso, visible.** Tener una idea rápida de en qué etapa está cada caso (ej.
   desde cero / validado, necesita escalar / en negociación de alianza). **No es el eje que
   organiza qué especialistas se convocan** — el §2 ya estableció que el arquetipo/estadío no
   predice qué ayuda hace falta — es visibilidad de estado para Sebas y el Conductor, no un
   router de equipo.

De estas, la **3** es la que más cambia el diseño técnico, no solo la interfaz: si hay
especialistas que coautoría documentos y especialistas que solo conversan, son dos modos de
interacción distintos, no una sola pantalla de chat para todos.

---

## 8. Modelo de IA por agente

**Confirmado:** elegir modelo y proveedor de IA por agente desde un desplegable en la web. Ya
existe el patrón de fondo — "modelo configurable por agente" vía `.env`
(`SCOUT_MODEL`/`MARKET_MODEL`/etc., principio 7c del `CLAUDE.md`) — esto lo lleva a la UI y lo
extiende a múltiples proveedores, no solo Anthropic.

**Límite real, no de diseño:** la versión de suscripción (Claude Pro/Max, ChatGPT Plus, etc.) no
expone una API para uso programático — los agentes siempre corren contra la API paga por uso,
sin importar qué plan de suscripción exista en paralelo. Es una separación de producto de cada
proveedor, no algo que dependa de cómo construyamos CRIZA. Lo que sí se puede controlar: elegir
modelos más baratos por agente, prompt caching (ya lo usan varios agentes), y visibilidad de
gasto real (`token_usage`, ya trackeado en el KM).

---

## 9. Usuarios y accesos

**Decisión de alcance:** diseñar el modelo de datos de usuarios/roles/accesos ahora, **sin
implementar autenticación real todavía.** Uso actual: solo Sebas. El modelo de datos deja
preparado sumar a Pablo, Andrés u otros más adelante sin rediseñar — la implementación de
login/permisos reales queda para cuando haga falta de verdad.

---

## 10. Lo que ya está resuelto (herencia de sesiones anteriores — no hay que rehacerlo)

- El "cable cortado" que describía `PROPUESTA_CONDUCTOR.md` §2.1 (`tarea`/`contexto` del
  contrato, descartados por los agentes) — arreglado el 2026-07-22.
- El bug de Mercado no persistiendo al KM cuando corría vía Motor (vivía en el runner) —
  arreglado la misma sesión.
- Aislamiento de memoria por instancia (§9 de las decisiones cerradas de esa propuesta) — ya es
  un hecho consumado tras la independización de CRIZA.

---

## 11. Lo que falta decidir antes de tocar código

- ¿Quiénes interactúan con el sistema — solo vos, o también Pablo y Andrés? (§4) — **por ahora
  solo Sebas**, confirmado, preparado para sumar accesos después (ver §9).
- Uno por uno, el destino de los 4 agentes actuales (§6) — no se decide en este documento;
  confirmado que no se tocan por ahora, se ve en la marcha.
- ~~El registry data-driven~~ — **hecho el 2026-08-15.** `orquestador/agents_registry.yaml` +
  `orquestador/registry.py` (data-driven, sin imports hardcodeados) + `orquestador/invocador.py`
  (la costura: persiste `análisis` al KM de forma genérica para cualquier agente, sin que el
  agente tenga que acordarse — resuelve el riesgo estructural que se discutió el 14/08). Los 4
  agentes actuales se normalizaron para que esto funcione. Verificado real contra Neon, 218/218
  tests. Detalle: `docs/progress/2026-08-15.md`, fila "Motor v2" en `agents.md`.
- La captura de decisiones como eventos (§4.3 de `PROPUESTA_CONDUCTOR.md`) — sin construir. Ya
  existe el punto de enganche (`invocador.py::_registrar_evento`, placeholder explícito) — es el
  siguiente ítem lógico, ver orden acordado el 14/08.
- El Conductor conversacional en sí — sin construir. Confirmado con Sebas (14/08): el Conductor
  **asesora** sobre qué especialistas hacen falta y cómo, pero no codea — construir sigue siendo
  tarea de Sebas + Claude Code. No cambia la secuencia sugerida en `PROPUESTA_CONDUCTOR.md` §10.
- El tercer arquetipo (empresa con tecnología/maquinaria buscando nuevo uso) — sin caso real
  todavía. No diseñar el patrón en abstracto hasta que aparezca uno.
- **Nuevo, de hoy:** diseño concreto de la app Next.js — estructura de páginas, cómo conviven
  modo chat y modo documento (§7), y el modelo de datos de caso (frentes, pendientes, estadío,
  artefactos vinculados) que la va a alimentar.
- **Nuevo, de hoy:** el modelo de datos de usuarios/roles (§9) — a diseñar, sin login todavía.
- **Nuevo, de hoy:** capa de abstracción de proveedor de modelo por agente (§8) — a diseñar,
  siguiendo el mismo patrón que `EMBEDDING_PROVIDER` en `knowledge_module.embeddings`.
