# architecture.md — CRIZA-biotech

Decisiones técnicas del sistema. No es un historial de sesiones (eso va en `progress/`).
Para arquitectura de plataforma → `KRIZA_Foundation_Document.md` (carpeta padre EMPRESAS-IA/).

---

## Identidad del sistema

- **Qué es:** Primera empresa agéntica de la plataforma EMPRESAS-IA. Instancia de Capa 2.
- **Dominio:** Transferencia de tecnología ciencia-industria, foco biotech agro argentino (M1).
- **Usuarios:** Sebas (fundador), Pablo (co-fundador), Andrés (productor — Buenas Maltas).
- **Milestone M1:** Agente científico validado + agente de mercado operativo + primer cliente.

---

## Stack

| Componente | Tecnología | Notas |
|---|---|---|
| Agentes | Python 3.13 + Anthropic SDK | Loop agéntico con tool use |
| Modelos | Claude (configurable por agente en .env) | SCOUT_MODEL · SPECIALIST_MODEL · MARKET_MODEL |
| Literatura | OpenAlex API | 250M+ papers, sin key, 10 req/s. Fallback: Semantic Scholar |
| GPU | RunPod pod `qruo50jffhrgze` (H200 SXM, 141GB, US-CA-2) | APAGADO por defecto |
| Tests | pytest | Markers: unit / integration |
| Repos | GitHub org `criza-platform` | Pendiente sincronización tras reorganización |

---

## Decisiones de arquitectura del sistema

### [2026-05] Loop agéntico vs. pipeline determinístico

**Decisión:** Loop agéntico (tool use de Anthropic SDK).

**Por qué:** Proteínas con mucha literatura necesitan menos búsquedas; proteínas poco estudiadas necesitan más. Un pipeline fijo no puede adaptarse. El workflow mandatorio se define en el system prompt, no en el código — Claude lo sigue pero puede adaptarse.

**Consecuencia:** El agente es menos predecible en tiempo. En compensación, `verbose=True` loguea cada tool call en tiempo real.

---

### [2026-05] Estructura multi-repo por capa/instancia

**Decisión:** Un repo por instancia/capa. `criza/` es Capa 2. Cuando existan `knowledge/` y `orchestration/` (Capa 1), serán repos separados.

**Por qué:** Control de acceso a nivel de repo en GitHub. Un dev biotech no debe ver el código de DPN, y viceversa.

**Estado actual:** Solo existe `criza/`. Los repos de Capa 1 se crean cuando se construyan.

---

### [2026-05] Docker solo si hay colaboradores

**Decisión:** Docker activado en `scientific_agent/` (Dockerfile + docker-compose.yml). `market_agent/` sin Docker por ahora.

**Por qué:** Con múltiples developers, entorno reproducible. Para trabajo solo, es overhead innecesario.

**Cuándo activar en market_agent:** cuando se sume un developer al proyecto.

---

### [2026-05] Modelos configurables por agente

**Decisión:** Cada agente lee su modelo desde `.env` (SCOUT_MODEL, SPECIALIST_MODEL, MARKET_MODEL). Default: `claude-sonnet-4-6`.

**Por qué:** Routing de costo — scout corre muchas veces (barato), especialista corre poco pero necesita profundidad (puede ser Opus). No hardcodear.

---

### [2026-05] OpenAlex como fuente primaria de literatura

**Migración:** PubMed → Semantic Scholar (v1.1) → OpenAlex (v1.4.1).

**Por qué OpenAlex:** Semantic Scholar tenía rate limiting agresivo (100 req/5min sin key, 1 req/seg con key). El agente hace 3–5 búsquedas por análisis en ráfaga → SS cortaba silenciosamente y el agente degradaba sin notificar. OpenAlex: 10 req/seg en polite pool, solo requiere `mailto=` en header, sin key.

**Implementación:** `tools/openalex.py` primaria. `tools/semantic_scholar.py` como fallback automático si OpenAlex retorna 429/503 o timeout.

---

### [2026-05] ESMFold local en RunPod vs. API pública

**Decisión:** ESMFold local vía fair-esm en RunPod (pod H200 SXM).

**Por qué:** ESMFold API pública tiene límite de 200aa. Lactoferrina tiene 710aa. Sin GPU local, solo se analiza el 28% de la proteína.

**Protocolo RunPod:** pod APAGADO por defecto. Iniciarlo solo para análisis con proteínas >200aa. SIEMPRE Stop (no Terminate) — Stop conserva disco y parches. Terminate borra todo.

**Fallback:** Si pod apagado → `predict_structure` (API pública, 200aa). El agente lo maneja automáticamente.

---

### [2026-05] Scout separado del especialista

**Decisión:** `scout.py` (multidominio, ancho, sin tools pesadas) es independiente de `specialist_proteins.py` (profundo, con GPU).

**Por qué:** El scout barre el universo de candidatos sin sesgo de dominio. Es barato en tokens. El especialista solo corre sobre candidatos que pasaron el filtro. Economía: el análisis profundo (caro, GPU) corre sobre pocos candidatos.

**Regla:** El scout NO decide ruteo. Solo clasifica con tag de dominio. El ruteo es del Orquestador (humano hoy, agente a futuro).

---

### [2026-06-01] Agente de Mercado — etiquetas de confianza

**Decisión:** Todo dato reportado por el Agente de Mercado lleva etiqueta de confianza:
- `[VERIFICADO]` → COMTRADE o datos.gob.ar (APIs oficiales)
- `[ESTIMADO, fuente: dominio]` → web fetch
- `[INFERIDO]` → razonamiento del agente

**Por qué:** El diferencial del output no es la cantidad de datos sino la trazabilidad de su confiabilidad.

---

### [2026-06-01] Emails — gate humano obligatorio

**Decisión:** `draft_outreach_email()` NUNCA envía. Status siempre = `PENDIENTE_APROBACION`. El usuario envía manualmente.

**Por qué:** Regla no negociable del Foundation Document §7. El agente declara sus gaps y propone acción, el humano decide y ejecuta.

**Futuro:** cuando exista Gmail MCP + Orchestration Layer, el flujo será redactar → mostrar → aprobar → enviar con un click. La aprobación sigue siendo obligatoria.

---

### [2026-06-02] Inversión supply-first → demand-first — jubilación del scout

**Decisión:** El `scout.py` (supply-first) se jubila. Se reemplaza por un agente nuevo construido de cero, **demand-first**. El scout no se reformula ni convive: sus partes buenas se absorben como etapas internas del agente nuevo.

**Cómo llegamos a esta decisión (trazabilidad — no repetir el error):**

1. Corrimos el Agente de Mercado sobre lactoferrina. Preguntaba *"¿cuánta lactoferrina se importa en Argentina?"* — y concluyó que el mercado local del ingrediente es chico (50–200 kg/año).
2. Sebas detectó que el análisis estaba mal **enfocado**, no mal ejecutado. El objetivo de CRIZA no es vender el ingrediente a quienes ya lo compran, sino producir por biotech algo que sustituya y **destrabe demanda hoy reprimida**.
3. El whitepaper de TurtleTree (LF+, lactoferrina por fermentación de precisión) cristalizó el modelo: la lactoferrina es "oro rosa" — 10.000L de leche por 1kg, tan cara que el 80% va solo a fórmula infantil. Producirla barata **no le roba clientes a Fonterra; abre mercados que hoy no la pueden pagar** (yogures, leches plant-based, deportiva, salud femenina).
4. Eso reveló que el scout está **orientado al revés**: parte de "¿qué podemos producir?" (oferta) cuando el valor está en "¿dónde hay demanda reprimida que el biotech destrabaría?" (demanda).

