# Design Gate — Evidence Generalista

**Versión:** 1.2
**Fecha:** 2026-06-16 · última revisión 2026-07-02
**Módulo:** `criza/evidence_generalista/`
**Capa:** 2 (instancia CRIZA)
**Estado:** ✅ LISTO — 47/47 tests unitarios pasando

---

## 1. Identidad

| Pregunta | Respuesta |
|---|---|
| ¿Qué es? | Agente LLM que evalúa la factibilidad técnica de crear una solución para un dolor dado. Technology-agnostic. Llena el cruce 2 del expediente a nivel de screening. |
| ¿Qué problema resuelve? | El cruce 2 siempre es `a-confirmar` porque no hay agente que lo llene. Sin él el expediente es estructuralmente incompleto. |
| ¿Quién lo usa? | El Orquestador (lo llama en el pipeline) |
| ¿De qué depende? | OpenAlex (literatura científica), `motor_api` (KM), `aprendizaje` |
| ¿Qué depende de él? | Orquestador (lee `props.evidencia.especialista_recomendado` para decidir routing), Armador (lee `props.evidencia` para cruce 2) |
| ¿Milestone? | M1 — Base sólida |

---

## 2. Trazabilidad diseño → implementación

### Entidades

| Entidad | Descripción | Scope v1 | Estado |
|---|---|---|---|
| `search_literature` | OpenAlex via `criza/utils/openalex.py` (copia canónica compartida). | ✅ incluido | ✅ construido |
| `buscar_corpus_cientifico` | Búsqueda semántica en corpus_cientifico — CONICET (625 fichas) + INTA vía el motor nuevo, `criza/utils/corpus.py` (compartido con market_agent). | ✅ incluido (v1.2) | ✅ construido |
| `submit_evidencia` | Output estructurado obligatorio. Captura cruce_2 + especialista_recomendado + informe completo. | ✅ incluido | ✅ construido |
| `cruce_2` | Schema estructurado con 6 campos, todos required. | ✅ incluido | ✅ construido |
| `especialista_recomendado` | Flag + descripción libre. El Orquestador matchea con su registry. | ✅ incluido | ✅ construido |

### Schema del cruce_2

```json
{
  "solucion_propuesta": {
    "valor": "descripción de la solución técnica identificada (puede no existir aún)",
    "estado": "establecido|asumido|a-confirmar",
    "fuente": "..."
  },
  "estado_cientifico": {
    "valor": "maduro|emergente|experimental|conceptual",
    "justificacion": "...",
    "estado": "establecido|asumido|a-confirmar",
    "fuente": "..."
  },
  "factibilidad_produccion": {
    "valor": "propia|socio|hibrida|a-confirmar",
    "que_requiere": "descripción de capacidades necesarias — SIN nombrar tecnologías específicas",
    "estado": "establecido|asumido|a-confirmar"
  },
  "ventaja_vs_incumbente": {
    "valor": "...",
    "estado": "establecido|asumido|a-confirmar",
    "fuente": "..."
  },
  "brechas_tecnicas": [
    {
      "brecha": "...",
      "impacto_en_decision": "alto|medio|bajo",
      "donde_confirmar": "..."
    }
  ],
  "evidencia": {
    "fuentes": ["..."],
    "estado": "establecido|asumido|a-confirmar"
  }
}
```

### Schema del especialista_recomendado (en submit_evidencia)

```json
{
  "si_no": true,
  "descripcion": "texto libre describiendo qué análisis adicional aportaría valor — el Orquestador matchea con su registry de especialistas disponibles",
  "razon": "por qué se recomienda — qué pregunta dejaría sin responder el generalista solo"
}
```

**Principio 7b aplicado:** el generalista NO nombra la tecnología ni el tipo de especialista. Describe QUÉ análisis haría falta. El Orquestador decide si hay un especialista disponible para eso.

### Contrato con el Orquestador

```python
async def run_agent(oportunidad_id: str, verbose: bool = False) -> tuple[str, dict, list[str]]:
    """
    Retorna (informe_markdown, evidencia_dict, lecciones_caso).
    Side effect: escribe props.evidencia en el KM.
    """
```

### KM write — Evidence Generalista

| Tipo de output | Qué contiene | Key en KM | Cómo | Estado |
|---|---|---|---|---|
| **Resultado estructurado** | cruce_2 + especialista_recomendado + fuentes_y_cobertura | `props.evidencia` | `motor_api.actualizar_props` | ✅ construido |
| **Informe narrativo completo** | El markdown íntegro del análisis de evidencia | `props.evidencia.informe_completo` | `motor_api.actualizar_props` | ✅ construido (dentro de evidencia_dict) |
| **Token usage** | Tokens consumidos por el agente | `props.token_usage.evidencia` | `motor_api.actualizar_props` | ✅ construido (vía TokenTracker) |
| **Aprendizaje** | Lecciones del caso | área `lecciones` | `aprendizaje.guardar_leccion_caso` + `cierre_aprendizaje` | 🔵 pendiente v1.1 |

---

## 3. Checklist del playbook

### Seguridad Nivel 1

- [ ] Credenciales en `.env`, nunca en código
- [ ] `.env` en `.gitignore`
- [ ] `.env.example` completo
- [ ] Sin credenciales en historial de git

