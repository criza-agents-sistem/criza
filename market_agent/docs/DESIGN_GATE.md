# Design Gate — Agente de Mercado v1 (SEB-148)

**Versión:** 1.2
**Fecha:** 2026-06-16 · última revisión 2026-07-02
**Módulo:** `criza/market_agent/` (Capa 2 — instancia CRIZA)
**Estado:** ✅ LISTO — decisiones A–J cerradas (2026-07-02)

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

## 9. Estado del gate

**Estado:** ✅ **LISTO** — decisiones A–J cerradas. Desarrollo puede arrancar.

*Siguiente: implementar. Patrón de referencia para todos los agentes investigadores (SEB-149, SEB-146).*