**Por qué reemplazar y no reformular:** Cuando se invierte el punto de partida (supply→demand), se invierten también la estrategia de búsqueda, las tools y los criterios. Reformular un agente cuya orientación de base es la equivocada deja lógica vestigial que lo arrastra de vuelta al sesgo viejo. Construir de cero es correcto **en este caso puntual** — no por la regla genérica "mejor desde cero", sino por la inversión estructural de orientación.

**Qué se conserva del scout (se absorbe, no se tira):** filtro de factibilidad de producción, tags de dominio, niveles de confianza [LIT/EST/INC], forma del contrato de agentes, criterios B2B y restricciones duras. Lo que se invierte es el arranque.

**Las 5 palancas de sustitución** (el agente busca mercados donde al menos una está activa): precio · escasez/inestabilidad de suministro · costo ético-ambiental · dependencia de importación · trazabilidad regulatoria. La lactoferrina activa 4 de 5 — por eso es buen caso.

---

### [2026-06-02] Dos agentes especializados (diverge / converge) acoplados por artefacto

**Decisión:** El pipeline de descubrimiento se parte en dos agentes especializados, NO uno solo:
- **Divergente** (sucesor del scout, demand-first): encuentra y rankea oportunidades de sustitución por desbloqueo de demanda.
- **Convergente** (deep-dive): toma UNA oportunidad y profundiza — precio techo real, dimensionamiento de demanda latente, fabricantes locales que reformularían, camino regulatorio, go/no-go para wet lab.

**El seam es un artefacto con schema definido, NO comunicación en vivo.** La salida del divergente es un documento estructurado que **es** el contrato; el convergente lo consume como input. Hoy el carrier es el humano (un paso: pasar el artefacto). Mañana, el Orquestador.

**Cómo llegamos (trazabilidad):** Tensión observada por Sebas — la especialización mejora a los agentes (uno diverge, otro converge), pero la comunicación entre agentes nunca funcionó. Insight: la comunicación nunca falló porque "dos agentes no pueden hablar"; falló porque **nunca hubo contrato (SEB-115 sin adoptar) ni carrier de estado** — Sebas era el cable, de memoria. Por lo tanto: dos agentes (honra la especialización) + acople por artefacto definido (esquiva el fracaso histórico, que no era el número de agentes).

**Esto ES SEB-115 aterrizado:** el contrato no es mensajería en vivo, es un schema de artefacto compartido. La costura barata.

**Schema del seam (borrador) — cada oportunidad lleva:** producto candidato + tag de dominio · palanca(s) de sustitución activa(s) · mercado/productos finales que se destrabarían · señal preliminar de tamaño del desbloqueo + confianza · factibilidad de producción (propia/socio/híbrida).

**Secuencia de construcción:** primero el divergente (que produzca artefactos limpios) → validar con un caso → recién después el convergente. No construir los dos a la vez: si el artefacto está bien definido, el convergente es fácil; si está mal, se descubre antes de duplicar trabajo.

---

### [2026-06-02] Modelo de "condiciones" del agente divergente — cuestionario configurable + 3 entradas

**Contexto:** El agente divergente (demand-first) necesita un criterio que defina qué es una oportunidad. Antes de diseñar tools, se definió el modelo de condiciones.

**Tres entradas — la misma pregunta con distinto grado de "fijado":**
- **A (científico):** se fija el producto → buscar dónde se destraba demanda.
- **B (empresario):** se fija la capacidad → buscar qué productos encajan.
- **C (abierta):** no se fija nada → buscar productos que cumplan las condiciones, sin semilla.

**C es el núcleo generativo. A y B son C con un campo pre-completado.** C es la pregunta que da origen al negocio — así emergió la lactoferrina (no se partió de producto ni de capacidad). Se diseña el núcleo para C; A y B son modos restringidos. Validación: primera corrida en "modo A" (pin lactoferrina) para confirmar que el razonamiento reproduce lo conocido, después soltar a C completo.

**Las condiciones NO son fijas — son un cuestionario configurable.** Cada gate es un parámetro de la búsqueda con un default; un search específico puede relajarlo (ej: proteína dulce → habilitar B2C). Una búsqueda = (modo de entrada A/B/C) + (perfil de condiciones).

**Nivel 1 — Gate (sí/no, binario, descarta):**

| # | Pregunta | Default | ¿Relajable? |
|---|---|---|---|
| G1 | ¿Es un insumo B2B? | Sí requerido | Sí (ej: proteína dulce B2C) |
| G2 | ¿Hay demanda — actual documentada o latente evidente? | Sí requerido | Raro |
| G3 | ¿Hay al menos una palanca de sustitución activa? | Sí requerido | No (esencia demand-first) |
| G4 | ¿El biotech tiene ventaja clara sobre el método incumbente? | Sí requerido | No |
| G5 | ¿Libre de restricción dura? | Sí requerido | Caso por caso |

**Restricciones duras (G5):** fármaco/medicamento ANMAT/FDA (tiempo al mercado prohibitivo) · síntesis química establecida y barata sin ventaja biotech. **ANMAT-alimento NO es restricción dura** — pasa a Nivel 2 como barrera puntuada.

**G2 es permisivo (decisión Sebas):** se exige demanda, pero puede ser latente-evidente — un producto que nadie produce porque nunca fue posible barato es candidato válido (más arriesgado, potencialmente más disruptivo). Lo que era restricción se volvió permisivo.

**Nivel 2 — Score (graduado, rankea a los que pasaron el gate):**
- Tamaño del desbloqueo de demanda (es score, no gate)
- Fuerza de las palancas (cuántas activas, qué tan fuertes)
- Factibilidad de producción (propia/socio/híbrida — **nunca descarta**, comentario de Andrés: los fermentadores son la primera capacidad, pero se puede producir con socios/otras tecnologías)
- Defendibilidad / ventana competitiva (foso vs. comoditización — ej: dumping chino)
- Camino regulatorio (SENASA ágil / ANMAT-alimento más lento)
- Prueba de la demanda (mercado actual documentado [alta confianza] vs. latente-evidente [riesgo/reward, etiquetado])

**Por qué dos niveles:** mezclar "lo que descarta" con "lo que rankea" fue parte del problema del scout viejo. Gate = binario y configurable. Score = graduado.

---

### [2026-06-02] Set de tools del agente divergente — capas de certeza + roadmap v1/v2

**Consigna:** prioridad de información certera (principio de veracidad operativizado en la elección de tools).

**Hallazgo:** las tools casi no son nuevas — se reutilizan las que ya existen, partidas entre scout (ciencia) y market_agent (mercado). Lo nuevo es cómo se combinan (demand-first) y un par de fuentes adicionales.

**Capas de certeza:**

| Tier | Fuente | Etiqueta | Para qué |
|---|---|---|---|
| 1 — aduana embarque (v2 pago) | NOSIS / Penta-Transaction (AR); ImportGenius/Panjiva (global) | [VERIFICADO] | Desagregar precio/volumen por producto (resuelve el problema HS agregado) |
| 1 — comercio exterior | COMTRADE (gratis) | [VERIFICADO] | Demanda directa del ingrediente importado, precio CIF, orígenes/competencia |
| 1 — estadística doméstica | datos.gob.ar (INDEC/MAGYP) | [VERIFICADO] | **Tamaño del desbloqueo** (producción de categorías finales) |
| 1 — ciencia | OpenAlex + conectores (PubMed, ChEMBL, ClinicalTrials, bioRxiv, OpenTargets, Consensus) | [LIT] | G4 ventaja biotech, factibilidad, bioactividad, aplicación |
| 1 — primario humano | `draft_outreach_email` (gate) | [VERIFICADO-campo] | Cerrar gaps críticos que ninguna base resuelve |
| 2 — research/web | web_fetch (cámaras, consultoras, Mordor, M&M) | [ESTIMADO] | Contexto — nunca base única de un score alto |

