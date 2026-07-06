# Knowledge Base Ligera — CRIZA

> Archivo de reserva (Lectura B). Captura la experiencia acumulada en forma de contexto
> consumible por el agente. No está activo todavía — se usa si no llegamos a construir el
> Knowledge Module completo (SEB-121) a tiempo.
>
> Cómo alimentarlo: al cerrar cada sesión, agregar lo nuevo en la sección que corresponde.
> No duplicar lo que ya está en `criterios_seleccion_producto.md` ni en `metodologia_busqueda_AGENTE.md`
> — solo lo que es "experiencia de instancia": lo que aprendimos corriendo el agente en el mundo real.

---

## 1. Sesgos documentados — cómo se manifiestan y cómo se corrigieron

### 1.1 Sesgo USA/exportador (sesgo de encuadre geográfico)
**Qué hace el modelo:** razona por defecto con marcos de mercados grandes, economías exportadoras
y precios internacionales. Cita impactos en USD millones para EEUU o Brasil como si fueran
directamente aplicables a Córdoba. Sobreestima tamaños de mercado cuando los compara con benchmarks
globales.

**Cómo se detectó:** en corridas tempranas el agente dimensionaba oportunidades con datos de EEUU
sin aclarar que eran inferencias para Argentina.

**Corrección aplicada en la metodología:** regla de dos pruebas para cada dato — veracidad (¿es real?)
y pertinencia (¿aplica a Argentina?). Los datos internacionales se usan como proxy solo cuando se
declara explícitamente que son inferencias.

**Lo que no se puede corregir solo con instrucción:** el modelo no siempre sabe cuándo un dato
"no aplica" localmente porque no tiene ese conocimiento de instancia. El equipo humano (Pablo y
Andrés) cierra esa brecha con conocimiento tácito del sector.

---

### 1.2 Sesgo data-first (razonar desde los datos disponibles, no desde la decisión)
**Qué hace el modelo:** arranca por lo que tiene a mano y deduce oportunidades desde ahí, en lugar
de plantearse primero qué necesita saber para tomar una decisión y buscar eso. Produce análisis
que responden "¿qué encontré?" en lugar de "¿qué necesitamos saber para decidir?".

**Cómo se detectó:** en outputs tempranos el agente rellenaba gaps con datos que tenía disponibles
(aunque fueran irrelevantes o desactualizados) en lugar de declararlos como preguntas abiertas.
Ejemplo concreto: en una corrida afirmó que Argentina tiene múltiples tipos de cambio desde la
memoria del modelo, sin verificar con fuente actual.

**Corrección aplicada:** la metodología introduce razonamiento objective-first explícito — trabajar
"desde la decisión hacia atrás". La regla anti-relleno: si no podés verificar un dato, declaralo
como pregunta abierta, nunca lo rellenes con una suposición disfrazada de hecho.

---

### 1.3 Sesgo de la herramienta-zanahoria (COMTRADE en el divergente)
**Qué hace el modelo:** cuando tiene acceso a datos de volumen de importación (COMTRADE), los usa
como señal de oportunidad. "Se importan X millones de USD de este producto" actúa como zanahoria
que atrae al agente hacia sustitución de importación, aunque el must #12 lo prohíba explícitamente.

**Cómo se detectó:** tras agregar must #12 ("no es sustitución de importación"), el agente seguía
produciendo candidatos de sustitución de importación cuando COMTRADE estaba activo. Al remover
COMTRADE del divergente y re-correr, los candidatos de sustitución cayeron y subieron blue oceans
reales.

**Corrección aplicada:** se removió COMTRADE del agente divergente. El sesgo era de la herramienta,
no del agente. COMTRADE puede ser útil en el convergente (análisis profundo de un candidato ya
seleccionado), pero no en la fase de descubrimiento.

**Principio extraído:** una herramienta que introduce un proxy equivocado de valor puede hacer más
daño que bien aunque el agente tenga la instrucción correcta. El sesgo entra por la estructura de
incentivos del tool, no por el system prompt.

---

### 1.4 Sesgo de los dolores obvios hacia mercados rojos
**Qué hace el modelo:** tiende a desarrollar más los dolores grandes y bien documentados (los que
tienen más literatura), que son precisamente los que ya tienen más jugadores encima.

**Cómo se detectó:** en corridas tempranas los candidatos más desarrollados (mastitis, coccidiosis,
enzimas digestivas) eran exactamente los mercados más competidos.

**Corrección aplicada en la metodología:** instrucción explícita en el paso 2 — los dolores sutiles,
poco documentados o que el sector menciona al pasar son a menudo los mejores blue oceans; perseguirlos
como candidatos, no dejarlos como nota al pie.

---

## 2. Decisiones metodológicas de instancia

### 2.1 Sin ejemplos en lo que ve el agente
Los ejemplos en el system prompt anclan al agente. Si se da un ejemplo de oportunidad, el agente
busca oportunidades similares. Se eliminaron todos los ejemplos de la versión para el agente.

### 2.2 Sin scores numéricos
Los puntajes numéricos dan falsa precisión y el agente los inventa (no tiene base para calcularlos).
La prioridad es cualitativa (alta / media / baja) con razonamiento explícito.

### 2.3 Correr secuencial, no en paralelo
El rate limit de Tier 1 (30k tokens/minuto) hace que las corridas paralelas fallen. Secuencial es
más lento pero confiable. Tier 2 ($40 acumulado en Anthropic) lo resuelve si hace falta escalar.

