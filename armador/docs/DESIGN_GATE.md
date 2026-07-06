# Design Gate — Armador del Expediente

**Versión:** 1.1  
**Fecha:** 2026-06-16 · última revisión 2026-07-02
**Módulo:** `armador/`  
**Capa:** 2 (CRIZA-specific)  
**Issue:** SEB-145  
**Estado:** ✅ LISTO — decisiones A–G cerradas; desarrollo puede arrancar

> **Regla de uso:**
> Este archivo se crea ANTES de escribir cualquier código del módulo.
> El desarrollo puede arrancar solo cuando el estado sea 🟡 o ✅.
> Cada vez que se diseña un nodo/entidad/contrato nuevo, se actualiza esta tabla primero.

---

## 1. Identidad

| Pregunta | Respuesta |
|---|---|
| ¿Qué es? | Agente ensamblador del expediente de decisión. Lee lo que los agentes investigadores ya escribieron en el KM y arma el documento final de 6 bloques. NO investiga, NO elige, NO inventa. |
| ¿Qué problema resuelve? | Los agentes investigadores (Mercado, Evidencia Científica, etc.) escriben cruces aislados en el KM. El Armador los integra en el expediente unificado que el humano lee para decidir. |
| ¿Quién lo usa? | Sebas (o el Orquestador futuro). Recibe un `oportunidad_id` y devuelve el expediente completo + lo escribe en el KM. |
| ¿De qué depende? | KM Motor (leer props de la oportunidad) + Market Agent v1 (cruces 1/3/4 en `props.mercado`) + `aprendizaje.py` (loop de aprendizaje SEB-156). |
| ¿Qué depende de él? | El humano (expediente de decisión). Futuro: Orquestador → Armador como paso final del pipeline. |
| ¿Milestone más próximo? | M1 — pipeline completo: agentes investigadores → Armador → expediente → Sebas decide. |

---

## 2. Trazabilidad diseño → implementación

### Entidades / componentes

| Entidad | Doc de diseño | En código (archivo) | Scope v1 | Estado |
|---|---|---|---|---|
| **Armador — agente principal** | SEB-145 + `expediente_decision_SPEC.md` | `armador/armador.py` | ✅ incluido | 🔜 por construir |
| **Tool `submit_expediente`** | §5.B de este gate — output estructurado obligatorio | `armador/armador.py` (TOOLS) | ✅ incluido | 🔜 por construir |
| **Input builder** | §5.C — construye el mensaje inicial desde props del KM | `armador/armador.py` (`build_input()`) | ✅ incluido | 🔜 por construir |
| **KM read** | Motor API (`motor_api.obtener`) | `armador/armador.py` | ✅ incluido | 🔜 por construir |
| **KM write-back** | Motor API (`motor_api.actualizar_props`) — key "expediente" | `armador/run.py` | ✅ incluido | 🔜 por construir |
| **Loop de aprendizaje** | `aprendizaje.py` — contrato SEB-156 | `armador/armador.py` + `run.py` | ✅ incluido | 🔜 por construir |
| **Runner interactivo** | Convención CRIZA (`agents.md`) | `armador/run.py` | ✅ incluido | 🔜 por construir |
| **ROADMAP.md** | Convención CRIZA | `armador/ROADMAP.md` | ✅ incluido | 🔜 por crear |
| **Tests unitarios** | Playbook CRIZA | `armador/tests/test_armador.py` | ✅ incluido | 🔜 por construir |
| **Cruce 2 (Capacidad/Tecnología)** | `expediente_decision_SPEC.md` Bloque 2 | completado por Evidence Agent (SEB-149, no construido) | 🔵 v1: placeholder explícito `a-confirmar` | 🔵 postergado — sin bloquear |
| **Herramienta de búsqueda de vecinos** | — | — | 🔵 v2 | 🔵 postergado — no aporta a v1 |

### Contratos / interfaces

| Contrato | Entre quiénes | Doc de diseño | En código | Scope v1 | Estado |
|---|---|---|---|---|---|
| **KM props read** | KM → Armador | Motor API `obtener(oportunidad_id)` | `armador.py` / `run.py` | ✅ incluido | 🔜 construir |
| **KM props write-back** | Armador → KM | Motor API `actualizar_props(id, {"expediente": ...})` | `run.py` | ✅ incluido | 🔜 construir |
| **`submit_expediente` schema** | Armador → output estructurado | §5.B de este gate | `armador.py` TOOLS | ✅ incluido | 🔜 construir |
| **Contrato aprendizaje** | Armador ↔ `aprendizaje.py` | SEB-156 `knowledge_module/aprendizaje.py` | `armador.py` + `run.py` | ✅ incluido | 🔜 construir |

