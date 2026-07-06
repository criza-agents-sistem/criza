# Diseño — Motor Dirigido por Objetivo (Orquestador v2)

**Fecha:** 2026-06-27  
**Issue:** SEB-152  
**Estado:** 🟡 Diseño completo — construcción por etapas

> Este documento es el diseño completo del Motor Dirigido por Objetivo. El diseño está cerrado.
> La construcción puede hacerse por etapas. Nunca construir sin leer este documento primero.

---

## 1. Contexto y motivación

El Orquestador v1.0 (existente en `orquestador.py`) es un "LLM puro" que toma decisiones de routing
dinámicamente. Esto funciona pero tiene un problema estructural: **el flujo está hardcodeado** en el
SYSTEM_PROMPT. Para correr el pipeline de CRIZA-dolor, el modelo sabe los pasos porque los tiene en el
prompt. No puede correr otro flujo (DPN, EIA-1, un flujo de ventas) sin un nuevo agente.

La decisión D10 del rethink dice:

> El Orquestador es un **MOTOR DIRIGIDO POR OBJETIVO (genérico)**, no un ejecutor del pipeline
> de descubrimiento. Ejecuta flujos **DECLARADOS** (config, como las plantillas) → sirve a
> cualquier instancia. Diseñado para **generalizar al CEO de una empresa agéntica**.

El rediseño convierte el Orquestador en un motor que:
1. Recibe un **objetivo** y una **entrada** (sector / dolor / planta-recurso / etc.)
2. Selecciona el **flujo declarado** que corresponde al tipo de entrada
3. **Ejecuta** el flujo paso a paso — el LLM no imposta el routing, lo lee del config
4. Escribe estado en el KM después de cada paso (idempotente, recuperable)
5. Para en **gates humanos** donde corresponde y espera

---

## 2. Arquitectura del motor (Capa 1 genérica)

### 2.1 Componentes

```
ENTRADA DEL USUARIO
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│  MOTOR (Capa 1 — genérico, plataforma/)                     │
│                                                             │
│  ┌───────────────┐    ┌─────────────────┐                  │
│  │  Flow Loader  │───▶│  Flow Executor  │                  │
│  │  (lee config) │    │  (corre pasos)  │                  │
│  └───────────────┘    └────────┬────────┘                  │
│                                │                            │
│  ┌───────────────┐    ┌────────▼────────┐                  │
│  │  KM State     │◀──▶│  Step Runner    │                  │
│  │  (pipeline_   │    │  (llama agentes │                  │
│  │   status)     │    │   vía run())    │                  │
│  └───────────────┘    └────────┬────────┘                  │
│                                │                            │
│              ┌─────────────────▼──────────────┐            │
│              │  Agent Registry (Capa 2)        │            │
│              │  {"mercado": market_agent.run,  │            │
│              │   "evidencia": evidence.run, …} │            │
│              └─────────────────────────────────┘            │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
EXPEDIENTE DE DECISIÓN → KM + render markdown
```

### 2.2 Separación de capas

| Componente | Capa | Dónde vive |
|---|---|---|
| Motor (Flow Loader + Executor + Step Runner) | 1 — genérico | `plataforma/motor/` |
| Flow configs (YAML/JSON) | 2 — instancia | `criza/orquestador/flows/` |
| Agent Registry | 2 — instancia | `criza/orquestador/registry.py` |
| KM state writer | 1 — genérico | ya existe en `motor_api.actualizar_props` |

> **Nota de construcción:** en v1 del motor, el Flow Loader y Executor pueden vivir en
> `criza/orquestador/motor.py` (Capa 2). Cuando DPN o EIA-1 necesiten el motor, se mueve a
> `plataforma/motor/`. No anticipar la extracción antes de tener la segunda instancia.

---

## 3. Schema de flujos declarados

### 3.1 Formato (YAML canónico)

