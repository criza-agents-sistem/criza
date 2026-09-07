# Design Gate — Agente de Mercado (SEB-148)

**Versión:** 2.0
**Fecha:** 2026-06-16 · última revisión 2026-09-07 (Etapa 20 — reconexión a casos.yaml)
**Módulo:** `criza/market_agent/` (Capa 2 — instancia CRIZA)
**Estado:** ✅ LISTO — decisiones A–N cerradas (2026-09-07)

> **Regla de uso:** se crea ANTES de codear. Desarrollo arranca con estado 🟡 o ✅.
> Trazabilidad: `criza/docs/architecture.md` + épico SEB-143 / issue SEB-148.
> Contratos heredados: `knowledge_module/docs/APRENDIZAJE_LOOP_GATE.md` (SEB-156) ·
> `knowledge_module/docs/KM_MOTOR_GENERICO_GATE.md` · `criza/docs/expediente_decision_SPEC.md`.

---

## 1. Identidad

| Pregunta | Respuesta |
|---|---|
| ¿Qué es? | Agente investigador de mercado v1. Lee una oportunidad del KM, levanta datos de los cruces 1 (demanda), 3 (competencia) y 4 (viabilidad en contexto) + anclas del bloque 6, y escribe los resultados de vuelta en la ficha. |
| ¿Qué problema resuelve? | Sin datos de mercado verificados, el expediente de decisión no tiene los cruces 1/3/4 completos — solo asunciones. El agente los puebla con datos reales (corpus CONICET, series oficiales, SENASA, web). |
| ¿Qué NO hace? | No elige la oportunidad ganadora. No recomienda GO/NO-GO. No llena los cruces 2 (capacidad/tecnología — eso es Evidencia Científica). No inventa números sin fuente. No analiza importaciones (no es sustitución de importaciones). |
| ¿Quién lo usa? | Sebas vía `run.py` (manual en v1). En v2+: Orquestador (SEB-152). |
| ¿De qué depende? | Motor KM (`motor/api.py`), `aprendizaje.py` (SEB-156), corpus_cientifico (SEB-150), datos.gob.ar, Neon. |
| ¿Qué depende de él? | Armador (SEB-145) lee los cruces 1/3/4 + bloque 6 anclas que este agente escribe. |
| ¿Milestone? | M1 — primer expediente con cruces de mercado reales. |

---

## 2. Trazabilidad diseño → implementación

### Entidades / componentes

| Entidad | Archivo | Capa | Scope v1 | Estado |
|---|---|---|---|---|
| **Agente de Mercado v1** | `market_agent/market_agent.py` | 2 | ✅ incluido | 🔜 refactorizar v0 |
| **Tool `buscar_corpus_cientifico`** | `market_agent/tools/corpus.py` (nueva) | 2 | ✅ incluido | 🔜 construir |
| **Tool `search_series`** | `market_agent/tools/datosgobar.py` (ya existe) | 2 | ✅ incluido | 🔜 wirear |
| **Tool `get_series_values`** | `market_agent/tools/datosgobar.py` (ya existe) | 2 | ✅ incluido | 🔜 wirear |
| **SENASA / regulatorio** | `market_agent/tools/web_fetch.py` (ya existe) + URLs SENASA en descripción | 2 | ✅ incluido (fetch_page_text) | 🔜 actualizar descripción |
| **System prompt orientado a cruces** | `market_agent/market_agent.py` | 2 | ✅ incluido | 🔜 reescribir |
| **KM read — leer oportunidad** | `motor/api.py` `obtener` (ya existe) | 1 | ✅ incluido | ✅ reusar |
| **KM write-back — cruces 1/3/4 + bloque 6** | `motor/api.py` `actualizar_props` (ya existe) | 1 | ✅ incluido | ✅ reusar |
| **Loop de aprendizaje** | `knowledge_module/aprendizaje.py` (SEB-156, ya existe) | 1 | ✅ incluido | ✅ reusar |
| **`run.py` actualizado** | `market_agent/run.py` | 2 | ✅ incluido | 🔜 actualizar |
| **Tests formales** | `market_agent/tests/` | — | ✅ incluido | 🔜 ampliar |