**Corrección metodológica — COMTRADE es ciego a la demanda doméstica.** COMTRADE solo ve comercio internacional. Consecuencias:
1. **"Sin importaciones" ≠ "sin demanda"** — un ingrediente producido localmente y no importado muestra cero en COMTRADE; no concluir ausencia de mercado.
2. **Dos capas de demanda distintas:**
   - *Demanda directa del ingrediente* → COMTRADE si se importa [VERIFICADO]
   - *Demanda de desbloqueo* (tamaño de las categorías de producto final que lo adoptarían — yogures, leches, bebidas) → **estadística de producción doméstica, NUNCA COMTRADE**

   El sizing de lactoferrina fue débil porque se apoyó en COMTRADE, que no puede ver el desbloqueo. El score más importante del agente (tamaño del desbloqueo) tiene como fuente primaria producción doméstica + razonamiento.

**Roadmap de tools:**
- **v1 (gratis, construible ya):** 4 tools existentes (COMTRADE, datos.gob.ar, OpenAlex, web_fetch) + conectores de ciencia disponibles + web_fetch dirigido a cámaras/consultoras.
- **v2 (pago, según financiamiento):** datos de aduana a nivel embarque (NOSIS/Penta-Transaction) + market research pago + `regulatory_lookup` dedicado.

**Circuito humano (in-the-loop):** ancho y automático primero, confirmar con humano al final. Flujo: divergente barre ancho → convergente profundiza UNO → identifica gaps **críticos** → outreach humano cierra esos gaps. Un gap es crítico (dispara outreach) solo si **(i)** cambia materialmente el go/no-go del wet lab **y (ii)** no se puede cerrar con bases TIER-1. El outreach es tool del **convergente**, quirúrgico, no masivo.

**Frontera diverge/converge confirmada:** divergente ancho + verificación TIER-1 liviana (GO/NO-GO + señal gruesa). Deep-dive caro (desagregación de precio, sizing fino, outreach) es del convergente. No profundizar en el divergente — fundiría los dos agentes y gastaría tokens en candidatos que se descartan.

---

### [2026-06-02] El seam (artefacto entre agentes) + convergente como embudo N→1

**Formato: JSON canónico + render markdown.** El JSON es la verdad (contrato parseable, validable, almacenable en el Knowledge Module futuro); el markdown es el render legible. **Ambos son necesarios** — Sebas quiere intervenir en la decisión y necesita la vista humana. (JSON = registro de base de datos; markdown = informe impreso.)

**Principios estructurales del artefacto:**
1. **Candidato autosuficiente** — cada bloque-candidato se para solo, para poder compararse y para que el convergente lo procese sin el resto del documento.
2. **Micro-tipo `claim` selectivo** — `{ value, confidence: VERIFICADO|ESTIMADO|INFERIDO, source }` se aplica SOLO a los campos que pesan en el go/no-go (palancas, señales de demanda, precio, factibilidad, regulatorio). NO a los descriptivos (nombre, tag, nombres de productos). Rigor donde importa, sin verborragia donde no.
3. **`divergent_flags` (ex recommended_deep_dive) es advisory, no vinculante** — el divergente (modelo más débil, info liviana) no debe condicionar la línea del convergente (más fuerte). Son pistas; el convergente arma su propio plan de investigación.

**Estructura (esqueleto):** meta (modo A/B/C, perfil de condiciones, scope) · candidates[] (cada uno: gate G1-G5, substitution_levers, demand{direct, unlock}, production_feasibility, defensibility, regulatory, score, confidence_overall, references, divergent_flags) · discarded[] · gaps[] · angles_not_explored[].

---

### [2026-06-13] Rethink: de "embudo que decide" a "sistema de expediente de decisión" + 2 fases

**Origen (trazabilidad):** el output del convergente no generaba confianza para invertir (fuentes viejas/internacionales, datos locales decisivos sin verificar, "GO" inflado). Se frenó y se repensó. Detalle: `progress/2026-06-11.md` y `2026-06-12.md`. Épico: SEB-143.

**D1 — El entregable es un EXPEDIENTE DE DECISIÓN, no una recomendación.** El sistema ARMA la decisión; el humano elige. Pedirle que "decida/elija el producto" lo empuja a fabricar confianza. Spec: `criza/docs/expediente_decision_SPEC.md` (6 bloques).

**D2 — Veracidad por dato.** Cada dato = establecido (con fuente) / asumido (con peso) / a-confirmar (con dónde). Nunca número inventado. El modelo sobreestima tiempos → no confiar en timelines generados.

**D3 — Múltiples puertas de entrada, un mismo entregable:** sector / dolor / tecnología de científico / planta-recurso / necesidad de empresario. Demand-pull Y supply-push convergen al expediente. (Supera el demand-first lineal del 2026-06-02: demand-first sigue siendo UNA puerta, no la única.)

**D4 — "Blue ocean" = cruce de 4:** demanda real no resuelta + capacidad/tecnología + competencia débil + viabilidad en contexto. El sistema PUEBLA y VERIFICA los 4; no "declara".

**D5 — Dos fases:** Fase 1 Decisión (el expediente); Fase 2 Desarrollo (construir el producto elegido). Evaluar-para-decidir ≠ ingeniería-para-construir.

**D6 — Set de agentes (validado contra 5 casos):**
- Fase 1: **Descubrimiento de Demanda** (redefine el divergente — solo cuando la puerta no trae demanda; modos forward/inverso) · **Evidencia Científica** (amplía el científico) · **Mercado** (repotenciado) · **Investigación Amplia** (NUEVO — mapea el espacio de soluciones) · **Armador** (transforma el convergente: de decisor a armador, sin embudo N→1).
- Fase 2: familia de **Diseño y Desarrollo** por dominio (el especialista de proteínas es el 1er miembro).

**D7 — El seam: el motor del KM es el sustrato; los agentes no hablan en vivo.** La `oportunidad` es ficha de 1ra clase (vectoriza → espacio semántico); los 4 cruces = props estructuradas `{valor, estado, fuente|dónde_confirmar, agente}`; evidencia = fichas `fuente`/`documento` conectadas; el Armador renderiza el expediente (documento versionado). Completa SEB-115 (contrato = API del motor + convención de estado por dato). Migración: la `oportunidad` absorbe problema (cruce 1) + solucion (cruce 2).

**D8 — Aprendizaje transversal (loop).** `lección` = ficha de 1ra clase por área (tipo error-a-evitar/solución/acierto · `sirve_a` el objetivo · nivel_confianza/veces_confirmado). Todo agente lee lecciones análogas ANTES de actuar y escribe DESPUÉS; refuerza confianza al reconfirmar. SEB-156. (Estaba en los cimientos del KM pero se había caído en el rethink.)

**D9 — Flujos de orquestación: 5 puertas → 3 patrones.** (a) demanda definida → directo (dolor, empresario); (b) sector → Descubrimiento forward → priorizar → investigar; (c) supply-push → gate de validación del activo → Descubrimiento inverso → investigar. Investigadores **en paralelo** (llenan cruces distintos). Gates humanos donde es caro/irreversible/externo + **decisión final siempre humana**.

**D10 — El Orquestador es un MOTOR DIRIGIDO POR OBJETIVO (genérico), no un ejecutor del pipeline de descubrimiento.** Ejecuta flujos DECLARADOS (config, como las plantillas) → sirve a cualquier instancia. Diseñado para **generalizar al CEO de una empresa agéntica** (mismo patrón un nivel arriba: coordina funciones hacia el objetivo de la empresa; es un fractal). La **autoridad de decisión se gana por etapas** — no se asume; hoy decide el humano. Objective-first + loop de aprendizaje son las piezas load-bearing del CEO, ya presentes. Construcción por etapas; diseño completo desde ahora (CLAUDE.md Regla de capa pto 5).