---

## 3. Checklist del playbook

### Seguridad Nivel 1

- [ ] Credenciales en `.env`, nunca en código
- [ ] `.env` en `.gitignore` (heredado del repo `criza/`)
- [ ] `.env.example` completo (ANTHROPIC_API_KEY + ARMADOR_MODEL)
- [ ] Sin credenciales en historial de git

### Seguridad Nivel 3

¿Aplica? [x] Sí — procesa datos estratégicos de oportunidades de inversión de CRIZA.

| Requerimiento | Decisión |
|---|---|
| `tenant_id` | ✅ heredado del KM v0.2 — todas las escrituras llevan `tenant='criza'` |
| RLS en Neon | 🔵 antes del segundo tenant (DPN) — igual que el resto |
| Gate humano | ✅ El Armador NO decide ni recomienda; el output es insumo humano (§1 del CLAUDE.md) |

### Estructura de archivos

- [ ] `docs/DESIGN_GATE.md` ← este archivo ✅
- [ ] `ROADMAP.md`
- [ ] `.env.example`
- [ ] `tests/__init__.py` + `tests/conftest.py`

### Testing

- [ ] Tests de estructura: `submit_expediente` tiene los campos requeridos
- [ ] Tests de input builder: con y sin cruce 2, con y sin bloque_6_anclas del market agent
- [ ] Tests de integración: corrida real con oportunidad del KM (marker `integration`)

### Observabilidad

¿Va a producción? Sí (Sebas lo corre sobre oportunidades reales).

- [ ] Verbose mode: logging de la call a Claude (tokens, modelo)
- [ ] Logging del resultado de write-back al KM

---

## 4. Scope explícito por versión

| Entidad / feature | Versión objetivo | Razón del postergue | Bloqueante para avanzar |
|---|---|---|---|
| **Cruce 2 — Capacidad/Tecnología** (completado) | v2 | SEB-149 (Evidence Agent) no construido | Requiere SEB-149 done |
| **Búsqueda de vecinos oportunidad** | v2 | No aporta al expediente v1; el Armador sintetiza lo existente | — |
| **Trigger automático desde Orquestador** | v3 | Requiere Orquestador SEB-152 | SEB-152 done |
| **Validación de integridad del expediente** | v2 | Requiere N casos reales para definir los controles | Mínimo 3 corridas reales |

---

## 5. Decisiones de diseño