### Contratos / interfaces

| Contrato | Entre quiénes | Estado |
|---|---|---|
| `obtener(oportunidad_id)` → ficha con props | motor → agente (input) | ✅ reusar |
| `actualizar_props(oportunidad_id, {"mercado": {...}})` → cruces 1/3/4 + bloque 6 | agente → motor (output) | ✅ reusar |
| `bloque_lecciones_para_prompt(agente="mercado", consulta=contexto)` | aprendizaje → agente (inicio) | ✅ reusar (SEB-156) |
| `guardar_leccion_caso(contenido, agente, contexto)` | agente → aprendizaje (cierre) | ✅ reusar (SEB-156) |
| `cierre_aprendizaje(agente, lecciones_auto)` | aprendizaje → run.py (cierre) | ✅ reusar (SEB-156) |
| `motor_api.buscar(area="corpus_cientifico", consulta, tipo="fuente")` | corpus (SEB-150) → tool | ✅ reusar (SEB-150) |

---

## 3. Tools del agente v1 (6 tools)

| Tool | Función | Cuándo usa | Ya existe | Cambio |
|---|---|---|---|---|
| `buscar_corpus_cientifico` | Búsqueda semántica en el corpus CONICET local — papers argentinos | Cruce 1 (evidencia del dolor, literatura local), Cruce 3 (estado del arte de soluciones) | ❌ nueva | Crear `tools/corpus.py` |
| `search_official_stats` | CKAN datos.gob.ar (datasets INDEC/MAGyP) | Cruce 1 (producción, consumo), Cruce 4 (indicadores sectoriales) | ✅ | Sin cambio |
| `search_series` | API de Series datos.gob.ar (series con valores) | Cruce 1 (series producción porcina/avícola/agrícola — tamaño del sector) | ✅ función | Wirear como tool |
| `get_series_values` | Valores de una serie por id | Cruce 1 (últimos 12 valores de la serie elegida) | ✅ función | Wirear como tool |
| `fetch_page_text` | Web fetch (SENASA, BCR, asociaciones, competidores) | Cruce 3 (competidores locales, soluciones existentes), Cruce 4 (encuadre regulatorio SENASA) | ✅ | Actualizar descripción con URLs SENASA |
| `draft_outreach_email` | Redacta email para gaps que no resuelve ninguna fuente pública | Al cerrar, si quedan gaps críticos a-confirmar | ✅ | Sin cambio |

**SENASA:** no requiere tool dedicada. `fetch_page_text` + URLs SENASA en la descripción. La descripción de la tool actúa como instrucción de navegación.

### Patrón de extensión — conectores locales (INTA, CREA, otros)

Agregar una fuente local = **un archivo + una entrada en la lista de tools**. Sin tocar el agente.

```
criza/market_agent/tools/
  ├── corpus.py          ← CONICET (v1, ya incluido)
  ├── datosgobar.py      ← Series datos.gob.ar (ya existe)
  ├── ckan.py            ← CKAN datos.gob.ar (ya existe)
  ├── web_fetch.py       ← Web + SENASA (ya existe)
  ├── inta.py            ← INTA (futuro — cuando se conecte)
  └── crea.py            ← CREA (futuro — cuando se conecte)
```

**Contrato de cada conector:**
1. Función `search_<fuente>(query: str, ...) -> list[dict]` con campos uniformes: `titulo`, `resumen`, `fuente`, `url`, `fecha`
2. Registrado como tool en `market_agent.py` con descripción que incluye: qué tiene esa fuente, cobertura, cuándo consultarla
3. La **descripción de la tool** es el manual del agente — sin descripción buena, el agente no sabe cuándo usarla

Cuando INTA o CREA tengan API o formato scrapeable, se agrega `tools/inta.py` y se registra la tool. El agente lo incorpora automáticamente.