**Estado:** estructura cerrada a nivel diseño (2026-06-13). Validar el expediente contra un caso real (SEB-144). Construcción: épico SEB-143 + sub-tareas (arranque sugerido: conector CONICET SEB-150 + Armador SEB-145).

**El input del convergente es TODO el conjunto de candidatos, no uno pre-elegido.**

**CORRECCIÓN del modelo diverge/converge — el convergente es un EMBUDO N→1.**

La versión anterior tenía: divergente tira N → humano elige 1 → convergente profundiza ese 1. Error: la convergencia (N→1, la decisión más cara) la hacía un humano leyendo un ranking débil del divergente. "Converger" ES reducir N→1, y eso debe hacerlo el convergente con rigor.

Modelo corregido — embudo de rigor creciente:
1. Divergente → N candidatos (ancho, barato, verificación TIER-1 liviana)
2. Convergente: pasada comparativa media sobre los N → elimina → quedan 1-2 finalistas → deep-dive completo (aduana, outreach) SOLO sobre finalistas
3. Recomienda 1, con runner-up documentado
4. Humano: dirige/aprueba la recomendación + gate de outreach

Ventajas: converge de verdad (N→1 con rigor creciente) Y controla costo (no deep-dive caro ×5, solo sobre sobrevivientes). El humano deja de pre-seleccionar a ciegas; pasa a aprobar una convergencia rigurosa. **Reemplaza la nota previa de "humano elige 1 antes del convergente".**

---

### [2026-06-14] Construcción del rethink — mapa de agentes, corpus de fuentes locales, secuencia

Decisiones cerradas con Sebas para arrancar la construcción (épico SEB-143). No re-discuten D1–D10;
las aterrizan.

**Mapa de agentes — qué se adapta / crea / retira:**
- `scout.py` → **retirar** (jubilado, partes ya absorbidas en el divergente).
- `divergent_agent` → **adaptar** a Descubrimiento de Demanda (SEB-147): ya no es inicio obligatorio;
  se invoca solo cuando la puerta no trae demanda; agregar modo inverso.
- `convergent_agent` → **transformar** en Armador del Expediente (SEB-145): se le quita el embudo N→1 y
  la elección de finalista; conserva marco blue ocean, `motor_selector`, write-back; pasa a renderizar
  el expediente. No investiga.
- `market_agent` → **adaptar/repotenciar** a Mercado (SEB-148): fix datos.gob.ar ya aplicado; wirear
  `search_series`, sumar SENASA/regulatorio; orientar a cruces 1/3/4 + anclas del bloque 6.
- **Split del científico (decisión):** `specialist_proteins` (ESMFold/FoldX/diseño de variantes) es
  **Fase 2 — Diseño y Desarrollo (SEB-153)**, ingeniería-para-construir. **Evidencia Científica
  (Fase 1, SEB-149)** es un agente **distinto** (evaluar-para-decidir: literatura, factibilidad, estado
  del arte), construido sobre la capa de literatura, NO sobre las tools de proteínas. D5 los separa.
- **Redistribución de tools (decisión):** las 5 tools de ciencia pendientes del rediseño v0.2 del
  convergente (ChEMBL, ClinicalTrials, PubMed, bioRxiv, patentes) **migran a los investigadores**
  (Evidencia Científica / Investigación Amplia), no al Armador.
- `Investigación Amplia` (SEB-146) → **crear nuevo** (cruce 3). `Orquestador` (SEB-152) → **diseñar**
  (motor dirigido por objetivo).

**Corpus de fuentes locales = área propia genérica en el motor del KM (Opción A).** Los papers
cosechados (CONICET, INTA…) aterrizan como fichas `fuente` en una **área/plantilla propia** del motor
(Capa 1, genérica, sirve a DPN), con su **espacio semántico separado** del de descubrimiento (no
contamina problema/solución). Vectoriza título+abstract; dedup por identifier OAI/DOI/handle; **no
pre-conectadas** a problema/solución — los investigadores las traen por búsqueda semántica
(`vecinos`/`buscar`) al llenar sus cruces. Descartadas: tabla `documento` legacy (se está retirando →
deuda) y store de texto aparte (segundo sustrato en paralelo → viola D7). Coherente con D7 (evidencia =
fichas fuente conectadas) y con el motor genérico.

**Conector OAI-PMH:** harvester genérico = **Capa 1** (`knowledge_module/`); endpoint CONICET + filtro
agro/ganadería = **Capa 2** (config CRIZA). Cosecha incremental (`from`/`until` + resumption tokens),
idempotente por el dedup near-identical del motor. v0.1 = metadata Dublin Core + abstract + link al
full-text; fetch de full-text = v0.2. Gate: `knowledge_module/docs/CONICET_CONNECTOR_GATE.md`.

**Secuencia de construcción (decisión, "no parches"): CONICET (SEB-150) → Mercado (SEB-148) →
Armador (SEB-145).** El flujo de datos es investigadores → Armador; construir el Armador primero lo
haría ensamblar datos sintéticos/viejos + casi todo `a-confirmar`. Con CONICET (sustrato local) +
Mercado (primer investigador real, es adaptación) el Armador llega a cruces reales y valida la spec del
expediente (SEB-144) contra la realidad. Secuenciar construcción ✓; el diseño ya está completo (D1–D10).

---

### [2026-06-02] Anti-sesgo de encuadre — dos ejes: veracidad + pertinencia

**Contexto / cómo llegamos:** El divergente produjo un análisis de lactoferrina coherente y bien fundado pero **sin sentido para Argentina** — citó precios de Nueva Zelanda y Alibaba, usó el libreto de TurtleTree (Singapur, país SIN industria lechera) en un país que es uno de los mayores productores de leche del mundo. Sebas detectó que es una tendencia sistemática de los modelos Claude: aprendieron con datos de economías grandes/exportadoras (USA) y resbalan al marco dominante, fuera de foco para una economía chica e importadora como Argentina.

**El insight clave — son DOS ejes de error distintos:**

| Eje | Pregunta | Mecanismo |
|---|---|---|
| 1. Veracidad | ¿El dato es real? | Etiquetas [VERIFICADO]/[ESTIMADO]/[INFERIDO] |
| 2. Pertinencia/encuadre | ¿El dato y su interpretación aplican a Argentina? | (nuevo — ver abajo) |

Un dato puede ser VERIFICADO en el eje 1 y erróneo en el eje 2 (precio de leche NZ = real pero fuera de marco para AR). El principio de veracidad NO cubre el encuadre. Por eso el énfasis en "datos reales" no resolvía esto.

**Verdad estratégica:** es un PRIOR del modelo — no se elimina con instrucciones, va a resbalar siempre. Por lo tanto el sesgo se atrapa **por proceso/estructura, no por buena voluntad del modelo.** Diseñar alrededor del sesgo, no pelearlo con prompts.

**Defensas estructurales (norma transversal — aplica a TODO agente de análisis de CRIZA y futuras instancias):**