### 2.4 El divergente es no-determinístico y no-exhaustivo por corrida
Una sola corrida del divergente no barre todo el espacio. El workflow correcto es: correr cada
sector varias veces, unir todos los candidatos, y pasarle la unión al convergente. No confiar en
una sola corrida para declarar que algo "no existe".

### 2.5 Las palancas de utilidad no llevan peso
Una definición de palanca que asigna más peso a unas que otras hace que el agente descarte dolores
que viven en palancas "secundarias". Sin peso fijo, el agente busca dónde está el valor real en
cada candidato.

### 2.6 Riesgo ecológico solo para organismos con exposición al ambiente
Para candidatos que involucran organismos vivos liberados al ambiente, aplicados en superficies
expuestas, o que pueden persistir fuera de un sistema controlado: el agente incluye análisis de
riesgo sobre especies no blanco. Para organismos contenidos (ingeridos, encerrados en sustrato),
la categoría no aplica — incluirla generaría texto vacío o buscaría riesgos donde no los hay.

---

## 3. Candidatos identificados hasta ahora

> Estado al 2026-06-08. Fuente: corridas del agente divergente (ganadería bovina, avicultura,
> porcicultura) + modo A (control de moscas en feedlot).

| Candidato | Sector | Prioridad agente | Estado equipo | Notas |
|---|---|---|---|---|
| Parasitoides de pupa (*Spalangia*, *Muscidifurax*) contra moscas en feedlot | Ganadería bovina / feedlot | **ALTA** | Sin validar | Validación cruzada: Andrés lo detectó independientemente hablando con referente del sector. Riesgo ecológico pendiente de análisis. |
| Bacteriófagos / bacteriocinas anti-*Fusobacterium* (abscesos hepáticos feedlot) | Ganadería bovina / feedlot | **ALTA** | Sin validar | Campo nasciente (literatura 2024-2025). Riesgo regulatorio SENASA como pregunta crítica. |
| Hongos entomopatógenos (*Beauveria bassiana* / *Metarhizium*) contra *Haematobia irritans* | Ganadería extensiva / tambo | **MEDIA** | Sin validar | Eficacia en campo mixta según literatura. Requiere ensayo piloto local. Riesgo ecológico aplica. |
| Consorcio microbiano para tratamiento de cama aviar reutilizada | Avicultura | **ALTA** | Sin validar | Blue ocean más nítido del sector avícola. Vía regulatoria ágil (uso ambiental, no veterinario). |
| Sinbiótico de arranque para pichón en hatchery | Avicultura | **ALTA** | Sin validar | Canal concentrado (pocas incubadoras). Competencia de multinacionales latente. |
| Inoculante LAB local para silaje de maíz | Ganadería bovina / feedlot + tambo | **ALTA** | Sin validar | Riesgo: diferenciación frente a Chr. Hansen / Lallemand. Depende de que cepas locales tengan ventaja real. |
| Hongos entomopatógenos contra garrapata resistente a acaricidas | Ganadería bovina | **ALTA** (consistente en 2 corridas) | Sin validar | Lead más replicable entre corridas. |
| Probiótico peripartal para cetosis subclínica | Tambo | **MEDIA** | Sin validar | Riesgo técnico: eficacia en campo de probióticos ruminales es inconsistente. |
| Bioprotector de arranque para pichón ("cepa local + valor diferencial") | Avicultura | **Sin clasificar** | Sin validar | Candidato borderline. No es sustitución de importación si la propuesta de valor es la cepa local adaptada. |

---

## 4. Lo que no funcionó (aprendizajes negativos)

| Experimento | Por qué no funcionó | Qué se aprendió |
|---|---|---|
| COMTRADE en el agente divergente | Actuaba como zanahoria hacia sustitución de importación incluso con must #12 activo | El sesgo puede entrar por la herramienta, no por el prompt. Quitar la herramienta fue más efectivo que reforzar la instrucción. |
| Must #12 solo, sin quitar COMTRADE | El agente lo cumplía en el texto pero el razonamiento seguía siendo import-substitution driven | Una instrucción prohibitiva no cancela el incentivo de una herramienta mal ubicada. |
| Scores numéricos de prioridad | El agente inventaba números sin base real | Prioridad cualitativa + razonamiento explícito es más honesto y más útil. |
| Ejemplos en el system prompt | Anclaban al agente hacia oportunidades similares a los ejemplos | Sin ejemplos, el agente explora más libremente. |

---

## 5. Preguntas abiertas de instancia

> Preguntas que el agente no puede cerrar solo — requieren el equipo humano o datos locales.

- ¿Cuántos establecimientos de feedlot hay en Córdoba y qué volumen de moscas manejan?
- ¿Hay algún proveedor local de parasitoides (aunque sea informal) operando en Argentina?
- ¿El operador de feedlot percibe el problema de moscas como dolor que "le duele" o lo naturaliza?
- ¿Qué categoría regulatoria aplica en SENASA para parasitoides de insectos en ganadería?
- ¿Las plantas de incubación cordobesas ya usan sinbióticos en spray, y cuáles?
- ¿Quién toma la decisión de compra en la avicultura integrada: el productor o el integrador?
- ¿Cuánto gasta hoy un feedlot mediano en control de moscas por temporada?