---

## 4. Schema del write-back al KM

El agente escribe en los props de la `oportunidad` bajo la clave `"mercado"`:

```json
{
  "mercado": {
    "cruce_1": {
      "tamaño":    {"valor": "...", "unidad": "...", "fuente": "...", "estado": "establecido|asumido|a-confirmar"},
      "urgencia":  {"valor": "...", "estado": "...", "peso": "alto|medio|bajo"},
      "evidencia": ["paper CONICET 1", "dato MAGyP", "serie producción porcina"]
    },
    "cruce_3": {
      "qué_existe":       {"valor": "...", "estado": "...", "fuente": "..."},
      "registros_senasa": {"estado": "a-confirmar", "dónde_confirmar": "https://www.senasa.gob.ar/senasa/..."},
      "intensidad":       {"valor": "vacío|débil|fuerte", "estado": "..."}
    },
    "cruce_4": {
      "encuadre_regulatorio":    {"valor": "...", "estado": "asumido|a-confirmar"},
      "accesibilidad_mercado":   {"valor": "...", "estado": "...", "dónde_confirmar": "..."},
      "factibilidad_costo":      {"valor": "...", "estado": "asumido|a-confirmar", "dónde_confirmar": "..."}
    },
    "bloque_6_anclas": {
      "inversión":    {"comparables": "...", "estado": "a-confirmar|asumido"},
      "regulatorio":  {"camino": "...", "plazo": "incógnita conocida", "estado": "asumido"}
    },
    "gaps_prioritarios": ["gap 1", "gap 2"],
    "agente": "mercado",
    "fecha": "YYYY-MM-DD",
    "modelo": "claude-sonnet-4-6"
  }
}
```

**Convención de estado** (idéntica a `expediente_decision_SPEC.md`):
- `establecido` — verificado, tiene fuente citable.
- `asumido` — sin verificar, lleva `peso` (cuánto depende la tesis de este supuesto).
- `a-confirmar` — no disponible públicamente, lleva `dónde_confirmar`.

---

## 5. Flujo de la corrida v1

```
run.py
  │
  ├─ 1. Leer oportunidad del KM (obtener oportunidad_id)
  │      O: modo texto-libre (sin KM — para testing)
  │
  ├─ 2. Inyectar lecciones al system prompt
  │      bloque_lecciones_para_prompt(agente="mercado", consulta=contexto)
  │
  ├─ 3. Loop agéntico (market_agent.run_agent)
  │      → buscar_corpus_cientifico (cruce 1: evidencia local del dolor)
  │      → search_series + get_series_values (cruce 1: tamaño del sector)
  │      → search_official_stats (cruces 1/4: datasets MAGyP/INDEC)
  │      → fetch_page_text SENASA + web (cruce 3: competidores; cruce 4: regulatorio)
  │      → draft_outreach_email (gaps irreducibles, max 2)
  │      → produce: markdown resumen + dict cruces_1_3_4
  │
  ├─ 4. Write-back al KM
  │      actualizar_props(oportunidad_id, {"mercado": cruces_1_3_4})
  │
  ├─ 5. guardar_leccion_caso (el agente escribe lo que aprendió del dominio)
  │
  └─ 6. cierre_aprendizaje (prompt al humano para lección de proceso)
```

---

## 6. Checklist del playbook

### Seguridad Nivel 1
- [ ] `ANTHROPIC_API_KEY` en `.env`, nunca en código. (`.env` ya en `.gitignore`.)
- [ ] Sin credenciales en historial de git.

### Testing
- [ ] **Unit:** `buscar_corpus_cientifico` con mock del motor; tools `search_series`, `get_series_values` con fixtures; filtro de agente en lecciones.
- [ ] **Integration:** corrida real contra oportunidad del KM → verifica que `actualizar_props` escribe cruces; lecciones se guardan y leen.
- [ ] Tests heredados de v0 siguen pasando (no regresión).