- **A. Eje de pertinencia en el micro-tipo `claim`** — además de la confianza, marca si la evidencia es argentina o importada de otro contexto. Una palanca/claim justificada solo con fuentes extranjeras NO puede superar [INFERIDO] cuando `target_market = Argentina`. Sesgo topado por schema.
- **B. Auditoría de geografía de fuentes** — el artefacto reporta su mezcla (AR vs internacional). Dominado por fuentes extranjeras → conclusiones provisionales, flag. El agente audita su propio sesgo.
- **C. Contra-caso obligatorio** — para cada candidato top, construir el argumento más fuerte EN CONTRA (ej: "por qué la extracción le gana a la fermentación en Argentina"). Trabajo científico: hipótesis + nulidad. **Vive en el CONVERGENTE** (pocos candidatos) por costo de tokens; el divergente solo deja el flag.
- **D. No pre-decidir en NINGUNA dirección** — el agente no asume que la fermentación gana (sesgo Singapur) ni que la extracción gana. Compara los caminos con datos reales y, si faltan, declara el gap. Es el principio de veracidad en su forma más estricta = trabajo científico.

**Mecanismo de garantía (cómo aseguramos que no recurra): evals de regresión de sesgo.** La lactoferrina se vuelve caso de test fijo. Cada versión nueva del agente se corre y se verifica: ¿hizo el chequeo de aplicabilidad local? ¿construyó el contra-caso? ¿su mezcla de fuentes está balanceada? Si vuelve a citar Alibaba y olvidar el suero argentino, el eval falla ANTES de llegar a una decisión de inversión. Ligado a SEB-122.

---

### [2026-06-02] target_market configurable + anti-anclaje de input

**target_market en el perfil de condiciones:** default = Argentina (mercado doméstico). Opcional = exportación. Las palancas se evalúan RELATIVAS al mercado configurado (ej: la palanca ético-ambiental/animal-free pesa poco en AR doméstico, fuerte en exportación ESG).

**Anti-anclaje de input (cómo llegamos):** El agente fijó TurtleTree como marco porque el assistant lo sembró en la query de `run.py` (un PDF que Sebas compartió para ilustrar un concepto, no para ser EL marco). El agente tomó marketing de una empresa interesada como columna vertebral. Reglas:
- **No sembrar referencias en el input.** En modo A se da el producto + la pregunta, NO una narrativa pre-armada ni una empresa-campeona. El agente construye caso Y contra-caso solo.
- **Disciplina anti-anclaje en el system prompt:** fuentes comerciales (empresa promoviendo su producto) = interesadas, baja confianza; buscar activamente evidencia que contradiga; ninguna fuente única fija el marco.

**Costo en tokens (decisión Sebas: preferir sobrediseñar por ahora):** el costo de un análisis sesgado que dispara un wet lab >> costo de tokens. El contra-caso caro vive en el convergente; el system prompt grande se cachea (prompt caching); medir consumo real en próxima corrida y revisar (liga SEB-120).

---

### [2026-06-02] Modelo de costos del embudo — rigor barato arriba / caro abajo

**Trade-off detectado (Sebas):** si el divergente es barato/superficial y pasa candidatos mal-encuadrados, el convergente quema tokens caros analizando candidatos equivocados. Mover el rigor caro abajo no ahorra si el filtro de arriba es poco confiable.

**Resolución — el rigor no es monolítico:**
- **Rigor barato (filtrado):** detectar candidatos mal-encuadrados (eje de pertinencia + auditoría de fuentes + sanity "¿tiene sentido para AR?"). Costo bajo. Va ARRIBA (divergente). Es lo que atrapa candidatos equivocados y PROTEGE el presupuesto del convergente.
- **Rigor caro (analítico):** contra-caso con datos reales (extracción-vs-fermentación, aduana, outreach). Va ABAJO (convergente, solo finalistas).

**Doble gate:** el trabajo caro está detrás de DOS filtros baratos — el del divergente Y la pasada comparativa media del convergente. Un candidato equivocado debe engañar a ambos para quemar tokens del contra-caso caro.

**Riesgo residual:** si el sesgo es sistemático y compartido, atraviesa ambos gates. Por eso las defensas anti-sesgo son transversales (los dos agentes las aplican), no solo del divergente.

**Palanca de calibración + medición:** el lever es cuántos candidatos pasa el divergente. Medir eficiencia POR ETAPA del embudo (no solo tokens totales): si el convergente elimina muchos candidatos del divergente en la pasada media → filtro del divergente demasiado flojo → ajustar umbral/shortlist. Liga SEB-120 (medición por agente/run/etapa).

---

### [2026-06-02] Disciplina de construcción de prompts — estructura, no memoria

**Contexto / cómo llegamos:** Tras el refactor anti-sesgo, el divergente SEGUÍA sesgado — citaba "a diferencia de Singapur o Israel". Causa: el assistant había sembrado esa tesis comparativa en el system prompt al agregar el "contexto país". Además había sembrado "lactoferrina activa 4/5 palancas" (pre-decisión) y hechos hardcodeados de Argentina. Tercer ancla en tres intentos, siempre por el mismo lugar: el assistant escribía el prompt a mano.

**Insight de Sebas:** el contexto país NO es input — es trabajo del agente. El usuario solo dice el target_market; el agente CONSTRUYE el contexto con datos (Fase 0). Si se lo doy masticado, lo anclo y lo vuelvo inútil para otros mercados.

**Disciplina (estructura que hace el error imposible, no depende de recordar):**
- **Base del system prompt = constante auditada.** No se reescribe por análisis. Cambios = diff revisable. Genérica: sin hechos de país, sin tesis comparativas, sin empresas, sin candidatos-ejemplo. Solo el MÉTODO de razonar.
- **El input se arma con `build_query()` tipado** (target_market, product?, capacity?, ajustes de gate). NO hay campo de texto libre → estructuralmente imposible inyectar narrativa/ancla. El "cómo razonar" vive en el system prompt; el query solo lleva variables.
- **Fase 0 — el agente construye el contexto del mercado** con datos reales. No se le da hardcodeado.
- **Linter de prompt (pendiente):** chequeo pre-corrida que falla si el query menciona empresas, compara países, o la base tiene hechos hardcodeados. Liga SEB-129 (evals).

**Principio:** estructura primero (hace imposibles los errores comunes) → eval segundo (caza lo que se cuela) → memoria/norma tercero (el juicio). Así Sebas deja de tener que recordar/auditar cada corrida.

**UX de activación (embrión del Orquestador):** "activá el divergente" → preguntas guiadas (modo A/B/C · mercado · producto/capacidad · ajustes de gate, con defaults) → build_query → corre. El usuario solo pone inputs, nunca escribe un prompt.

---

### [2026-06-02] Output del divergente — razonamiento trazable, sin scores numéricos

**Cómo llegamos:** El output estructurado (score 6.48, "socio", palancas) afirmaba conclusiones sin mostrar POR QUÉ. Sebas: "lo leo y no se entiende por qué llega a lo que llega" → no válido para pasar a segunda etapa. Causa: el assistant forzó "solo JSON" y mató la narrativa de razonamiento que el agente SÍ había escrito en la primera corrida (era lo valioso). Además, un score numérico sobre datos [INFERIDO] es falsa precisión inauditable.

**Decisión:**
- El artefacto LIDERA con un campo `reasoning` (narrativa trazable: por qué es/no oportunidad, evidencia, qué queda abierto). La estructura (palancas, gate, demanda, fuentes) lo RESPALDA, no lo reemplaza.
- **Sin scores numéricos en el divergente.** Prioridad CUALITATIVA (alta/media/baja) + rationale explícito. El número cuantitativo lo pone el convergente con datos reales.
- Hay dos lectores: el convergente (máquina, quiere estructura) y el humano (quiere seguir la lógica). El JSON canónico sirve al primero; el render markdown determinístico (`to_markdown()`) lidera con el razonamiento para el segundo.

**Observación meta (el assistant sobre sí mismo):** venía apilando estructura (gates, palancas, scores, claims) y el resultado afirmaba en vez de explicar. El arreglo no es MÁS estructura — es razonamiento transparente que un humano pueda seguir.

---

