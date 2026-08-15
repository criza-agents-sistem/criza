# Design Gate — Agente Investigación Amplia

**Versión:** 2.1  
**Fecha:** 2026-07-01 · última revisión 2026-07-02
**Módulo:** `criza/investigacion_amplia`  
**Capa:** 2 (CRIZA-específico)  
**Estado:** ✅ LISTO — v2.1 implementada y testeada (37/37 unit tests)

> **Regla de uso:**
> Este archivo se crea ANTES de escribir cualquier código del módulo.
> El desarrollo puede arrancar solo cuando el estado sea 🟡 o ✅.
> Cada vez que se diseña un nodo/entidad/contrato nuevo, se actualiza esta tabla primero.

---

## 1. Identidad

| Pregunta | Respuesta |
|---|---|
| ¿Qué es? | Agente que mapea a lo **ancho** el espacio de soluciones/competencia/estado del arte para entradas tipo `sector` o `planta-recurso`. Análogo a "el que hizo a mano el mapa del caso olor del estiércol". |
| ¿Qué problema resuelve? | El Orquestador no puede lanzar el Agente de Mercado (cruce 1) sin saber cuáles son los dolores/candidatos relevantes en un sector o recurso. Investigación Amplia llena ese gap: produce el **mapa de candidatos** y el **cruce 3** sectorial. |
| ¿Quién lo usa? | Orquestador (como pre-paso para entradas tipo sector/planta). Opcionalmente: Sebas directamente (exploración manual de un sector). |
| ¿De qué depende? | KM (`motor_api`), `knowledge_module/tools/search.py` (`get_sector_corpus`, `get_paper_full_text`), `utils/agrovoc.py` (expand_term), `utils/openalex.py`, DB directa para pre-flight CONICET. |
| ¿Qué depende de él? | Orquestador — lee `mapa_candidatos` para decidir a qué candidato enviar al Agente de Mercado. |
| ¿Milestone más próximo? | SEB-204 (pipeline ganadería bovina) — re-run después de que CONICET harvest ≥ 100 fichas. |

---

## 2. Trazabilidad diseño → implementación

### Entidades / nodos

| Entidad | Doc de diseño | En código | Scope | Estado |
|---|---|---|---|---|
| `cruce_3` (Competencia) | `docs/expediente_decision_SPEC.md §Cruce 3` | `investigacion_amplia.py` → tool `submit_investigacion_amplia` | ✅ incluido | ✅ implementado |
| `mapa_candidatos` | Este gate §2 | `investigacion_amplia.py` → campo en submit | ✅ incluido | ✅ implementado |
| `estado_de_desarrollo` (TRL) | Decisión SEB-204 (2026-07-01) | `mapa_candidatos[*].estado_de_desarrollo` | ✅ incluido v2.0 | ✅ implementado |
| `papers_fuente` | Decisión SEB-204 (2026-07-01) | `mapa_candidatos[*].papers_fuente` | ✅ incluido v2.0 | ✅ implementado |
| `_preflight_check` | Decisión SEB-204 — objective-first | `investigacion_amplia.py` — corre antes del loop LLM | ✅ incluido v2.0 | ✅ implementado |
| `INPUT_CONTRACT` / `OUTPUT_CONTRACT` v2.0 | `docs/orchestration-layer.md §6.2` (SEB-115) | `investigacion_amplia.py` nivel módulo | ✅ incluido | ✅ implementado |
| `run(contract_input)` | `docs/orchestration-layer.md §6.2` (SEB-115) | `investigacion_amplia.py` | ✅ incluido | ✅ implementado |
| Tests unitarios v2.0 | — | `tests/test_investigacion_amplia.py` | ✅ incluido | ✅ 25 tests, 25/25 pasan |

### Contratos / interfaces