### Observabilidad
- [ ] Log de cada tool call con resultado (success/error) — ya presente en v0.
- [ ] Log del write-back: `oportunidad_id` + resumen de campos escritos.

---

## 7. Scope explícito v1

| Feature | Versión | Razón |
|---|---|---|
| Conectores INTA / CREA | v2 | No disponibles aún. Patrón de extensión diseñado (§3) — agregar = un archivo. |
| Contrato estándar input/output Orquestador (SEB-115) | v2 | Orquestador (SEB-152) no existe aún. En v1: input manual vía `run.py`. |
| Gmail MCP (envío real de emails) | v2 | Prerequisito: Orquestador con flujos asíncronos. |

---

## 8. Decisiones cerradas

| # | Pregunta | Decisión | Fecha |
|---|---|---|---|
| A | ¿KM write-back en v1? | ✅ **Sí** — `actualizar_props` bajo clave `"mercado"`. Schema definido en §4. | 2026-06-16 |
| B | ¿SENASA = tool dedicada o fetch_page_text? | ✅ **fetch_page_text** + URLs SENASA en la descripción de la tool. No hay razón para una tool extra en v1. | 2026-06-16 |
| C | ¿`search_series` y `get_series_values` = tool nueva o fusionada con `search_official_stats`? | ✅ **Tools separadas** — flujo de 2 pasos natural (buscar serie → traer valores); fusionarlas opaca el razonamiento del agente. | 2026-06-16 |
| D | ¿Loop de aprendizaje en este agente? | ✅ **Sí** — implementa contrato de SEB-156 (ya Done): `bloque_lecciones_para_prompt` + `guardar_leccion_caso` + `cierre_aprendizaje`. | 2026-06-16 |
| E | ¿Input = oportunidad_id KM o texto libre? | ✅ **Hybrid**: `oportunidad_id` es el modo principal (lee del KM, escribe de vuelta). Texto libre = modo testing (sin KM). `run.py` maneja los dos. | 2026-06-16 |
| F | ¿Qué cruces llena este agente? | ✅ **1, 3 y 4** + anclas bloque 6. El cruce 2 (capacidad/tecnología) = Evidencia Científica (SEB-149). | 2026-06-16 |
| G | ¿Output del agente = markdown + write-back o solo uno? | ✅ **Ambos**: write-back al KM (datos estructurados para el Armador) + markdown de resumen para Sebas. | 2026-06-16 |
| H | ¿COMTRADE incluido? | ✅ **No** — COMTRADE analiza importaciones y sesga al agente hacia sustitución de importaciones. CRIZA busca blue oceans demand-first. Ningún cruce del expediente requiere datos de importaciones como fuente primaria. Eliminado completamente. | 2026-06-16 |
| I | ¿Cómo se agregan conectores locales (INTA, CREA, otros)? | ✅ **Patrón conector**: un archivo `tools/<fuente>.py` + registrar la tool en `market_agent.py`. Contrato uniforme: `search_<fuente>(query) -> list[dict]`. La descripción de la tool es el manual del agente. Ver §3 patrón de extensión. | 2026-06-16 |
| J | ¿Cómo se adopta el patrón anti-sesgo por estructura (`docs/orchestration-layer.md` v0.2, Decisión 6)? | ✅ **Retrofit completo**: pre-flight bloqueante (`corpus_cientifico`, `web_search`) + advertencia (`datos.gob.ar`) vía `knowledge_module/preflight.py`. `buscar_corpus_cientifico` limit=5→100 (fuente propia, ya no muestrea). Tool `web_search` nativo de Anthropic agregado — Cruce 3 antes solo podía fetchear URLs ya conocidas, no descubrir competidores reales. `marco_blue_ocean_CRIZA.md` cargado en runtime (antes: cero referencias). Campos estructurales nuevos en `submit_analysis`: `sustitucion_importacion` (condición 12 del marco, la única "sin excepción" — antes solo vivía como prosa en el prompt) y `valor_cliente` (fuerza las 6 dimensiones del marco). `fuentes_y_cobertura` obligatorio. Motivado por auditoría de sesgos 2026-07-02 (ver `criza/docs/progress/2026-07-02.md`). **63/63 unit tests.** | 2026-07-02 |