### [2026-06-02] Razonamiento OBJECTIVE-FIRST — el cambio de raíz

**El problema más profundo de toda la sesión (diagnóstico de Sebas).** El agente razona dirigido por
la información disponible, no por el objetivo:

- **MAL (data-first, lo que hace):** "Tengo estos datos (COMTRADE, literatura) → ¿qué deduzco?".
  La información disponible maneja el análisis. Lidera con "importaciones HS3504" porque es lo que
  tiene, no porque la decisión lo requiera. Rellena gaps con memoria stale. Tapa lo que no sabe.
- **BIEN (objective-first):** "¿Cuál es la decisión? → ¿Qué necesito saber para tomarla? → busco
  eso → analizo contra la decisión". La pregunta maneja el análisis; los datos la sirven.

**Un mismo error de raíz explica TODOS los síntomas:** jerga de framework (el framework manejó en
vez del objetivo), números sin significado (reportó el dato que tenía, no el que la decisión
necesita), macro desactualizada (agarró info disponible en memoria), no ayuda a decidir (nunca
ancló en la decisión).

**Workflow correcto del agente:**
1. Plantear la DECISIÓN concreta (ej: "¿conviene que CRIZA produzca lactoferrina por biotech para AR?").
2. Derivar las 4-5 PREGUNTAS que la deciden (mercado interno y tamaño, costo biotech vs. precio
   importado puesto, camino y tiempo regulatorio, posición defendible).
3. Para cada pregunta, ir a buscar el dato que la responde con las tools.
4. Responder lo verificable [VERIFICADO] / nombrar lo que no como GAP de primera clase (lo que hay
   que averiguar antes de invertir) — NO taparlo.
5. Sintetizar contra la decisión: la lectura, con qué confianza, y la incógnita crítica que la gatilla.

**Consecuencias de diseño:**
- El output se organiza por las PREGUNTAS DE LA DECISIÓN, no por candidatos-con-palancas.
- El andamiaje (palancas, gates, contra-caso) pasa a ser AYUDA INTERNA del agente para derivar
  preguntas — NO estructura del output ni vocabulario visible. El informe humano es prosa plana.
- Cada dato tiene sentido porque se buscó para responder una pregunta de la decisión.
- Los gaps se vuelven lo más valioso: dicen qué conseguir después (y son el caso de financiamiento —
  con tools gratuitas varias preguntas no se responden: mercado interno, precio actual, regulación).
- Veracidad estricta: prohibido opinar de macro/regulación/precios actuales desde memoria; si no se
  verifica, es gap. (Ej de fallo: dijo que Argentina tiene múltiples tipos de cambio — dato viejo.)

**Esto supera la inversión supply→demand:** demand-first fue direccionalmente correcto pero se
implementó como "¿qué palancas están activas?" (framework) en vez de "¿qué necesita la decisión?"
(objective-first). Objective-first es el nivel que faltaba. Probablemente SIMPLIFICA el agente, no
lo complica. Pendiente: rediseñar el workflow + output del divergente sobre esta base.

---

### [2026-06-10] COMTRADE fuera de los agentes — induce sesgo de marco

**Decisión (Sebas):** No conectar COMTRADE (datos de importación) a ningún agente. Se removió `get_import_data`
del set de tools del convergente. El divergente nunca lo expuso (estaba importado pero no en su lista de tools).

**Por qué:** COMTRADE solo ve comercio internacional → empuja al agente al marco "sustitución de importaciones",
que es un sesgo exportador documentado (ver [2026-06-02] "Anti-sesgo de encuadre"). En la corrida de validación
del convergente (porcicultura, 2026-06-10) se observó el síntoma: el agente fue a buscar "precio CIF de fitasa
importada" como pregunta central, cuando el valor real de CRIZA está en el DESBLOQUEO de demanda doméstica, no en
sustituir lo que ya se importa. El costo del sesgo > el dato que aporta.

**Consecuencia:** la demanda directa del ingrediente se razona desde producción doméstica (datos.gob.ar) +
contexto (web), no desde comercio exterior. El sizing del desbloqueo ya tenía como fuente correcta la producción
doméstica. Quitar la tool hace estructuralmente imposible que el agente derive al marco equivocado (estructura
primero, no depender de que el prompt lo recuerde).

---

### [2026-06-10] Agente Convergente v0.1 — el seam es el KM, embudo N→1

**Decisión:** El convergente NO recibe un archivo del divergente. Lee del Knowledge Module las oportunidades del
sector (modo Auto: estado `detectada`; modo Manual: IDs explícitos). El divergente es estocástico y sus corridas
ya ingestan candidatos deduplicados en `oportunidad` → la unión vive en el KM. **El KM es el carrier de estado**
que faltaba en el viejo fracaso de "comunicación entre agentes" (nunca hubo contrato ni carrier; Sebas era el cable).

**Embudo N→1 con costo escalonado:** pasada comparativa media sobre las fichas sintéticas (barato) → deep-dive
solo sobre 1-2 finalistas, donde se carga el reasoning completo del divergente (`load_divergent_reasoning`) y se
construye el contra-caso. Ingesta de salida en 3 capas: Corrida + Documento (informe completo) + update de
`estado_analisis` de cada oportunidad analizada (el análisis de los no-finalistas no se pierde).

**SYSTEM_PROMPT propio** (no reusa `metodologia_busqueda_AGENTE.md` del divergente): destila los principios
transversales de architecture.md — objective-first, veracidad de 2 ejes, anti-sesgo de encuadre, contra-caso.
Detalle y decisiones en `convergent_agent/docs/DESIGN_GATE.md` (§5.A–E).

---

### [2026-06-02] Principio de veracidad — datos comprobados, no suposiciones

**Decisión:** Ambos agentes nuevos (divergente y convergente) deben operar sobre información **veraz y comprobada**. El sesgo por defecto es hacia el dato verificable; las suposiciones se etiquetan explícitamente y nunca se presentan como hechos.

**Por qué:** El output alimenta una decisión de inversión real (tiempo y dinero significativos en un wet lab y un negocio). Un dato no confiable presentado como confiable puede inducir una inversión equivocada. El valor del sistema no es la cantidad de conclusiones sino **cuán cerca de la realidad** están. Mejor un gap declarado que una inferencia disfrazada de verificación.

**Implementación:** se extiende el sistema de etiquetas del Agente de Mercado ([VERIFICADO]/[ESTIMADO]/[INFERIDO]) como obligación de diseño en ambos agentes. Toda afirmación lleva su nivel de confianza y su fuente. Lo que no se puede verificar se declara como gap, no se rellena con suposición.

---

### [2026-06-27] Fuentes de literatura local — INTA Digital + AGROVOC

**Contexto:** El evidence agent necesita fuentes locales (argentinas) para evitar el sesgo de encuadre detectado en [2026-06-02]. Las fuentes internacionales (OpenAlex) no tienen literatura del INTA. Se construyó el stack de ingestión de fuentes externas.

**Decisión — INTA Digital via OAI-PMH + discover:**
El repositorio INTA (repositorio.inta.gob.ar) expone 25.662 documentos vía OAI-PMH. El CICVyA (umbrella biotech) tiene 1.640 registros. Acceso confirmado:
- OAI-PMH: `repositorio.inta.gob.ar/oai/request` — harvest bulk + individual record retrieval. ✅
- Discover: scraping HTML para búsqueda por keyword. ✅
- REST API DSpace: 404. ✗ Solr: 403. ✗

**Decisión — AGRIS excluido:**
AGRIS (FAO, global) retorna 403 a acceso programático. Sin API pública. Decisión: contenido argentino se obtiene directamente de INTA + CONICET; contenido global via OpenAlex. AGRIS no agrega valor marginal suficiente para justificar scraping no-oficial.