| # | Pregunta | Opciones | Decisión tomada | Fecha |
|---|---|---|---|---|
| A | ¿Directorio nuevo o dentro de `convergent_agent/`? | A) `armador/` nuevo / B) Reescribir `convergent_agent/` | **A — `armador/` nuevo.** El convergente es investigador N→1; el Armador es sintetizador. Son conceptos distintos. El convergente queda operativo hasta que el Orquestador lo haga obsoleto. | 2026-06-16 |
| B | ¿El Armador tiene tools de investigación? | A) Sí (buscar en corpus, web, etc.) / B) No — solo `submit_expediente` | **B — solo `submit_expediente`.** El Armador NO investiga. Los datos vienen de los agentes investigadores vía KM. Una tool de output estructurado es suficiente. | 2026-06-16 |
| C | ¿Qué hace con cruce 2 ausente (sin Evidence Agent)? | A) Deja el bloque vacío / B) Inventa / C) Bloque explícito `a-confirmar` con referencia a SEB-149 | **C — bloque `a-confirmar` explícito.** Nunca vacío, nunca inventado. Declara: "Fuente pendiente: Agente de Evidencia Científica (SEB-149, por construir)". Veracidad por dato. | 2026-06-16 |
| D | ¿Bajo qué key escribe en el KM? | A) "expediente" / B) Reemplaza props.mercado / C) Nuevo campo "expediente_v1" | **A — "expediente"** en `actualizar_props`. No toca "mercado" (escrito por market agent). Cada agente escribe su key propia. | 2026-06-16 |
| E | ¿Es async o sync? | A) async / B) sync | **A — async.** Mismo patrón que market_agent. Motor API es async-first. | 2026-06-16 |
| F | ¿Cómo evita la colisión de `sys.modules['tools']`? | A) `_load_fn` (como convergente) / B) Importar tools ANTES de motor (como market_agent) / C) Sin tools propias → sin conflicto | **C — sin tools/** propias. El Armador no tiene un directorio `tools/` — `submit_expediente` se define inline en `armador.py`. Sin colisión. | 2026-06-16 |
| G | ¿Cómo se adopta el patrón anti-sesgo por estructura (`docs/orchestration-layer.md` v0.2, Decisión 6) si el Armador no tiene fuentes propias que verificar? | ✅ **Validación de cobertura aguas arriba** en vez de pre-flight de fuentes: `_validar_cobertura_upstream(props)` — sin `mercado` → bloqueante (no hay nada que ensamblar); sin `evidencia` o con `cobertura_declarada` parcial → advertencia, se ensambla igual y se marca. Nuevo campo `bloque_3.cobertura_global` (alto/medio/bajo) — **calculado por `_derive_cobertura_global`, no autoreportado por el modelo** (veracidad por dato: establecido > asumido). Motivado por auditoría de sesgos 2026-07-02. | 2026-07-02 |

---

### §5.B — Schema `submit_expediente`

El agente DEBE llamar esta tool como último paso. El loop la captura y usa los datos para el KM write-back.

```python
{
    "bloque_1": {
        "tesis": str,               # 1-2 frases: qué, para quién, por qué ahora
        "puerta_de_entrada": str,   # sector | dolor | tecnología | planta-recurso | necesidad-empresario
        "disparador": str,          # el input concreto que generó esta oportunidad
        "oportunidad_nombre": str
    },
    "bloque_2": {
        "cruce_1": dict,            # copiado de props.mercado.cruce_1 (establecido/asumido/a-confirmar por campo)
        "cruce_2": dict,            # de props.evidencia si existe; si no → a-confirmar completo (decisión C)
        "cruce_3": dict,            # copiado de props.mercado.cruce_3
        "cruce_4": dict             # copiado de props.mercado.cruce_4
    },
    "bloque_3": {
        "establecidos": list[str],  # lista de los datos con estado=establecido
        "asumidos": list[dict],     # [{"dato": str, "peso": "alto|medio|bajo"}]
        "a_confirmar": list[dict],  # [{"dato": str, "donde_confirmar": str, "impacto_en_decision": "alto|medio|bajo"}]
        "indice_confianza": str,    # "alto" | "medio" | "bajo" — síntesis cualitativa por dato
        "cobertura_global": str     # "alto" | "medio" | "bajo" — calculado por el Armador, no por el modelo (Decisión G)
    },
    "bloque_4": {
        "nivel": str,               # "hipotesis_de_screening" | "parcialmente_validado" | "listo_para_decision"
        "justificacion": str
    },
    "bloque_5": {
        "gaps": list[dict]          # [{"descripcion": str, "como_confirmar": str, "quien_o_fuente": str, "prioridad": "alta|media|baja"}]
    },
    "bloque_6": {
        "inversion": dict,          # componentes, comparables o a-estimar
        "tiempo_a_mercado": dict,   # anclado en comparables; si no → a-juicio-humano. SIN timeline del modelo
        "capacidades": dict,        # requeridas vs disponibles (humano/CONICET/socios)
        "regulatorio": dict         # encuadre + anclas históricas; plazo = incógnita conocida
    },
    "trazabilidad": {
        "agentes_que_contribuyeron": list[str],
        "fuentes_usadas": list[str],
        "fecha": str
    },
    "resumen_markdown": str,        # render del expediente completo para lectura humana
    "lecciones_caso": list[str]     # para guardar_leccion_caso() al cierre
}
```

### §5.C — Input builder

El runner lee del KM y construye el mensaje inicial para el agente:

```
Oportunidad: {nombre}
ID: {oportunidad_id}
Descripción: {descripcion}

## Datos del Agente de Mercado (cruces 1 / 3 / 4):
{json.dumps(props.mercado, indent=2)}

## Datos del Agente de Evidencia Científica (cruce 2):
{json.dumps(props.evidencia, indent=2) si existe, else "[NO DISPONIBLE — SEB-149 pendiente]"}

## Contexto adicional de la oportunidad:
{json.dumps(props_restantes, indent=2)}
```

### §5.D — sys.path (sin colisión)

El Armador no tiene `tools/` propio. `submit_expediente` se define inline. El único import necesario es `motor_api` y `aprendizaje`, ambos de `knowledge_module/`. No hay colisión de paquetes.

---

## 6. Estado del gate

**Estado actual:** ✅ LISTO — decisiones A–G cerradas, desarrollo puede arrancar.

**Deuda intencional documentada (no bloquea):**
- 🔵 Cruce 2 completo → v2 (requiere SEB-149 Evidence Agent)
- 🔵 Búsqueda de vecinos → v2
- 🔵 Trigger automático desde Orquestador → v3 (SEB-152)

---

*Actualizar este archivo antes de cada sesión que agregue entidades nuevas.*
*Si surge una entidad nueva en el diseño, agregarla a §2 ANTES de codearla.*