---

## 9. Etapa 20 (2026-09-07) — reconexión al modelo de casos.yaml

Este agente había quedado sin tocar desde 2026-07-02, mientras los otros 4 especialistas
(microbiólogo/ingeniero ambiental/agrónomo/biotecnólogo) se construyeron ya conectados a
`casos.yaml` (frente_id). Sebas: "Vamos con el análisis de mercado, te pido que revises bien el
código para que esté bien alineado con lo que tenemos ahora... recuerda que no tenga sesgo
exportador, porque los principales clientes serán cercanos por cuestión de flete, salvo que sea
algo de muy grande valor agregado que se pueda exportar."

| # | Pregunta | Decisión | Fecha |
|---|---|---|---|
| K | ¿Adaptar el agente existente o construir de cero (preocupación explícita de Sebas: "me preocupa que adaptar sea un error, tal vez lo mejor sea crear de cero")? | Adaptar / Construir de cero | **Adaptar.** No aplica el mismo problema que `scientific_agent/specialist_proteins.py` (abandonado, no adaptado) — ese tenía un `SYSTEM_PROMPT` hardcodeado a un caso cancelado, con supuestos tecnológicos INCORRECTOS imposibles de extraer limpio. `market_agent` ya era genérico (nunca mencionaba un caso ni una tecnología) y el gap real (razonar sobre densidad de valor/alcance geográfico) es una consideración AUSENTE, no una equivocada — se agrega, no se arranca nada. Las tools reales (INDEC/MAGyP, corpus CONICET/INTA, `web_search` nativo con su excepción ya decidida), el framework de blue ocean completo (compartido con evidencia/investigación amplia/armador — reinventarlo los desalinearía), y el patrón de conexión SEB-115+chat ya probado 4 veces son hard-won — reconstruirlos de cero solo para "empezar limpio" hubiera sido caro sin ganar nada real. | 2026-09-07 |
| L | ¿Mantener soporte a `oportunidad_id` (modelo viejo, `pipeline_sector.yaml`/`pipeline_dolor.yaml`) o pasar a `frente_id`-only? | Mantener ambos / Solo `frente_id` | **Solo `frente_id`** — mismo criterio que los otros 4 especialistas al conectarse (todos dejaron de soportar `oportunidad_id` por completo). Ningún caso real usa el modelo viejo desde que todo pasó a `casos.yaml`; los 2 flows viejos quedan sin poder invocar a `mercado` si alguna vez se corrieran, deuda intencional documentada (no en uso hoy). | 2026-09-07 |
| M | ¿Cómo evitar el sesgo exportador sin caer en el sesgo opuesto (asumir mercado local por default)? Sebas, corrigiendo el planteo inicial: "no quiero que lo de flete sea un sesgo, la cuestión es desde donde hace el análisis este agente... qué tipo de análisis haga dependerá de los productos que son viables realizar técnicamente." | Regla fija ("priorizar local") / Derivar caso por caso de la densidad de valor del producto | **Derivar caso por caso, nunca una regla fija.** El agente no asume ni local ni exportador de antemano — para cada producto candidato, estima su densidad de valor (valor económico por unidad de volumen/peso) y de ahí deriva el alcance geográfico razonable: bajo valor por volumen (ej. un gel voluminoso) → el flete es una restricción real, radio limitado; alto valor por volumen (ej. un compuesto concentrado) → radio mayor, exportación puede tener sentido. Implementado en `SYSTEM_PROMPT` (sección "ALCANCE GEOGRÁFICO DEL MERCADO") + campos nuevos obligatorios en `submit_analysis.cruce_4.accesibilidad_mercado` (`densidad_valor_producto`, `alcance_geografico_recomendado`) — declarados explícitamente, nunca omitidos ni asumidos en silencio. Para saber QUÉ producto está evaluando, necesita la decisión N. | 2026-09-07 |
| N | ¿Cómo sabe el Agente de Mercado qué producto candidato evaluar, si él no investiga factibilidad técnica? Pedido de Sebas, generalizado durante la conversación: "me parece que estaría bueno que todos puedan ver qué está realizando el resto" (los 5 especialistas, no solo mercado) — con el riesgo explícito que señaló: "cuál es el costo de tokens... a medida que crece el proyecto es mayor la cantidad de documentos que se generan, cuáles ve y cuáles no?" | Inyectar contenido completo de todo / Lista liviana + lectura on-demand | **Lista liviana siempre + lectura on-demand por tool.** `build_input_desde_frente` de los 5 especialistas (los 4 activos retrofit + mercado desde el arranque) incluye la lista COMPLETA de documentos ya producidos en el frente (id/título/agente/fecha — metadata, no contenido) vía `utils/casos.py::obtener_documentos_de_frente` (ya existía, Etapa 19). Tool nueva `ver_informe_especialista(documento_id)`, reusando el helper nuevo `utils/casos.py::obtener_documento_por_id` (extraído de `conductor.py::_tool_ver_documento`, no duplicado 5 veces), trae el contenido completo bajo demanda — el agente decide qué leer según el título, no recibe todo de entrada. Responde directamente la preocupación de escala: la lista crece linealmente pero es barata (solo metadata) sin importar cuántos documentos existan; el costo de tokens real solo se paga por los que el agente decide leer, acotado por instrucción explícita ("no leas todos, solo los relevantes"). | 2026-09-07 |