**Decisión — AGROVOC como tesauro canónico:**
Los términos de búsqueda se resuelven contra el tesauro AGROVOC de la FAO (mismo vocabulario que usa INTA para indexar). `criza/utils/agrovoc.py` — `expand_term(term)` retorna prefLabel ES/EN + broader/narrower/related. Fallback EN si el término no tiene tilde correcta en ES. Decisión: todos los agentes que busquen en INTA usan AGROVOC para expandir términos, no texto libre.

**Decisión — Document Store en Capa 0-1 (`plataforma/`):**
PDFs descargados de fuentes externas viven en `plataforma/document_store/data/{instance}/`. El texto extraído va al KM (`Documento.texto_completo`). Dos capas separadas por propósito: disco = persistencia del binario; KM = sustrato semántico. Capa 0-1 porque DPN necesitará el mismo patrón para normativa argentina. El nombre de carpeta es `plataforma/` (no `platform/` — conflicto con built-in de Python).

**Decisión — `store_fuente_externa()` como único punto de entrada al KM para docs externos:**
`knowledge_module/tools/store.py::store_fuente_externa()`. Dedup por `fuente_url` (índice UNIQUE parcial sobre NOT NULL, para que docs internos sin URL no colisionen). Idempotente — re-run devuelve `{action: "skipped"}`. El modelo `Documento` (v0.3) ahora tiene: `texto_completo`, `autores`, `subjects`, `fuente_url`, `doi`. Los check constraints de `agente` y `tipo` se expandieron para aceptar 'harvest'/'ingest' y 'paper'/'reporte'/'norma'/'patente'/'otro'.

**Harvest orquestador:** `criza/ingest/harvest_inta.py` — une todo el stack. Flags: `--set`, `--desde`, `--con-pdf`, `--dry-run`. Requiere km venv (asyncpg + sqlalchemy + pypdf).

**Decisión — FTS PostgreSQL sobre corpus externo (sin embeddings):**
El corpus de documentos externos (INTA) se busca con `websearch_to_tsquery('simple', ...)` + índice GIN sobre columna GENERATED ALWAYS `fts_vector`. Cubre título + contenido + subjects. Se eligió FTS sobre embeddings porque: (a) los embeddings del KM (BGE-m3) son para oportunidades y aprendizajes — corpus distinto; (b) los papers de INTA son literatura técnica en ES/EN con terminología precisa, donde la búsqueda léxica exacta supera a semántica difusa; (c) `'simple'` como config es agnóstico al idioma (bien para mezcla ES/EN). Función: `search_fuentes_externas()` en `knowledge_module/tools/search.py`. Expuesta también en el MCP server como `km_search_fuentes_externas`.

**Decisión — Evidence Generalista v1.2: corpus INTA + AGROVOC como fuentes de evidencia local:**
El evidence agent tiene 4 tools: `search_literature` (OpenAlex global, EN), `expand_agrovoc` (FAO tesauro, ES/EN), `search_corpus_inta` (corpus INTA local, ES/EN), `submit_evidencia`. El SYSTEM_PROMPT sugiere el ciclo `expand_agrovoc → search_corpus_inta` para dolores agropecuarios argentinos. `expand_agrovoc` es sync (urllib) y expuesto como tool explícito — el agente decide cuándo vale el round-trip de ~2s a AGROVOC, en vez de hacer la expansión automática en cada búsqueda. Rationale: INTA indexa con vocabulario AGROVOC; buscar con el término canónico del tesauro (ej: "Garrapata" no "garrapatas", "ticks") mejora el recall en el corpus español.

**Decisión — `batch_store_fuentes_externas`: INSERT ON CONFLICT DO NOTHING (no SELECT pre-fetch):**
El approach original (SELECT existing URLs → filter → INSERT) tiene race condition: dos background tasks concurrentes que ya habían insertado registros causaban `UniqueViolationError` porque sus commits no eran visibles al SELECT previo. Fix: `pg_insert(Documento).values(rows).on_conflict_do_nothing(index_elements=["fuente_url"], index_where=text("fuente_url IS NOT NULL")).returning(Documento.id)`. El índice parcial `uq_documento_fuente_url` (WHERE fuente_url IS NOT NULL) requiere `index_where` para que SQLAlchemy lo matchee correctamente. `RETURNING id` retorna solo los rows realmente insertados (no los que conflictuaron), permitiendo contar `created` exacto; `skipped = total_input - created - errors`. Atómico, idempotente, sin race conditions. Intra-batch dedup por URL via dict antes del INSERT (INTA incluye el mismo handle en múltiples sets del umbrella). Tests: 8/8 en `knowledge_module/tests/test_batch_store.py`.

**Decisión — Motor Dirigido por Objetivo v2: flujos declarados + plataforma genérica (SEB-152):**
Diseño completo del Orquestador como motor genérico. Ver `criza/orquestador/docs/DISEÑO_MOTOR_ORQUESTADOR.md`. Decisiones clave: (A) Flujos en YAML (`criza/orquestador/flows/`) — no Python — legibles, versionables, no-código para editar flows; (B) Motor en Capa 1 desde el diseño, aunque la primera implementación vive en `criza/orquestador/motor.py` (se extrae a `plataforma/motor/` cuando la segunda instancia lo necesite — evitar la trampa "generalizamos después"); (C) LLM solo en los agentes, no en el motor — el motor ejecuta el flujo declarado, no razona sobre el routing; (D) Registry en Python (`registry.py`) conecta nombres de agentes con imports lazy; (E) `pipeline_status` escrito en KM después de cada paso — habilita recovery y transparencia; (F) Gates humanos declarados en el flow YAML (`gate_humano: {mensaje, espera_campo}`) — flexibles por instancia; (G) Routing declarativo (`routes: campo → siguiente_paso`) — reproducible y testeable sin LLM. El orquestador v1 (LLM puro) sigue funcionando hasta que v2 esté construido y validado — no se depreca hasta tener reemplazo. Secuencia: v2.0 (motor + flow dolor) → v2.1 (flow sector, gate humano) → v2.2 (flow supply-push + divergente) → v2.3 (extracción plataforma). Fractal CEO: el mismo motor generaliza un nivel arriba coordinando funciones de empresa.

**Decisión — Agente Investigación Amplia v1 (SEB-146):**
Nuevo agente que llena el cruce 3 (Competencia) del expediente de decisión para entradas tipo `sector` o `planta-recurso`. 5 tools: `search_literature` (OpenAlex), `expand_agrovoc` (FAO tesauro), `search_corpus_inta` (corpus INTA FTS), `fetch_page_text` (scraping web), `submit_investigacion_amplia` (output). Output: `cruce_3` (intensidad: vacío/débil/fuerte + evidencia + registros SENASA/patentes) + `mapa_candidatos` (dolores priorizados alta/media/baja). `próximo_agente = "mercado"` si hay ≥1 candidato alta-prioridad; `None` si todos son media/baja. `nivel_confianza` derivado de intensidad del cruce_3 × count de candidatos establecidos. Importa tools directamente desde `knowledge_module` y `utils` (mismo patrón que evidence_generalista, evitando colisión de paquete `tools/` de SEB-196). `fetch_page_text` implementado inline con urllib (sin deps externas). `search_series`/`search_official_stats` postergados a v0.2 (SENASA API formal + patentes). Gate: 🟡 Listo con deuda, todas las decisiones cerradas en el gate. 18/18 unit tests.