| Contrato | Entre quiénes | Doc de diseño | En código | Scope | Estado |
|---|---|---|---|---|---|
| `run(contract_input)` SEB-115 | Orquestador → Investigación Amplia | `orchestration-layer.md §6.2` | `investigacion_amplia.py` | ✅ | ✅ implementado |
| `submit_investigacion_amplia` | Agente LLM → Python handler | Este gate §2 (schema) | inline en el agente | ✅ | ✅ implementado |
| `get_sector_corpus` | Agent → KM/INTA | `knowledge_module/tools/search.py` | via import directo | ✅ | ✅ implementado |
| `search_corpus_cientifico` | Agent → KM/corpus_cientifico (CONICET+INTA) | `motor_api.buscar(area="corpus_cientifico", filtro)` | via `_search_corpus_cientifico_fn` | ✅ | ✅ implementado |
| `fetch_paper_full_text` | Agent → KM/INTA | `knowledge_module/tools/search.py` | via import directo | ✅ | ✅ implementado |
| `motor_api.actualizar_props` | Investigación Amplia → KM | `knowledge-module.md` | via `motor_api` import | ✅ | ✅ implementado |

### Schema del tool `submit_investigacion_amplia` (v2.0)

```json
{
  "cruce_3": {
    "qué_existe": "string — panorama competitivo narrativo",
    "registros": {
      "SENASA": ["string"],
      "patentes": ["string"]
    },
    "intensidad": "vacío | débil | fuerte",
    "evidencia": [
      {
        "competidor": "string",
        "descripción": "string",
        "estado": "establecido | asumido | a-confirmar",
        "fuente": "string — URL o referencia"
      }
    ]
  },
  "mapa_candidatos": [
    {
      "candidato": "string — dolor u oportunidad identificada",
      "señal_demanda": "string — por qué hay demanda real",
      "señal_competencia": "string — quién ya lo resuelve (si alguien)",
      "intensidad_competencia": "vacío | débil | fuerte",
      "estado_de_desarrollo": "idea | lab | piloto | comercial | a-confirmar",
      "prioridad": "alta | media | baja",
      "estado": "establecido | asumido | a-confirmar",
      "papers_fuente": ["string — ID o título del paper que evidencia"]
    }
  ],
  "gaps_prioritarios": ["string"],
  "informe_completo": "string — markdown con ## Fuentes y cobertura obligatorio",
  "lecciones_caso": ["string"]
}
```