### Estructura de archivos

- [ ] `evidence_generalista.py` — SYSTEM_PROMPT + TOOLS + run_agent()
- [ ] `run.py` — runner interactivo
- [ ] `tools/openalex.py` — reusar de divergente (o symlink/import)
- [ ] `docs/DESIGN_GATE.md` — este archivo
- [ ] `.env.example`
- [ ] `tests/`

### Testing

- [ ] Test: TOOLS tiene exactamente 2 tools (`search_literature` + `submit_evidencia`)
- [ ] Test: submit_evidencia tiene cruce_2 y especialista_recomendado como campos required
- [ ] Test: SYSTEM_PROMPT no menciona ninguna tecnología específica (principio 7b)
- [ ] Test: SYSTEM_PROMPT menciona que la solución puede no existir aún
- [ ] Test: build_input inyecta correctamente dolor + market agent context
- [ ] Test: run_agent mock captura submit_evidencia
- [ ] Test: run_agent escribe a props.evidencia en KM

---

## 4. Scope explícito por versión

| Feature | Versión | Razón |
|---|---|---|
| Tools de análisis específico por dominio | v2+ (especialistas) | Principio 7b — no anclar tecnología en el generalista |
| Acceso a corpus CONICET local | v1.2 (entregado 2026-07-02) | Quedó documentado como deuda desde 2026-06-16 sin cerrarse — ver decisión F. Cerrado vía `buscar_corpus_cientifico`. |
| Lectura del output del market agent como contexto | v1 | Incluido — el generalista se beneficia de saber el dolor ya caracterizado |

---

## 5. Decisiones requeridas antes de arrancar

| # | Pregunta | Opciones | Decisión | Fecha |
|---|---|---|---|---|
| A | ¿El generalista lee `props.mercado` del market agent como contexto adicional? | Sí / No | **Sí** — el dolor ya caracterizado por el market agent mejora la búsqueda de literatura técnica. Lo lee de `props.mercado.cruce_1` (dolor y quién lo sufre). | 2026-06-16 |
| B | ¿Tool set: solo `search_literature` o también `buscar_corpus_cientifico`? | Solo OpenAlex / OpenAlex + corpus CONICET local | **Solo OpenAlex** en v1. El corpus CONICET (SEB-150) se agrega en v1.1. | 2026-06-16 |
| C | ¿`submit_evidencia` incluye `especialista_recomendado` como campo required? | Required / Opcional | **Required** — el Orquestador siempre necesita saber si hay routing al especialista. Si no se recomienda, `si_no: false`. | 2026-06-16 |
| D | ¿El generalista menciona tecnologías específicas en su SYSTEM_PROMPT (principio 7b)? | Mencionar / No mencionar | **No mencionar** — ningún ejemplo de tecnología en el SYSTEM_PROMPT. La descripción en `especialista_recomendado` también es libre, sin enum de tipos. | 2026-06-16 |
| E | ¿Cómo se adopta el patrón anti-sesgo por estructura (`docs/orchestration-layer.md` v0.2, Decisión 6)? | ✅ **Retrofit completo**: pre-flight bloqueante (INTA corpus) + advertencia (OpenAlex) vía `knowledge_module/preflight.py`. `search_corpus_inta` dejó de usar `search_fuentes_externas` (FTS con `LIMIT` chico) y ahora delega en `get_sector_corpus` (OR exhaustivo, misma fuente que usa investigacion_amplia) — `limit` default 10→1000, ya no muestrea por default. `marco_blue_ocean_CRIZA.md` cargado en runtime (antes: cero referencias). `fuentes_y_cobertura` obligatorio en `submit_evidencia`. Motivado por auditoría de sesgos 2026-07-02. | 2026-07-02 |
| F | La decisión B (2026-06-16) difirió el acceso a CONICET a "v1.1" y quedó sin cerrarse — el agente corrió semanas sin ningún tool que tocara corpus_cientifico/CONICET (625 fichas), pese a estar documentado como deuda. ¿Se cierra ahora? | Cerrar ya / seguir diferido | **Cerrar ya** — se agregó `buscar_corpus_cientifico` (mismo tool que usa market_agent, movido a `criza/utils/corpus.py` para compartirlo entre agentes), declarado bloqueante en el pre-flight (`_check_corpus_cientifico`) y en `fuentes_y_cobertura`. Motivado por: la deuda documentada nunca se revisaba de oficio — solo salía a la luz cuando Sebas preguntaba directamente si el pipeline estaba realmente conectado. Ver `criza/docs/progress/2026-07-02.md`. | 2026-07-02 |

---

## 6. Estado del gate

**Estado actual:** ✅ LISTO

Decisiones A–F cerradas. El agente ahora tiene acceso real a las tres fuentes propias de
literatura: OpenAlex (global), corpus_cientifico (CONICET+INTA vía el motor nuevo, semántico) y
el corpus INTA legacy (exhaustivo vía FTS).

**Deuda intencional documentada:**
- Tools de dominio → van a los especialistas, no al generalista
- Persistencia automática de lecciones_caso → pendiente integración con `aprendizaje.guardar_leccion_caso`