**Bug real encontrado y arreglado durante la verificación (no relacionado con la reconexión en
sí):** `resumen = next((b.text for b in response.content if hasattr(b, "text")), ...)` y su
equivalente en `enviar_mensaje()` rompían con `TypeError` cuando la respuesta del modelo incluía
un bloque nativo de Anthropic (`server_tool_use`, `web_search_tool_result` — reales al usar
`web_search`) que SÍ tiene el atributo `.text` pero en `None` — `hasattr(b, "text")` da `True`
igual. Corregido con `getattr(b, "text", None)`. El mismo patrón existe en los otros 8 módulos de
agentes del repo — flageado aparte (no corregido acá, para no inflar este cambio) vía
`spawn_task`, pendiente de auditoría en una sesión separada.

**Verificado real de punta a punta contra producción (no solo mocks):** conversación de chat real
contra el Frente técnico de Helios — el agente leyó los 2 informes reales del Biotecnólogo (tool
`ver_informe_especialista`, sin que se le dijera cuáles leer), identificó 2 productos candidatos
distintos (ectoína y un gel SAM biopolimérico), y recomendó alcance geográfico **opuesto para cada
uno con justificación real**: ectoína (€500–2.000/kg, densidad de valor "extremadamente alta") →
exportación/global, citando el mercado europeo real (Evonik/bitop AG); gel SAM (mayormente agua,
densidad de valor "baja-media") → local, radio ~200-300km, citando el costo de flete como
restricción real — sin que ninguna de las dos conclusiones estuviera sesgada de antemano. Citó
fuentes argentinas reales verificables (Patricia Bres/INTA, relevamiento INTA-Secretaría de
Agricultura 2022, serie oficial de potencia instalada de biogás). Regresión completa del backend:
593 passed, 2 skipped (excluyendo el fallo ambiental preexistente de `sentence_transformers`, no
relacionado). `npm run build` de `web/` limpio con `mercado` sumado a `ESPECIALISTAS`.

---

## 10. Estado del gate

**Estado:** ✅ **LISTO** — decisiones A–N cerradas.

*Quinto agente de la biblioteca de especialistas conectado a `casos.yaml`, y el primero adaptado
de un agente ya existente en vez de construido desde cero.*