**Cambios v1.0 → v2.0:**
- `mapa_candidatos` suma `estado_de_desarrollo` (TRL: idea/lab/piloto/comercial) y `papers_fuente`
- `informe_completo` requiere sección `## Fuentes y cobertura` con N papers por fuente
- Tool `search_corpus_inta` reemplazada por `get_sector_corpus` (OR sin límite, no AND con límite=10)
- Tools nuevas: `search_corpus_cientifico` (originalmente `search_corpus_conicet`, renombrada 2026-07-01
  al migrar INTA a `corpus_cientifico` — ver decisión #10), `fetch_paper_full_text`

### KM write — obligatorio

| Tipo de output | Qué contiene | Key en KM | Cómo | Estado |
|---|---|---|---|---|
| **Resultado estructurado + informe narrativo** | `cruce_3` + `mapa_candidatos` (con TRL) + `gaps_prioritarios` + metadata v2.0 + `informe_completo` (markdown íntegro con fuentes y cobertura), todo en un solo dict | `props.investigacion_amplia` | La costura (`orquestador/invocador.py::invocar_agente`) persiste `análisis` tal cual — ya no es este módulo el que escribe (2026-08-15, ver PROPUESTA_DESTINO.md §11). Antes escribía además `props.investigacion_amplia_informe` por separado, duplicando el mismo texto — se eliminó esa clave. | ✅ implementado |
| **Token usage** | Tokens por run (input/output/calls) | `props.token_usage.investigacion_amplia` | `TokenTracker` → `motor_api.actualizar_props` (esta escritura sigue siendo del agente, no de la costura) | ✅ implementado |
| **Aprendizaje** | Lecciones del caso (auto) + de proceso (humano al cierre) | área `lecciones` | `aprendizaje.guardar_leccion_caso` + `cierre_aprendizaje` | 🔵 lecciones_caso retornadas, persistencia pendiente cierre |

---

## 3. Checklist del playbook

### Seguridad Nivel 1

- [x] Credenciales en `.env`, nunca en código
- [x] `.env` en `.gitignore` (heredado del repo)
- [x] `.env.example` existe
- [x] Sin credenciales en historial de git

### Seguridad Nivel 3

¿Aplica? [x] No — el agente consulta fuentes públicas y escribe en el KM propio del tenant.

### Estructura de archivos

- [x] `__init__.py` existe
- [x] `investigacion_amplia.py` existe (v2.0)
- [x] `tests/test_investigacion_amplia.py` existe (25 tests, 25/25 pasan)
- [x] `.env.example` existe

### Testing

- [x] Tests para `INPUT_CONTRACT` / `OUTPUT_CONTRACT` — version, campos, herramientas v2.0
- [x] Tests para `_derive_confidence(resultado)` — todos los casos (alto/medio/bajo)
- [x] Tests para `run(contract_input)` — formato output, próximo_agente, ordenamiento
- [x] Tests para `_preflight_check` — INTA bloqueante, CONICET bloqueante, OpenAlex advertencia, todo OK
- [x] Tests para `estado_de_desarrollo` — pasa en recomendaciones sin modificarse
- [x] Markers `unit` / `integration` configurados

### Observabilidad

- [x] `TokenTracker` persiste tokens en KM por run
- [x] Verbose mode: muestra pre-flight, calls, herramientas, candidatos
- [x] Pre-flight check loguea advertencias y bloqueantes

---

## 4. Scope explícito por versión

| Entidad / feature | Versión objetivo | Razón del postergue | Bloqueante |
|---|---|---|---|
| Búsqueda de patentes INPI/espacenet | v2.1 | API compleja; v2.0 cubre con `fetch_page_text` para señales iniciales | Acceso a API INPI |
| Registros SENASA (API formal) | v2.1 | SENASA no tiene API pública documentada | Gestión de acceso |
| Modo `planta-recurso` profundo | v2.1 | v2.0 cubre `sector` + señal ligera de planta; la semántica planta requiere más spec | Decisión de schema extendido |
| Aprendizaje transversal entre sectores | v3.0 | Requiere el Orquestador con memoria cross-instance para comparar sectores | Orquestador v1 |
| Persistencia lecciones_caso automática | v2.1 | El retorno existe pero no se llama `aprendizaje.guardar_leccion_caso` aún | Integración aprendizaje |

---

## 5. Decisiones

| # | Pregunta | Decisión tomada | Fecha |
|---|---|---|---|
| 1 | ¿El agente recibe `oportunidad_id` o texto libre? | **Ambos**: `caso` = texto libre; `conocimiento.oportunidad_id` = opcional para linkear al KM | 2026-06-27 |
| 2 | ¿`próximo_agente` sugiere Agente de Mercado? | **Sí**: retorna `"mercado"` si ≥1 candidato alta-prioridad; None si todos media/baja | 2026-06-27 |
| 3 | ¿Cuántos candidatos profundiza? | **Sin límite fijo** — el agente explora hasta tener señal suficiente | 2026-06-27 |
| 4 | ¿Cómo deriva `nivel_confianza`? | **Combinado**: `alto` si `cruce_3.intensidad` ≠ "a-confirmar" Y ≥ 3 establecidos; `medio` si parcial; `bajo` en otro caso | 2026-06-27 |
| 5 | ¿Las tools reutilizan las del agente de mercado o son propias? | **Importa directamente de knowledge_module** sin capa tools/ propia | 2026-06-27 |
| 6 | ¿FTS AND o OR para buscar el corpus INTA? | **OR sin límite** via `get_sector_corpus` — AND + limit=10 era el bug raíz de v1.0 (2 docs vs 341) | 2026-07-01 |
| 7 | ¿Pre-flight check es bloqueante o advertencia por fuente? | **INTA y CONICET = bloqueante** (fuentes que controlamos); **OpenAlex = advertencia** (externo, puede estar caído) | 2026-07-01 |
| 8 | ¿Cuántas fichas CONICET para desbloquear? | **≥ 100** — umbral conservador para corpus biotech/agro/vet con 28 sets cosechados | 2026-07-01 |
| 9 | ¿TRL se determina con abstracto o texto completo? | **Texto completo obligatorio** via `fetch_paper_full_text` — TRL requiere Métodos + Resultados | 2026-07-01 |
| 10 | ¿INTA queda solo en `documento` (FTS) o migra a `corpus_cientifico` (semántico)? | **Migra** — script `criza/ingest/migrate_inta_to_corpus.py` copia 1,643 registros de `documento` a `ficha/corpus_cientifico` con embeddings BGE-m3, sin tocar `documento` (queda como fuente exhaustiva para `get_sector_corpus`). Gap detectado: INTA tenía FTS pero no búsqueda semántica — violaba "no cosas a medias" | 2026-07-01 |
| 11 | ¿La búsqueda semántica en `corpus_cientifico` puede acotarse por organismo (INTA/CONICET/futuro CREA)? | **Sí** — `motor_api.buscar()` (Capa 1) suma parámetro opcional `filtro: dict` genérico por props (ej. `{"repositorio": ["INTA"]}`). Gap no contemplado en `CONICET_CONNECTOR_GATE.md` §5 original; se cierra acá. Tool renombrado `search_corpus_conicet` → `search_corpus_cientifico`, acepta `repositorio` opcional. PASO 3 del workflow ahora excluye INTA (ya cubierto exhaustivo en paso 2) para no releer ni gastar de más | 2026-07-01 |
| 12 | ¿El TRL puede quedar determinado solo con el abstract si el agente "lo considera suficiente"? | **No, nunca.** Gap encontrado en auditoría de sesgos 2026-07-02: PASO 5 pedía leer texto completo de "los 2-3 papers más relevantes" — dejaba a discreción del agente cuánto leer, exactamente el patrón de sesgo por muestreo ya corregido en la búsqueda del corpus. Cerrado con: (a) TODOS los candidatos de prioridad alta requieren `fetch_paper_full_text` antes de asignar `estado_de_desarrollo`, no una selección discrecional; (b) campo `cobertura_texto_completo` obligatorio en `submit_investigacion_amplia` (`candidatos_alta_prioridad` / `con_texto_completo_leido`) — declara la cobertura real, no la asume; (c) `_derive_confidence` capa `nivel_confianza` a `medio` como máximo si hay candidatos alta prioridad con cero texto completo leído — estructural, no depende de que el modelo lo respete en prosa. `fetch_paper_full_text` ahora también resuelve IDs de `search_corpus_cientifico` (antes solo funcionaba con IDs de `get_sector_corpus`/INTA) | 2026-07-02 |
| 13 | ¿`submit_investigacion_amplia` tiene `fuentes_y_cobertura` como campo estructurado (orchestration-layer.md Decisión 6), igual que market_agent/evidence_generalista/armador? | Sí / No | **No lo tenía — gap real, encontrado por el agente auditor** (`knowledge_module/auditor/`, primera corrida, 2026-07-02) contra el propio agente que originó Decisión 6. Tenía `cobertura_texto_completo` (mide lectura de texto completo de candidatos) pero la disponibilidad de fuente en sí seguía solo en prosa dentro de `informe_completo` ("## Fuentes y cobertura"), no estructurada — exactamente el anti-patrón que Decisión 6 corrige. Cerrado: campo `fuentes_y_cobertura` agregado a `submit_investigacion_amplia`, mismo schema que los otros 3 agentes, ahora `required`. Contrato v2.0 → v2.1. | 2026-07-02 |
| 14 | `_preflight_check` propio (tupla `(ok, bloqueantes, advertencias)`) seguía inline pese a que generalizarlo fue el origen de `knowledge_module/preflight.py` — market_agent/evidence_generalista/armador ya lo usaban, este agente no. ¿Se migra? | Sí / No | **Sí, migrado.** `_preflight_check` reemplazado por 3 `FuenteCheck` (`_check_inta_corpus_sector` — toma `terminos_sector` vía closure, `_check_corpus_cientifico`, `_check_openalex`) orquestados con `run_preflight()` genérico, mismo patrón que los otros 3 agentes. Comportamiento idéntico (mismos umbrales, mismos mensajes), solo cambia el mecanismo. Tests migrados de `asyncio.get_event_loop().run_until_complete()` a `@pytest.mark.asyncio`, reordenados al final del archivo (después de los tests legacy que sí necesitan `get_event_loop()`) para evitar el conflicto de event loop entre pytest-asyncio y el estilo legacy. | 2026-07-02 |

---

## 6. Contrato estándar v2.0 (SEB-115)

### INPUT_CONTRACT

```python
INPUT_CONTRACT = {
    "agent": "investigacion_amplia",
    "version": "2.0",
    "fields": {
        "caso": "Sector o planta/recurso a mapear (texto libre)",
        "tarea": "Análisis exhaustivo del corpus científico del sector para identificar blue oceans.",
        "contexto": "Opcional — outputs de agentes anteriores",
        "conocimiento": "Opcional — {'oportunidad_id': str} para linkear al KM",
        "herramientas": [
            "expand_agrovoc",
            "get_sector_corpus",
            "search_corpus_cientifico",
            "fetch_paper_full_text",
            "search_literature",
            "fetch_page_text",
            "submit_investigacion_amplia",
        ],
    },
}
```

### OUTPUT_CONTRACT

```python
OUTPUT_CONTRACT = {
    "agent": "investigacion_amplia",
    "version": "2.0",
    "fields": {
        "análisis": "{'informe': str, 'resultado': {'cruce_3': dict, 'mapa_candidatos': list, 'gaps_prioritarios': list}}",
        "nivel_confianza": "'alto' | 'medio' | 'bajo'",
        "recomendaciones": "mapa_candidatos ordenados por prioridad (alta → baja)",
        "próximo_agente": "'mercado' si hay ≥1 candidato alta-prioridad, else None",
        "nuevo_conocimiento": "lecciones_caso",
    },
}
```

### Derivación `nivel_confianza`

```python
def _derive_confidence(resultado: dict) -> str:
    cruce_3 = resultado.get("cruce_3") or {}
    intensidad = cruce_3.get("intensidad", "a-confirmar")
    mapa = resultado.get("mapa_candidatos") or []
    establecidos = [c for c in mapa if c.get("estado") == "establecido"]
    if intensidad != "a-confirmar" and len(establecidos) >= 3:
        return "alto"
    if intensidad in ("vacío", "débil", "fuerte") or len(establecidos) >= 1:
        return "medio"
    return "bajo"
```

---

## 7. Estado del gate

| Estado | Condición |
|---|---|
| 🔴 BLOQUEADO | Hay decisiones abiertas en §5 o GAPs sin resolver en §2 |
| 🟡 LISTO CON DEUDA | Decisiones cerradas; hay items 🔵 documentados como deuda intencional |
| ✅ LISTO | Todo resuelto — desarrollo puede arrancar |

**Estado actual:** ✅ LISTO — v2.1 implementada y testeada (34/34 unit tests)

**Deuda documentada (scope v2.2+):**
- 🔵 Persistencia automática de lecciones_caso via `aprendizaje.guardar_leccion_caso`
- 🔵 Patentes INPI/espacenet — API formal
- 🔵 Registros SENASA — API formal
- 🔵 Modo `planta-recurso` profundo

**Cerrado en v2.1 (2026-07-02):**
- ✅ CONICET harvest ≥ 100 fichas — 625 fichas al 2026-07-02
- ✅ Texto completo de CONICET disponible vía `knowledge_module/ingesta/download_corpus_pdfs.py`
  (backfill bulk, no bajo demanda — ver `orchestration-layer.md` Decisión 6 y decisión #12 de esta tabla)
- ✅ `fetch_paper_full_text` unificado — funciona con IDs de INTA (`documento`) y CONICET (`ficha`)
- ✅ `cobertura_texto_completo` obligatorio — cierra el hueco donde TRL podía quedar
  determinado solo con el abstract sin que nadie se enterara

---

*Actualizar este archivo antes de cada sesión de desarrollo que agregue entidades nuevas.*
*Si surge una entidad nueva en el diseño, agregarla a §2 ANTES de codearla.*
