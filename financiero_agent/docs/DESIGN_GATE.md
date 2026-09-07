# Design Gate — Agente Financiero

**Versión:** 1.0
**Fecha:** 2026-09-07
**Módulo:** `criza/financiero_agent/`
**Capa:** 2 (instancia CRIZA)
**Estado:** ✅ LISTO

---

## 1. Identidad

| Pregunta | Respuesta |
|---|---|
| ¿Qué es? | Quinto especialista de la biblioteca (`docs/PROPUESTA_DESTINO.md` §5) y el primero construido de cero para cubrir un gap identificado por el Conductor (ver `docs/progress/2026-08-24.md`, tabla "Equipo IA — cobertura y gaps"): **Modelo económico-financiero**. Responde una pregunta que ningún otro especialista cubre: dado un producto/proceso candidato ya identificado (por Biotecnólogo/Microbiólogo/Ingeniero Ambiental/Agrónomo) y su mercado (Agente de Mercado), ¿es financieramente viable, con qué inversión, en qué plazo, y con qué sensibilidad a los supuestos? |
| ¿Qué problema resuelve en una oración? | Sebas: "vamos con el modelo económico-financiero, este tiene que ser muy profesional" — sin este agente, el expediente de decisión llega a Sebas sin números (CAPEX/OPEX/VAN/TIR), el paso final antes de decidir queda sin cubrir. |
| ¿Quién lo usa? | Sebas, directo o vía el Conductor (`correr_especialista`, sexta entrada en `_ESPECIALISTAS_CASOS`). |
| ¿De qué depende? | `utils/ai_client.py` NO se usa (ver decisión C) — cliente nativo Anthropic (mismo patrón que `market_agent`, por `web_search`). `utils/casos.py` (incluye `crear_pendiente`, nuevo), `utils/bcra.py` (nuevo), `market_agent/tools` (reuso de `search_series`/`get_series_values`/`search_official_stats`/`fetch_page_text`/`buscar_corpus_cientifico`), `knowledge_module.preflight`, `knowledge_module.aprendizaje`. |
| ¿Qué depende de él? | El Conductor, vía `correr_especialista`. Consume (`ver_informe_especialista`) los informes de los otros 5 especialistas sobre el mismo frente — es, por diseño, el último eslabón antes de la decisión humana. |
| ¿Milestone? | Sexto agente de la biblioteca de especialistas, 2026-09-07 (Etapa 21). |

---

## 2. Trazabilidad diseño → implementación

### Por qué este agente, ahora

Gap identificado por el propio Conductor en una conversación real preparando la reunión con
Helios (2026-08-24) — "Modelo económico-financiero" es uno de 4 roles sin cobertura. Sebas lo
priorizó explícitamente: "vamos con el modelo económico-financiero, este tiene que ser muy
profesional." Se preguntó nivel de rigor e input antes de codear (ver decisión A) — "Modelo
financiero completo" y "las dos cosas, incluso el agente podría pedir qué información necesita
para trabajar."

### Herramientas — verificadas en vivo, no asumidas

- **BCRA API pública** (`utils/bcra.py`, nuevo) — verificado real 2026-09-07: `GET
  https://api.bcra.gob.ar/estadisticas/v4.0/monetarias` (1.610 variables, sin auth; v3.0 está
  deprecada — 410 Gone) y `GET .../monetarias/{id}?desde=&hasta=&limit=` (histórico real). Con
  fecha de hoy: tipo de cambio minorista (id 4) $1.528,60/USD, BADLAR bancos privados (id 7)
  23,25% n.a. — datos reales, no simulados. Fuente para tasa de descuento, inflación y tipo de
  cambio (ver decisión D, sesgo de tasa de descuento).