```yaml
# criza/orquestador/flows/pipeline_dolor.yaml
name: "pipeline_criza_dolor"
version: "1.0"
description: "Pipeline para entradas con dolor específico conocido"
entry_type: "dolor"

objective_template: |
  Armar el expediente de decisión para el dolor: {entry.descripcion}.
  Mercado objetivo: {entry.mercado_objetivo}.

steps:
  - id: "crear_oportunidad"
    type: "km_write"
    action: "crear_oportunidad"
    props_from_entry:
      nombre: "entry.descripcion"
      descripcion: "entry.descripcion"

  - id: "market"
    type: "agent"
    agent: "mercado"
    contract_input:
      caso: "{entry.descripcion}"
      tarea: "Evaluar cruces 1, 3 y 4 del expediente de decisión"
      conocimiento:
        oportunidad_id: "{state.oportunidad_id}"
    on_error: "stop"

  - id: "evidence"
    type: "agent"
    agent: "evidencia"
    depends_on: "market"
    contract_input:
      caso: "{entry.descripcion}"
      tarea: "Evaluar factibilidad técnica — llenar cruce 2"
      contexto: "{steps.market.output.análisis.cruces.cruce_1}"
      conocimiento:
        oportunidad_id: "{state.oportunidad_id}"
    routing:
      field: "próximo_agente"
      routes:
        cientifico_especialista: "especialista"
        _default: "armador"
    on_error: "continue"

  - id: "especialista"
    type: "agent"
    agent: "cientifico_especialista"
    depends_on: "evidence"
    contract_input:
      conocimiento:
        oportunidad_id: "{state.oportunidad_id}"
    on_error: "continue"
    next: "armador"

  - id: "armador"
    type: "agent"
    agent: "armador"
    depends_on: ["market", "evidence"]
    contract_input:
      conocimiento:
        oportunidad_id: "{state.oportunidad_id}"
    on_error: "stop"

completion:
  write_status: true
  notify_human: true
```

### 3.2 Flow para entradas tipo `sector`

```yaml
name: "pipeline_criza_sector"
version: "1.0"
entry_type: "sector"

objective_template: |
  Mapear el espacio de oportunidades en el sector: {entry.sector}.
  Identificar el candidato más prometedor y armar su expediente.

steps:
  - id: "crear_oportunidad"
    type: "km_write"
    action: "crear_oportunidad"

  - id: "investigacion_amplia"
    type: "agent"
    agent: "investigacion_amplia"
    contract_input:
      caso: "{entry.sector}"
      conocimiento:
        oportunidad_id: "{state.oportunidad_id}"
    gate_humano:
      mensaje: |
        Investigación Amplia terminó.
        Candidatos identificados:
        {steps.investigacion_amplia.output.recomendaciones}

        ¿Cuál candidato querés profundizar? (escribe el texto del candidato o su índice)
      espera_campo: "candidato_elegido"

  - id: "market"
    type: "agent"
    agent: "mercado"
    depends_on: "investigacion_amplia"
    contract_input:
      caso: "{gate.candidato_elegido}"
      conocimiento:
        oportunidad_id: "{state.oportunidad_id}"

  - id: "evidence"
    type: "agent"
    agent: "evidencia"
    depends_on: "market"
    contract_input:
      conocimiento:
        oportunidad_id: "{state.oportunidad_id}"
    routing:
      field: "próximo_agente"
      routes:
        cientifico_especialista: "especialista"
        _default: "armador"

  - id: "especialista"
    type: "agent"
    agent: "cientifico_especialista"
    next: "armador"

  - id: "armador"
    type: "agent"
    agent: "armador"
```

### 3.3 Flow para entradas tipo `supply-push` (tecnología / planta-recurso)

```yaml
name: "pipeline_criza_supply"
version: "1.0"
entry_type: "tecnologia"  # o "planta-recurso"

steps:
  - id: "crear_oportunidad"
    type: "km_write"

  - id: "investigacion_amplia"
    type: "agent"
    agent: "investigacion_amplia"
    contract_input:
      caso: "{entry.descripcion}"

  - id: "gate_validacion_activo"
    type: "gate_humano"
    mensaje: |
      Antes de investigar en profundidad:
      ¿Confirmar que el activo tecnológico/planta está disponible y accesible?
    espera_campo: "activo_confirmado"
    on_no: "stop"

  - id: "market"
    type: "agent"
    agent: "mercado"
    # idem sector...

  # ... resto del pipeline
```

---

## 4. Contrato del Motor (API)

### 4.1 `motor.ejecutar(flow_config, entry, state_inicial)`