**Decisión — Contrato estándar de agentes: INPUT_CONTRACT + OUTPUT_CONTRACT + run() (SEB-115):**
Todo agente expone tres artefactos en su módulo principal: `INPUT_CONTRACT` (campos que acepta: caso, tarea, contexto, conocimiento, herramientas), `OUTPUT_CONTRACT` (campos que retorna: análisis, nivel_confianza, recomendaciones, próximo_agente, nuevo_conocimiento) y `async def run(contract_input)` que wrappea `run_agent()` con I/O tipado. Adoptado en Mercado v1 (18/18 tests) y Evidence Generalista v1.2 (34/34 tests). `próximo_agente` = None en el mercado (el Orquestador decide routing); = "cientifico_especialista" en evidencia si `especialista_recomendado.si_no=True`. `nivel_confianza` derivado de gaps (mercado) o estado_cientifico × brechas altas (evidencia). El contrato vive en cada módulo, no en una clase base — los agentes son independientes y el Orquestador los llama vía `run()`.

**Decisión — Market Agent v1: 7 tools, sin COMTRADE, demand-first (SEB-148):**
El agente de mercado v1 elimina COMTRADE (requería registro pago y latencia alta) y pasa a demand-first: el análisis parte de la demanda no resuelta, no de la oferta exportable. 7 tools: `buscar_corpus_cientifico` (KM motor), `search_series` + `get_series_values` (APIs de Series de datos.gob.ar), `search_official_stats` (CKAN datos.gob.ar), `fetch_page_text`, `draft_outreach_email`, `submit_analysis`. `_resolve_org` en `datosgobar.py` mapea aliases friendly → slugs reales de CKAN (ej: "indec" → "sspm", "senasa" → "agroindustria"). Tests: 41/41. Pendiente (SEB-196 backlog): integrar corpus INTA FTS en `buscar_corpus_cientifico` — colisión de paquete `tools/` entre `market_agent/tools/` y `knowledge_module/tools/` (opciones: lazy import via `importlib.util`, renombrar KM a `km_tools/`, o soft-fail `db.py` cuando DATABASE_URL ausente).

---

### [2026-06-30] Interfaces CRIZA: web + bot Telegram — stack y arquitectura

**Decisión:** construir dos canales de interacción sobre el Motor/Orquestador existente.

**Canal 1 — Bot Telegram:**
- Solo para el equipo operativo de CRIZA (Sebas por ahora; Pablo y Andrés a futuro).
- Flujo: usuario envía `/analizar ganadería bovina` → motor inicia `pipeline_sector` → gate humano se resuelve via Telegram → expediente se envía cuando termina.
- Implementación: webhook route dentro del FastAPI (`/telegram/webhook`). No es un servicio separado. Usa `python-telegram-bot` en modo webhook (no polling — más robusto en producción).
- Estado entre mensajes: `pipeline_status` en el KM (ya lo escribe el motor) + tabla simple `telegram_sessions` que mapea `chat_id → flow_run_id`.

**Canal 2 — Web app:**
- Acceso externo (no local). Equipo CRIZA: Sebas, Pablo, Andrés.
- Pantallas: home (indicadores), oportunidades (lista + estado), expediente (render completo), búsqueda KM (FTS sobre corpus INTA + CONICET).
- Diseñada para escalar a más usuarios — auth desde el arranque.

**Stack:**
- Frontend: Next.js / TypeScript → Vercel (proyecto `criza` en la cuenta de operación)
- Backend: FastAPI Python → Railway (proyecto `criza`, servicio `api`)
- DB: Neon existente (proyecto `criza`, `tenant_id = 'criza'`) — se agregan tablas de auth
- Auth: NextAuth + JWT (mismo patrón que Conflur, estándar de plataforma per D11)
- Bot: webhook route en el mismo FastAPI

**Auth (detalle):**
- NextAuth maneja la sesión en el frontend (Credentials provider → llama `/auth/*` del backend).
- FastAPI es dueño de la verificación. El JWT lleva `user_id`; FastAPI lo valida en cada request.
- Sin WebAuthn/Passkeys por ahora — herramienta operativa interna, no producto de cliente.
- Email + contraseña. Sesión: 30 días máx., expiración por inactividad a los 14 días (mismo que Conflur).
- Tabla nueva: `users` en Neon `criza`.

**Seguridad:** Nivel 1 + 2. No nivel 3 (sin datos sensibles de terceros aislados entre sí — toda la data de CRIZA es del equipo).

**Hosting:**
- Railway: cuenta de operación única (`sebasbizzi`), proyecto `criza`, servicio `api`.
- Vercel: cuenta única (`sebasbizzi`), proyecto `criza`.
- Variables cruzadas: `NEXT_PUBLIC_API_URL` (Vercel) = URL del servicio Railway; `NEXTAUTH_URL` = URL del frontend.

**Secuencia de construcción (decisión — no reordenar):**
1. Caso real ganadería bovina — prerequisito, valida el motor antes de construir interfaces
2. Design Gate `criza/api/` — obligatorio antes de código (CLAUDE.md)
3. Design Gate `criza/web/` — obligatorio antes de código (CLAUDE.md)
4. FastAPI + bot Telegram (un servicio)
5. Next.js frontend
6. Deploy Railway + Vercel

---

## Deuda técnica activa

| Item | Descripción | Issue |
|---|---|---|
| Contrato estándar de agentes | Costura — adoptar con los 2 agentes existentes antes de agregar más | SEB-115 |
| Embeddings BGE-m3 | Self-hosted, Capa 1 — DEADLINE antes de ingest DPN | SEB-118 |
| Knowledge Module ligero | RAG + memoria + loop de aprendizaje | SEB-121 |
| FoldX binario | Registrar en foldxsuite.crg.eu + subir al pod | SEB-94 |
| Serverless GPU | RunPod Serverless o Modal — eliminar gestión manual del pod | SEB-95 |
| ~~Tests de scout.py~~ | Scout se jubila (ver decisión 2026-06-02) — no invertir en tests | obsoleto |
| ARCHITECTURE.md en scientific_agent/ | Referencias a Semantic Scholar sin actualizar a OpenAlex | SEB-81 |
| Test E2E | No hay test automatizado del flujo completo | SEB-80 |

---

## Infraestructura GPU — etapas

| Etapa | Estado | Inversión | Capacidad |
|---|---|---|---|
| 0 — API pública | ✅ Activo | $0 | ESMFold 200aa, análisis parcial |
| 1 — RunPod H200 | ✅ Activo | ~$1.39/hr on-demand | ESMFold completo (710aa+), ProteinMPNN rápido |
| 2 — Serverless | Pendiente SEB-95 | ~$0.05-0.10/análisis | Sin gestión manual, cold start ~30-60s |
| 3 — AlphaFold 3 | Backlog | A definir | Binding ligando, complejos multi-cadena |

**Pod actual:** `qruo50jffhrgze` (mighty_brown_lark) — Secure Cloud H200 SXM 141GB, US-CA-2.
SSH: `ssh qruo50jffhrgze-64411a68@ssh.runpod.io -i ~/.ssh/id_ed25519`
Start command: `bash -c "bash /workspace/startup.sh; sleep infinity"`

---

## Decisiones de plataforma relevantes para CRIZA

*(Detalle completo en `KRIZA_Foundation_Document.md`)*

| Decisión | Impacto en CRIZA |
|---|---|
| Multi-tenant desde el día uno | Cuando exista backend: `org_id` en todas las tablas |
| Tenancy híbrido (dedicado ahora / pooled a futuro) | CRIZA y DPN tienen DBs separadas en Neon.tech |
| Abstracción de proveedor de modelo | Cada agente configura su modelo vía `.env`, no hardcodeado |
| Playbook como norma transversal | Todo repo cumple: agents.md + docs/progress/ + tests + .env.example |
| Las 3 costuras (contrato agentes, tenancy, abstracción proveedor) | Adoptar contrato estándar (SEB-115) con los agentes existentes |