- **market_agent/tools** (reuso, no duplicado) — `search_series`/`get_series_values`
  (datos.gob.ar, series INDEC/MAGyP: producción, precios) y `search_official_stats` (datasets
  complementarios) ya sirven para comparables de mercado/costos que el modelo financiero
  necesita igual que el Agente de Mercado. `fetch_page_text` para comparables de costo/precio en
  páginas públicas (proveedores, cotizaciones). `buscar_corpus_cientifico` para literatura sobre
  costos de proceso/escala (CONICET+INTA).
- **`web_search`** (nativo Anthropic) — mismo motivo y misma excepción permanente que Mercado:
  comparables de CAPEX/OPEX/precios vigentes no están en ningún corpus local, y "recordar" un
  costo del entrenamiento es exactamente el sesgo de anclaje que hay que evitar (ver decisión D).
- **`crear_pendiente`** (nuevo, `utils/casos.py`) — hasta esta etapa NINGÚN agente, ni el
  Conductor, podía crear un pendiente (solo leerlos). El Agente Financiero lo necesita para
  cumplir el segundo requisito de Sebas ("el agente podría pedir qué información necesita para
  trabajar") sin bloquearse ni inventar el dato faltante. Vive en `utils/casos.py` porque
  cualquier especialista futuro puede necesitar lo mismo — no es específico de este agente.

### Entidades

| Entidad | Descripción | Estado |
|---|---|---|
| `ver_informe_especialista` | Lee informes de otros especialistas sobre el mismo frente (mismo patrón que los otros 5). Es la ÚNICA fuente de qué producto/proceso/mercado evaluar — el agente nunca inventa el objeto de su propio análisis. | ✅ construido |
| `search_series` / `get_series_values` / `search_official_stats` / `fetch_page_text` / `buscar_corpus_cientifico` | Reusadas de `market_agent/tools` sin duplicar código. | ✅ construido (reuso) |
| `search_bcra` (nuevo) | `utils/bcra.py::search_bcra_variables`/`get_bcra_values` — tasas de referencia, inflación, tipo de cambio reales para fundamentar la tasa de descuento y proyecciones. | ✅ construido |
| `web_search` (nativo) | Comparables de costo/inversión/precio vigentes. | ✅ construido (excepción ya decidida para Mercado) |
| `pedir_informacion_faltante` (nuevo) | Wrapper de `utils/casos.py::crear_pendiente` — el agente declara qué dato le falta para poder trabajar, en vez de asumirlo. | ✅ construido |
| `submit_modelo_financiero` | Output único — ver schema completo en decisión B. | ✅ construido |

### Contrato SEB-115

```python
INPUT_CONTRACT  = {"agent": "financiero", "version": "1.0",
                   "fields": {caso, tarea, contexto, conocimiento: {"frente_id": str}, herramientas}}
OUTPUT_CONTRACT = {"agent": "financiero", "version": "1.0",
                   "km_escribe": ["documento_caso conectado vía frente_produce_documento",
                                  "pendiente conectado al caso vía tiene_pendiente (si pidió información)"],
                   "fields": {análisis, nivel_confianza, recomendaciones, próximo_agente, nuevo_conocimiento}}
```

Solo `frente_id` desde el arranque — ningún caso real necesita el modelo `oportunidad_id` viejo
para un agente construido hoy (mismo criterio que los 5 anteriores).

### KM write

| Tipo de output | Qué contiene | Key en KM | Cómo | Estado |
|---|---|---|---|---|
| **Resultado estructurado + informe** | Modelo financiero completo (CAPEX/OPEX/P&L/cash flow/VAN/TIR/payback/sensibilidad) | `documento_caso` conectado vía `frente_produce_documento` | La costura, no el agente | ✅ construido |
| **Pendientes** | Información faltante que el agente pidió en vez de asumir | `pendiente` conectado al caso vía `tiene_pendiente` | El agente escribe esto directo, vía `crear_pendiente` | ✅ construido |
| **Token usage** | Tokens consumidos | `props.token_usage.financiero` del **frente** | El agente escribe esto directo | ✅ construido |
| **Aprendizaje** | Lecciones del caso | área `lecciones` | 🔵 pendiente — misma deuda intencional que los otros 5 | — |

---

## 3. Checklist del playbook

### Estructura de archivos

- [x] `financiero_agent.py` — SYSTEM_PROMPT + TOOLS + `run_agent_desde_frente()` + `run()` + chat
- [x] `run.py`
- [x] `docs/DESIGN_GATE.md` — este archivo
- [x] `.env.example`
- [x] `tests/`

### Testing

- [x] Test: `TOOLS` tiene la cantidad esperada de tools
- [x] **Test explícito del checklist anti-sesgo: `SYSTEM_PROMPT` no contiene ninguna de las
      strings "Helios", "biogás", "biodigestor", "Mateo", "Andrés"** — mismo control que los
      otros 5 especialistas.
- [x] **Test explícito del chequeo final pedido por Sebas ("sólo te pido último chequeo de que
      no tenga sesgos")**: `SYSTEM_PROMPT` no contiene una tasa de descuento numérica fija
      (ningún "%" hardcodeado como default), no asume moneda única sin declararla, y contiene la
      instrucción explícita de derivar la tasa de descuento de `search_bcra`, nunca de un default
      de manual.
- [x] Test: `run()` requiere `frente_id`, no acepta `oportunidad_id`
- [x] Test: `run_agent_desde_frente` mock captura `submit_modelo_financiero`
- [x] Test: dispatch de `search_bcra`/`pedir_informacion_faltante`/tools reusadas
- [x] `utils/tests/test_bcra.py` nuevo — unit (mock) + integration (real, sin auth)
- [x] `utils/tests/test_casos.py` — tests nuevos de `crear_pendiente`
- [x] Al menos 1 corrida real — vía sesión de chat HTTP real (`iniciar_sesion`/`enviar_mensaje`,
      no mockeada) contra el `Frente técnico` real de Helios, ver `docs/progress/2026-09-07.md`
      para el detalle completo. Resumen: leyó 3 informes reales del Biotecnólogo
      (`ver_informe_especialista`, sin que se le dijera cuáles), usó `search_bcra` (6 consultas
      reales — encontró el tipo de cambio real, no encontró tasas de interés en esa corrida por
      un bug de matching ya corregido, ver abajo), `web_search` real (precios ectoína/
      fertilizantes), `buscar_corpus_cientifico` (papers CONICET/INTA reales citados), y creó 3
      pendientes reales vía `pedir_informacion_faltante` — confirmados presentes en el KM
      después de la corrida (CAPEX real de planta struvita, costo actual de gestión del
      efluente, escala real de producción prevista). Declaró honestamente `tasa_descuento` como
      `a-confirmar` cuando `search_bcra` no encontró la tasa buscada, en vez de inventar un
      número — el comportamiento anti-sesgo correcto incluso en el caso de falla de la
      herramienta.

**3 bugs reales encontrados y arreglados durante esta verificación** (ninguno vía tests, los 3
vía la corrida real contra producción):
1. `conductor.py::serializar_mensajes` solo contemplaba `ContentBlock` (`utils/ai_client.py`)
   para persistir sesiones de chat — nunca los bloques nativos del SDK de Anthropic
   (`TextBlock`/`ToolUseBlock`, pydantic v2) que produce cualquier agente Anthropic-only.
   Revienta con `TypeError: Object of type TextBlock is not JSON serializable` al persistir
   CUALQUIER turno de chat con Mercado o Financiero. Corregido generalizando a un helper
   (`_bloque_a_dict`) que también llama `.model_dump()` si existe — afecta retroactivamente
   también al chat de Mercado, que nunca había ejercitado este camino completo (HTTP +
   persistencia) en su propia verificación de la Etapa 20. Tests nuevos en
   `conductor/tests/test_conductor.py`.
2. `utils/bcra.py::search_bcra_variables` exigía el query completo como substring literal — un
   query natural como `"BADLAR bancos privados"` no matcheaba la descripción real (`"Tasa de
   interés BADLAR DE bancos privados"`) por la palabra "de" de más, y el agente reportaba la tasa
   de descuento como `a-confirmar` en vez de fundamentarla en datos reales — exactamente el
   chequeo anti-sesgo central de este agente (decisión D). Corregido con matching AND de palabras
   sueltas; reverificado directo contra el query real que había fallado (ahora 7 resultados,
   incluida la variable BADLAR real). Test nuevo en `utils/tests/test_bcra.py`.
3. `uvicorn --reload` solo observa `api/` — un cambio en `conductor/conductor.py` o
   `utils/bcra.py` (fuera de ese árbol) no dispara reload; hay que matar y reiniciar el proceso
   completo. Mismo gotcha ya documentado en la Etapa 20 (`docs/progress/2026-09-07.md`).
4. **Encontrado después de sumar COMTRADE (decisión E) al re-verificar**: el fix del bug #1
   (`.model_dump()` sin más) no alcanzaba — `server_tool_use`/`web_search_tool_result` incluyen
   un campo `text: None` que la API de Anthropic rechaza como *"Extra inputs are not permitted"*
   al reenviarlo como historial en el turno SIGUIENTE al que generó el bloque (no revienta al
   persistir, revienta un turno después, al re-leer y reenviar). Corregido con
   `model_dump(exclude_none=True)`. Test nuevo en `conductor/tests/test_conductor.py`.
   Reverificado real con una sesión nueva de punta a punta: el agente llamó `search_bcra`,
   `search_comtrade` (`hs_code=3105`, trajo el valor real 2023: USD 805M importado), `web_search`,
   `buscar_corpus_cientifico` y `pedir_informacion_faltante` en una sola corrida, sin ningún error
   de serialización en ningún turno subsiguiente.

---

## 4. Scope explícito por versión

| Feature | Versión | Razón |
|---|---|---|
| Camino `oportunidad_id` | No planeado | Mismo criterio que los otros 5. |
| Simulación Montecarlo de sensibilidad | v2, si Sebas lo pide | El análisis de escenarios (optimista/base/pesimista) declarado en el schema alcanza para v1 — una simulación probabilística completa es un salto de complejidad que nadie pidió todavía. |
| Comparación multi-moneda automática con cobertura de riesgo cambiario cuantificada | v2 | v1 declara el riesgo cambiario explícitamente (ver decisión D) pero no lo cuantifica con instrumentos de cobertura reales — nadie pidió eso todavía y requeriría datos de mercado de futuros/opciones que no están verificados. |
| Persistencia de lecciones de caso | backlog | Misma deuda intencional que los otros 5. |

---

## 5. Decisiones requeridas antes de arrancar

| # | Pregunta | Opciones | Decisión tomada | Fecha |
|---|---|---|---|---|
| A | ¿Nivel de rigor y de dónde saca el input? | Modelo simplificado / Modelo financiero completo · Solo conversación / Solo informes de otros / Ambas | **Modelo financiero completo** (CAPEX, OPEX, P&L multi-año, cash flow, VAN, TIR, payback, sensibilidad) — **ambas fuentes de input**, y el agente puede pedir explícitamente qué información le falta (`crear_pendiente`) en vez de asumirla o bloquearse. | 2026-09-07 |
| B | ¿Qué schema exacto para `submit_modelo_financiero`? | Ver detalle abajo | Ver bloque de código más abajo — supuestos con estado establecido/asumido/a-confirmar, CAPEX, OPEX, ingresos proyectados, P&L, cash flow, VAN/TIR/payback, escenarios optimista/base/pesimista, riesgo cambiario declarado si aplica, `fuentes_y_cobertura`. | 2026-09-07 |
| C | ¿Cliente nativo Anthropic (como Mercado) o traductor genérico (`utils/ai_client.py`, como los otros 4)? | Nativo (permite `web_search`) / Genérico (portable entre proveedores) | **Nativo** — el modelo financiero necesita comparables de costo/inversión/precio vigentes que ningún corpus local tiene; "recordar" un costo del entrenamiento es el mismo sesgo de anclaje que ya se prohibió para Mercado. Misma excepción permanente, mismo motivo. | 2026-09-07 |
| D | **Chequeo final anti-sesgo, pedido explícito de Sebas** ("sólo te pido último chequeo de que no tenga sesgos") | Ver detalle abajo | Ver tabla de riesgos de sesgo específicos del dominio financiero, cada uno con su mitigación concreta en el diseño (abajo). | 2026-09-07 |
| E | **¿COMTRADE (importaciones reales por HS)?** — Sebas, tras ver la primera corrida real: "es importante que pueda acceder a toda la información necesaria para cumplir sus funciones." | Incluir (reusando `market_agent/tools/comtrade.py`) / no incluir (mismo criterio que Mercado) | **Incluir** — Mercado la excluyó (decisión H de su Design Gate) porque sesga la elección de PRODUCTO hacia sustitución de importaciones; ese motivo no aplica acá porque Financiero no elige producto, solo lo cotiza. Verificada real antes de sumarla (`get_import_data(hs_code="3105")` → datos reales de 2022, USD 1,04/kg CIF). Se usa solo como precio de referencia (`search_comtrade`), con instrucción explícita de no razonar sobre conveniencia de importar/sustituir con ella. Key ya existía (`market_agent/.env`), copiada a `api/.env` (el proceso real que corre los especialistas). | 2026-09-07 |

### Detalle decisión B — schema `submit_modelo_financiero`

```
supuestos: [{variable, valor, estado: establecido|asumido|a-confirmar, fuente}]  # obligatorio, cada supuesto declarado
capex: {items: [{concepto, monto, moneda, estado, fuente}], total, estado}
opex: {items: [{concepto, monto_mensual, moneda, estado, fuente}], total_mensual, estado}
ingresos_proyectados: {supuesto_precio, supuesto_volumen, proyeccion_anual: [{año, monto, moneda}], estado}
pyl_multianual: [{año, ingresos, costos, resultado}]
flujo_de_caja: [{año, flujo_neto}]
tasa_descuento: {valor_pct, justificacion, fuente_bcra, estado}   # obligatorio citar search_bcra
van: {valor, moneda, estado}
tir: {valor_pct, estado}
payback: {años, estado}
riesgo_cambiario: {aplica: bool, descripcion}                     # obligatorio declararlo, aunque sea "no aplica"
analisis_sensibilidad: {optimista: {...}, base: {...}, pesimista: {...}}
informacion_faltante_pedida: [{descripcion, pendiente_id}]        # si usó pedir_informacion_faltante
fuentes_y_cobertura: {...}                                        # mismo patrón que los otros 5
informe_completo: str
lecciones_caso: [str]
```

### Detalle decisión D — riesgos de sesgo específicos de un modelo financiero, y su mitigación

| Riesgo de sesgo | Por qué es real acá (más allá del checklist genérico anti-caso) | Mitigación en el diseño |
|---|---|---|
| **Tasa de descuento de manual** (ej. 10-12% "estándar" de textbook USA) | En contexto argentino, con tasas de referencia reales órdenes de magnitud más altas (BADLAR ~23% n.a., verificado 2026-09-07), un descuento tipo textbook infla artificialmente el VAN de cualquier proyecto. | `tasa_descuento` es campo obligatorio con `fuente_bcra` obligatoria — el SYSTEM_PROMPT instruye explícitamente derivarla de `search_bcra` + una prima de riesgo justificada, nunca de un número "típico" recordado. Test explícito verifica que el prompt no tenga un % hardcodeado como default. |
| **Costos/precios "recordados" sin fuente** | Mismo sesgo de anclaje ya prohibido para Mercado — un costo plausible pero fabricado no es detectable a simple vista en un modelo financiero. | Misma regla textual que Mercado: "NUNCA un costo/precio sin fuente real de búsqueda." `web_search`/`fetch_page_text`/`search_series` son las únicas fuentes válidas para un número puesto en el modelo — si no hay fuente, va como `a-confirmar` o se pide vía `pedir_informacion_faltante`. |
| **Sesgo optimista en proyecciones** (común en modelos armados para "vender" una oportunidad) | Un modelo que solo declara un caso base optimista esconde el riesgo real de la decisión. | `analisis_sensibilidad` es obligatorio con un escenario pesimista real (no "base menos un poco") — el SYSTEM_PROMPT instruye explícitamente que el escenario pesimista use costos más altos y/o ingresos más bajos que los del caso base, con su propia justificación. |
| **Riesgo cambiario ignorado** | Si el Agente de Mercado recomendó alcance de exportación (ingresos en USD) sobre un caso con costos en ARS (o viceversa), un modelo que no trata la conversión explícitamente puede sobreestimar o subestimar el resultado. | `riesgo_cambiario` es campo obligatorio (aunque la respuesta sea "no aplica, todo en la misma moneda") — el SYSTEM_PROMPT instruye leer el alcance geográfico que recomendó Mercado (vía `ver_informe_especialista`) antes de fijar la moneda de ingresos vs. costos. |
| **El agente decide en vez de armar** | Un modelo financiero "atractivo" puede leerse implícitamente como una recomendación de GO. | El SYSTEM_PROMPT es explícito: el agente arma el modelo con sus números y gaps, nunca concluye "conviene" o "no conviene" — mismo límite que rige a los otros 5 (CLAUDE.md: "el sistema ARMA, el humano ELIGE"). |
| **Sesgo sectorial/tecnológico en el prompt** | Checklist heredado — un `SYSTEM_PROMPT` que mencione un caso concreto sesga cualquier corrida futura sobre un caso distinto. | Mismo checklist que los otros 5: cero menciones de Helios/biogás/biodigestor/Mateo/Andrés — test explícito. |

---

## 6. Estado del gate

**Estado actual:** ✅ LISTO

Decisiones A-E cerradas, ninguna abierta. Primer especialista construido de cero desde el
Biotecnólogo (2026-08-17) — a diferencia de la reconexión de Mercado (Etapa 20), acá no había
código previo que adaptar. El chequeo anti-sesgo pedido explícitamente por Sebas (decisión D)
queda documentado como tabla de riesgos concretos + mitigación, no como una afirmación genérica
de "no tiene sesgos" — cada riesgo tiene su control verificable (test o instrucción textual
específica en el prompt), y la mitigación de "tasa de descuento" (decisión D, fila 1) se validó
en vivo dos veces: primero falló de la forma correcta (el agente declaró `a-confirmar` en vez de
inventar un número, cuando `search_bcra` no encontró la tasa por un bug de matching), y después
del fix del bug la misma búsqueda encontró la tasa real — evidencia de que el chequeo anti-sesgo
funciona incluso cuando la herramienta subyacente falla, no solo cuando todo sale bien.

**Nota operativa:** la corrida real de verificación creó 3 pendientes reales en el caso Helios
(vía `pedir_informacion_faltante`) — quedan intencionalmente en el KM, no son pollution de test:
son gaps de información genuinos que el propio caso real tiene (CAPEX real de planta struvita,
costo actual de gestión del efluente, escala real de producción prevista).

**Deuda intencional documentada:**
- Camino `oportunidad_id` → no planeado
- Simulación Montecarlo → v2, si se pide
- Cobertura de riesgo cambiario cuantificada → v2, si se pide
- Persistencia de lecciones de caso → backlog, misma deuda que los otros 5
- El chat no escribe lecciones al cierre → mismo backlog que los otros 5