```python
async def ejecutar(
    flow_config: dict,          # flow YAML cargado como dict
    entry: dict,                # la entrada del usuario {tipo, descripcion, ...}
    tenant: str,                # "criza", "dpn", "eia1"
    state_inicial: dict = None, # para reanudar desde un paso (recovery)
    verbose: bool = False,
) -> MotorResult:
    """
    Ejecuta el flujo declarado. Para en gates humanos.
    Escribe `props.pipeline_status` en el KM después de cada paso.
    
    Returns:
        MotorResult(
            status: "completo" | "gate_humano" | "error" | "stop",
            oportunidad_id: str,
            gate_data: dict | None,      # contexto del gate si status="gate_humano"
            pipeline_status: dict,       # estado completo de todos los pasos
        )
    """
```

### 4.2 `motor.reanudar(oportunidad_id, gate_response, tenant)`

```python
async def reanudar(
    oportunidad_id: str,
    gate_response: dict,   # respuesta humana al gate {campo: valor}
    tenant: str,
    verbose: bool = False,
) -> MotorResult:
    """
    Reanuda un pipeline que estaba esperando en un gate humano.
    Lee el pipeline_status del KM para saber en qué paso estaba.
    """
```

### 4.3 `MotorResult` (dataclass)

```python
@dataclass
class MotorResult:
    status: str                   # "completo" | "gate_humano" | "error" | "stop"
    oportunidad_id: str
    pipeline_status: dict         # {paso_id: {status, output, error, started_at, ended_at}}
    gate_data: dict | None        # None si no es gate_humano
    expediente_markdown: str | None  # presente solo si status="completo"
```

---

## 5. State del pipeline en el KM

Después de cada paso, el motor escribe en `props.pipeline_status`:

```json
{
  "flow": "pipeline_criza_dolor",
  "flow_version": "1.0",
  "objetivo": "Armar expediente para el dolor: olor de estiércol porcino",
  "started_at": "2026-06-27T20:00:00Z",
  "status": "gate_humano",
  "current_step": "investigacion_amplia",
  "steps": {
    "crear_oportunidad": {
      "status": "completo",
      "ended_at": "2026-06-27T20:00:05Z"
    },
    "investigacion_amplia": {
      "status": "gate_humano",
      "gate_mensaje": "Candidatos identificados...",
      "espera_campo": "candidato_elegido"
    },
    "market": {"status": "pendiente"},
    "evidence": {"status": "pendiente"},
    "armador": {"status": "pendiente"}
  }
}
```

---

## 6. Agent Registry (Capa 2 — CRIZA)

```python
# criza/orquestador/registry.py

def _build_registry():
    """Lazy imports — igual que orquestador.py v1."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from market_agent.market_agent import run as _market_run
    from evidence_generalista.evidence_generalista import run as _evidence_run
    from investigacion_amplia.investigacion_amplia import run as _investigacion_run
    from armador.armador import run as _armador_run

    return {
        "mercado":               _market_run,
        "evidencia":             _evidence_run,
        "investigacion_amplia":  _investigacion_run,
        "armador":               _armador_run,
        "cientifico_especialista": None,  # stub hasta SEB-149
    }

AGENT_REGISTRY = None

def get_registry() -> dict:
    global AGENT_REGISTRY
    if AGENT_REGISTRY is None:
        AGENT_REGISTRY = _build_registry()
    return AGENT_REGISTRY
```

---

## 7. Motor v2 vs Orquestador v1 — qué queda, qué cambia

| Aspecto | v1 (LLM puro) | v2 (motor genérico) |
|---|---|---|
| Routing | LLM decide en SYSTEM_PROMPT | Config YAML declara el flujo |
| Nuevos flujos | Nuevo agent / nuevo prompt | Nuevo YAML en `flows/` |
| Portabilidad | Solo CRIZA | Cualquier instancia (Capa 1) |
| Estado | No persiste paso a paso | `props.pipeline_status` actualizado en cada paso |
| Recovery | No (si cae, reinicia) | Reanuda desde el último paso completado |
| Gates humanos | Manual (Sebas sabe qué hacer) | Declarados en YAML, motor pausa y espera |
| LLM | Decide TODO | Ejecuta el flujo; LLM solo en las tools de los agentes |
| Tests | 20 unit tests (v1) | Tests del motor + tests de cada flow config |

---

## 8. Fractal CEO — patrón un nivel arriba

D10 dice que el Orquestador está diseñado para **generalizar al CEO** de una empresa agéntica.
La lectura fractal:

```
CEO de empresa agéntica
    ├── objetivo: "llevar adelante la empresa en su área de foco"
    ├── flujos declarados: {"ventas": flow_ventas, "operaciones": flow_ops, ...}
    ├── agentes funcionales: Ventas / Marketing / Operaciones / Finanzas / R&D
    └── motor: exactamente el mismo — ejecuta flujos, para en gates humanos, escribe estado

Orquestador CRIZA (hoy)
    ├── objetivo: "armar expediente de decisión para esta oportunidad"
    ├── flujos declarados: {dolor, sector, supply-push}
    ├── agentes investigadores: Mercado / Evidencia / Investigación Amplia / Armador
    └── motor: el mismo motor genérico
```

El motor no sabe si está corriendo una empresa de biotech o de logistics. Lee el objetivo,
ejecuta el flujo, llama a los agentes disponibles. Es el mismo código.

**Condición para que el CEO gane autonomía:**
El CEO (Orquestador en rol CEO) puede tomar decisiones de routing sin gate humano cuando:
1. El nivel de confianza del output del paso anterior es "alto" (dato establecido)
2. La decisión es reversible (no implica gasto/compromiso externo)
3. El flujo lo declara como auto-enrutable (`gate_humano: false`)

Hoy: todos los gates son humanos. La autonomía se gana por etapas, con evidencia de que
los agentes producen output de calidad suficiente para decisiones no supervisadas.

---

## 9. Secuencia de construcción

| Fase | Qué se construye | Prerequisito |
|---|---|---|
| **v2.0** (próximo) | `motor.py` + `flows/pipeline_dolor.yaml` + `registry.py` | Todos los agentes con contrato SEB-115 ✅ |
| **v2.1** | `flows/pipeline_sector.yaml` — flow con gate humano en investigación amplia | SEB-146 ✅ (investigacion_amplia) |
| **v2.2** | `flows/pipeline_supply.yaml` + refactor divergente | SEB-147 (divergente redefinido) |
| **v2.3** | Motor → `plataforma/motor/` (extracción Capa 1) | Segunda instancia (DPN o EIA-1) que lo necesite |
| **CEO v1** | Flujos de empresa genérica + autoridad de decisión parcial | Después de 10+ expedientes completos |

---

## 10. Decisiones de diseño

| # | Decisión | Alternativa descartada | Razón |
|---|---|---|---|
| A | Flujos en YAML, no en Python | Código Python para los flujos | YAML es legible por humanos, editable sin programar, versionable; los flows son configuración, no lógica |
| B | Motor en Capa 1 desde el diseño (aunque se construya en Capa 2 primero) | Diseñar solo para CRIZA | Regla de plataforma-primero (CLAUDE.md): nunca "generalizamos después" |
| C | LLM queda solo en los agentes (no en el motor) | Motor LLM que también toma decisiones de routing | Separation of concerns: el motor ejecuta, los agentes razonan. El motor LLM (v1) mezcla ambos roles |
| D | Registry en código (no en config) | Registry en YAML como parte del flow | Los agentes son código Python, no servicios independientes. El registry conecta nombres con imports |
| E | `pipeline_status` en KM después de cada paso | Solo al final | Habilita recovery y transparencia; el motor puede reanudarse desde cualquier punto sin rehacer todo |
| F | Gates humanos declarados en el flow | Gates hardcodeados en el motor | Flexibilidad: cada instancia decide cuándo pausar sin tocar el motor |
| G | Routing declarativo (`routes: campo → siguiente_paso`) | LLM que interpreta el output y decide | Reproducible, testeable, auditable. El routing del flujo no debe depender de la interpretación del modelo |

---

## 11. Lo que NO es este diseño

- **No es un framework de agentes general** (no es LangGraph, no es AutoGen). Es específico para
  el patrón EMPRESAS-IA: flujo de investigación → expediente de decisión.
- **No reemplaza el contrato SEB-115**. El contrato `run(contract_input) → dict` sigue siendo
  la interfaz entre el motor y cada agente. El motor llama `run()` — los agentes no saben que
  hay un motor.
- **No elimina los gates humanos**. Los gates son load-bearing (principio 8 del CLAUDE.md:
  "decisión final siempre humana"). El motor los hace explícitos y estructurados, no los elimina.

---

*Próximo paso: construir `criza/orquestador/motor.py` (v2.0) — motor mínimo para el flow `pipeline_dolor`.*
*Prerequisito: todos los agentes del pipeline con contrato SEB-115 ✅ (completo 2026-06-27).*
