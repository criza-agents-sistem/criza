# Design Gate — Especialista Microbiólogo

**Versión:** 1.0
**Fecha:** 2026-08-16
**Módulo:** `criza/microbiologo_agent/`
**Capa:** 2 (instancia CRIZA)
**Estado:** ✅ LISTO

---

## 1. Identidad

| Pregunta | Respuesta |
|---|---|
| ¿Qué es? | Agente LLM especialista en microbiología aplicada al tratamiento biológico de efluentes/aguas residuales — evalúa qué microorganismos, procesos y enfoques técnicos aplican a un problema dado. |
| ¿Qué problema resuelve en una oración? | El primer especialista de la "biblioteca de especialistas" (`docs/PROPUESTA_DESTINO.md` §5) más allá de los 4 agentes del expediente viejo — cubre el ángulo científico que hoy ningún agente activo cubre. |
| ¿Quién lo usa? | Sebas, directo o vía el Motor (dos puertas de entrada, `PROPUESTA_CONDUCTOR.md` §3.1) — no hay Conductor todavía que lo invoque por su cuenta. |
| ¿De qué depende? | `utils/ai_client.py` (LiteLLM), `utils/corpus.py::buscar_corpus_cientifico`, `km_tools/search.py::get_sector_corpus`, `utils/openalex.py`, `utils/agrovoc.py`, `knowledge_module.preflight`, `knowledge_module.aprendizaje`. |
| ¿Qué depende de él? | Nada todavía — es el primer consumidor de este patrón fuera de Evidence Generalista/Investigación Amplia. El futuro Armador/Conductor podrían leer `props.microbiologo` más adelante. |
| ¿Milestone? | Etapa 1 del plan de construcción del nuevo sistema de agentes (`docs/progress/2026-08-16.md`). |

---

## 2. Trazabilidad diseño → implementación

### Por qué este agente y no reciclar `scientific_agent/specialist_proteins.py`

Investigado antes de diseñar (no asumido): `specialist_proteins.py` tiene tools de ingeniería de
proteínas (UniProt, ESMFold, ProteinMPNN, FoldX) — no calzan con biología ambiental de
biodigestores. Peor: su `SYSTEM_PROMPT` (líneas 397-407) está clavado a un caso específico
cancelado ("Andrés — Buenas Maltas", con restricciones tecnológicas hardcodeadas del tipo "NO
tiene capacidad de ingeniería genética"). Es exactamente el patrón de sesgo que
`PROPUESTA_CONDUCTOR.md` §6 describe como el motivo por el que ese agente "contaminaría
cualquier análisis" si se enchufa tal cual. No se recicla como base — se abandona salvo lo que
ya es genérico y compartido (`utils/openalex.py`, que este agente sí reusa).

**Template real: `evidence_generalista/evidence_generalista.py`.** Ya es technology-agnostic,
ya conecta las 4 tools de corpus que este agente necesita, ya usa el contrato SEB-115 completo,
ya usa `knowledge_module.preflight` para declarar cobertura en vez de asumirla, y ya pasó por la
migración a la costura (2026-08-15) — no hay que rehacer ese trabajo, solo clonarlo.

### Entidades

| Entidad | Descripción | Scope v1 | Estado |
|---|---|---|---|
| `search_literature` | OpenAlex vía `utils/openalex.py` (compartido). | ✅ incluido | ✅ construido |
| `buscar_corpus_cientifico` | Búsqueda semántica CONICET+INTA vía `utils/corpus.py` (compartido con market_agent/evidence_generalista). | ✅ incluido | ✅ construido |
| `search_corpus_inta` | FTS exhaustivo sobre el corpus INTA vía `km_tools/search.py::get_sector_corpus` (mismo patrón que evidence_generalista). | ✅ incluido | ✅ construido |
| `expand_agrovoc` | Expansión de términos vía tesauro AGROVOC (`utils/agrovoc.py`). | ✅ incluido | ✅ construido |
| `search_kegg` | Rutas metabólicas/módulos/compuestos/genes vía `utils/kegg.py` (REST, sin auth). Sumado 2026-08-16, decisión F. | ✅ incluido | ✅ construido |
| `search_rhea` | Reacciones bioquímicas con EC number vía `utils/rhea.py` (REST, sin auth). Sumado 2026-08-16, decisión F. | ✅ incluido | ✅ construido |
| `search_uniprot` | Identidad de enzima/proteína (función, organismo, EC) vía `utils/uniprot.py` (REST, sin auth). Sumado 2026-08-16, decisión F. | ✅ incluido | ✅ construido |
| `search_bacdive` | Fenotipo de cepas bacterianas vía `utils/bacdive.py` (REST, v2, sin auth — DSMZ sacó el requisito de registro en febrero 2026). Sumado 2026-08-16, decisión F. | ✅ incluido | ✅ construido y verificado en vivo, sin pendientes |
| `submit_evaluacion_tecnica` | Output estructurado obligatorio. Nombre genérico a propósito (no `submit_microbiologia`) — mismo schema se reusa para el ingeniero ambiental (Etapa 7 del plan), así el futuro Armador/Conductor pueden leer especialistas distintos con el mismo shape. | ✅ incluido | ✅ construido |

**BRENDA (cinética de enzimas — Km, kcat, Ki) queda deliberadamente afuera de esta ronda** — su
API es SOAP-only (WSDL verificado en vivo, sin equivalente REST), fricción real de integración
distinta a las 4 anteriores. Ver Etapa 8 del plan (`C:\Users\sebab\.claude\plans\
greedy-cooking-llama.md`) — decisión de Sebas 2026-08-16: sumar las 4 REST ahora, BRENDA en una
etapa separada.

### Schema de `evaluacion_tecnica`

```json
{
  "resumen": {
    "valor": "síntesis de la evaluación técnica, en prosa",
    "estado": "establecido|asumido|a-confirmar",
    "fuente": "..."
  },
  "microorganismos_o_procesos_relevantes": [
    {"nombre": "...", "rol": "...", "estado": "establecido|asumido|a-confirmar", "fuente": "..."}
  ],
  "enfoques_tecnicos_identificados": [
    {"enfoque": "...", "madurez": "maduro|emergente|experimental|conceptual", "fuente": "..."}
  ],
  "riesgos_o_limitaciones": [
    {"riesgo": "...", "estado": "establecido|asumido|a-confirmar"}
  ],
  "brechas_de_conocimiento": [
    {"brecha": "...", "impacto_en_decision": "alto|medio|bajo", "donde_confirmar": "..."}
  ],
  "especialista_adicional_recomendado": {
    "si_no": true,
    "descripcion": "qué análisis adicional aportaría valor — sin nombrar el tipo de especialista (principio 7b)",
    "razon": "..."
  }
}
```

Mismo principio que `evidence_generalista` (Design Gate, decisión D): el agente NO nombra qué
tipo de especialista hace falta, describe QUÉ análisis falta. Quien invoque decide si hay
alguien disponible para eso.

### Contrato SEB-115

```python
INPUT_CONTRACT  = {"agent": "microbiologo", "version": "1.0",
                   "fields": {caso, tarea, contexto, conocimiento, herramientas}}
OUTPUT_CONTRACT = {"agent": "microbiologo", "version": "1.0",
                   "fields": {análisis, nivel_confianza, recomendaciones, próximo_agente, nuevo_conocimiento}}

async def run(contract_input: dict, verbose: bool = False, model: str = DEFAULT_MODEL) -> dict:
    """Interfaz estándar del Orquestador. `análisis` incluye siempre `informe_completo`
    (convención 2026-08-15) — es lo que la costura persiste tal cual en `props.microbiologo`."""
```

**No escribe al KM él mismo.** Desde la migración del 2026-08-15 (`orquestador/invocador.py`),
persistir es responsabilidad de la costura, no del agente — este agente no tiene ningún
`motor_api.actualizar_props` propio, ni falta que le haga.

### KM write — Especialista Microbiólogo

| Tipo de output | Qué contiene | Key en KM | Cómo | Estado |
|---|---|---|---|---|
| **Resultado estructurado + informe (oportunidad)** | `evaluacion_tecnica` + `especialista_adicional_recomendado` + `informe_completo` (markdown íntegro) | `props.microbiologo` | La costura (`invocador.py::invocar_agente`), no el agente | ✅ construido (por diseño, no hay nada que construir acá) |
| **Resultado estructurado + informe (frente, casos.yaml)** | Mismo shape, dentro de `documento_caso.props.analisis_estructurado` + `.contenido` (informe) | `documento_caso` nuevo, conectado vía `frente_produce_documento` | La costura (`invocador.py::invocar_agente` → `utils/casos.py::guardar_documento_de_frente`), no el agente | ✅ construido, decisión G (2026-08-16) |
| **Token usage** | Tokens consumidos | `props.token_usage.microbiologo` de la oportunidad (camino viejo) o del **frente** (camino `casos.yaml`) | `TokenTracker` + `motor_api.actualizar_props` (el agente sí escribe esto — mismo patrón que los 4 activos, es local a la corrida, no al resultado) | ✅ construido |
| **Aprendizaje** | Lecciones del caso | área `lecciones` | `aprendizaje` | 🔵 pendiente — misma deuda intencional que evidence_generalista, no se cierra en esta etapa |

---

## 3. Checklist del playbook

### Seguridad Nivel 1

- [x] Credenciales en `.env`, nunca en código — usa `.env` propio de `microbiologo_agent/`, mismo patrón que los otros agentes
- [x] `.env` en `.gitignore` (ya cubierto por el `.gitignore` raíz del repo)
- [x] `.env.example` completo
- [x] Sin credenciales en historial de git

### Estructura de archivos

- [x] `microbiologo_agent.py` — SYSTEM_PROMPT + TOOLS + `run_agent()` + `run()`
- [x] `run.py` — runner interactivo
- [x] `docs/DESIGN_GATE.md` — este archivo
- [x] `.env.example`
- [x] `tests/`

### Testing

- [x] Test: TOOLS tiene exactamente 9 tools (4 de corpus + 4 bioquímicas + `submit_evaluacion_tecnica`, decisión F)
- [ ] Test: `submit_evaluacion_tecnica` tiene los 6 campos del schema como required
- [ ] **Test explícito del checklist anti-sesgo: `SYSTEM_PROMPT` no contiene ninguna de las
      strings "Helios", "biogás", "biodigestor", "efluente de biogás", "Mateo", "Andrés"** — el
      control concreto contra repetir el sesgo de `specialist_proteins.py`. El caso entra solo
      por `contract_input`, nunca por el prompt.
- [ ] Test: `SYSTEM_PROMPT` no nombra tipos de especialista en `especialista_adicional_recomendado`
      (principio 7b, mismo patrón que evidence_generalista)
- [ ] Test: `run_agent` mock captura `submit_evaluacion_tecnica`
- [ ] Test: `run()` arma `análisis` con `informe_completo` adentro, no escribe al KM directamente
- [ ] Al menos 1 integration test real contra el corpus INTA/CONICET

---

## 4. Scope explícito por versión

| Feature | Versión | Razón |
|---|---|---|
| Conexión al modelo de datos `casos.yaml` (leer/escribir `frente`/`documento_caso` de Helios) | ✅ v1.1 (2026-08-16, decisión G) | Construido en la Etapa 4 (parte 2), después de tener staging real (parte 1) — verificado en vivo escribiendo un `documento_caso` real contra el 'Frente técnico' de Helios en staging, confirmando además que producción quedó intacta. |
| Persistencia de lecciones de caso (`aprendizaje.guardar_leccion_caso`) | backlog | Misma deuda intencional que `evidence_generalista` — no bloquea nada hoy. |
| Tools bioquímicas (KEGG/Rhea/UniProt/BacDive) | ✅ v1 (2026-08-16, decisión F) | Sebas confirmó necesidad real y concreta del caso que trae ("bacterias, encimas") — se suman de una en vez de esperar una corrida que la muestre, con el mismo rigor de verificación en vivo (curl real de cada API antes de codear, no asumido). |
| BRENDA (cinética de enzimas, SOAP) | Etapa 8 del plan | Fricción de integración real y distinta (SOAP vs REST) — Sebas pidió sumarla en una etapa separada, no ahora. |

---

## 5. Decisiones requeridas antes de arrancar

| # | Pregunta | Opciones | Decisión tomada | Fecha |
|---|---|---|---|---|
| A | ¿Reciclar `specialist_proteins.py` o construir nuevo? | Reciclar / Nuevo | **Nuevo**, clonando `evidence_generalista.py`. Confirmado por Sebas — ver diagnóstico arriba y `docs/progress/2026-08-16.md`. | 2026-08-16 |
| B | ¿Cuántos especialistas científicos se construyen en esta etapa? | 1 (microbiólogo) / los 3 candidatos de §5 de una | **1 solo.** El patrón nunca se probó fuera de 2 agentes — clonarlo 3 veces antes de validarlo una vez multiplica el riesgo de repetir un defecto no visto todavía. Ingeniero ambiental y agrónomo quedan para la Etapa 7 del plan, con el patrón ya probado en uso real. | 2026-08-16 |
| C | ¿Tool set? | Solo las 4 genéricas de corpus / sumar algo nuevo de entrada | **Solo las 4 genéricas** (`search_literature`, `buscar_corpus_cientifico`, `search_corpus_inta`, `expand_agrovoc`) — cero trabajo nuevo de integración, mismo patrón ya probado. Nada de dominio-específico hasta que una corrida real muestre que hace falta. | 2026-08-16 |
| D | ¿Conecta con `casos.yaml` (Helios) en esta etapa? | Sí / No, todavía contra `props` de `oportunidad` | **No** — sigue el patrón viejo (`props` de `oportunidad`) como los 4 agentes activos hoy. La integración con `casos.yaml` es la Etapa 4 del plan, después de introducir staging. | 2026-08-16 |
| E | ¿Nombre del tool de submit y del schema? | `submit_microbiologia` (específico) / `submit_evaluacion_tecnica` (genérico) | **Genérico** (`submit_evaluacion_tecnica`) — mismo schema se va a reusar para el ingeniero ambiental (Etapa 7), así el futuro Armador/Conductor leen especialistas distintos con la misma forma. | 2026-08-16 |
| F | ¿Sumar tools de bases de datos bioquímicas (KEGG/Rhea/UniProt/BacDive/BRENDA) ahora o esperar señal de una corrida real? | Esperar señal (decisión C original) / Sumar ahora, Sebas confirma necesidad real del caso | **Sumar las 4 REST ahora** (KEGG, Rhea, UniProt, BacDive) — Sebas: "sé que este caso real que tengo las va a pedir". Cada API se verificó en vivo antes de codear (curl real, no asumido): las 4 son REST **sin auth** (BacDive se verificó dos veces: primero se construyó con Basic Auth asumiendo cuenta requerida — Sebas señaló la doc real de BacDive, que confirma que desde febrero 2026 la API es pública sin registro; se corrigió el cliente para no pedir credenciales). **BRENDA queda afuera de esta ronda** — confirmado en vivo que es SOAP-only (WSDL real, sin equivalente REST), fricción de integración genuinamente distinta — Sebas pidió sumarla en una etapa separada (Etapa 8 del plan). | 2026-08-16 |
| G | ¿Cómo se conecta el agente al modelo de `casos.yaml`? | Reemplazar el modelo viejo (`oportunidad`) / Sumarlo como camino alternativo, mutuamente excluyente | **Camino alternativo, no reemplazo.** `contract_input['conocimiento']` acepta `oportunidad_id` (modelo viejo, sin cambios) O `frente_id` (nuevo) — nunca los dos juntos. `run_agent_desde_frente()` lee `caso`+`frente`+`pendientes` vía `utils/casos.py` (nuevo, genérico — no específico de microbiólogo, para que el próximo especialista de la Etapa 7 lo reuse gratis). La costura (`invocador.py::invocar_agente`) persiste el resultado como `documento_caso` conectado vía `frente_produce_documento` en vez de `props[prop_key]` — mismo principio de siempre (el agente no persiste nada, la costura sí), generalizado a un segundo modelo de dato. `token_usage` de una corrida por-frente se guarda en `props` del **frente**, no de ningún `oportunidad` (no hay una oportunidad involucrada en ese camino). Verificado en vivo: `documento_caso` real (11.370 chars) creado y conectado al 'Frente técnico' real de Helios, corrido contra el branch de staging (`docs/STAGING.md`) — producción confirmada intacta (0 documentos) tras la corrida. | 2026-08-16 |

| H | Etapa 10 (2026-08-16) — Sebas pidió chat directo con cada especialista, no solo con el Conductor. ¿Cómo se vuelve conversacional el agente sin perder el contrato SEB-115 (`run()`, de un turno, que ya usa el Motor/la costura)? | Reemplazar `run()` por un loop conversacional / Sumar un camino conversacional aparte, `run()` intacto | **Sumar aparte.** `_run_loop()` (el loop de un turno, usado por `run_agent`/`run_agent_desde_frente`/`run()`) no se toca. Nuevo: `iniciar_sesion(frente_id)` arma el primer mensaje (mismo `build_input_desde_frente` que ya usaba la corrida formal) y `enviar_mensaje(messages, texto, frente_id)` es un loop tipo `conductor.enviar_mensaje()` — multi-turno, sin forzar un final. `TOOLS_CHAT = TOOLS - {submit_evaluacion_tecnica}` a propósito: el chat da acceso al mismo conocimiento (búsquedas, KEGG/Rhea/UniProt/BacDive), pero la evaluación formal persistida sigue siendo exclusiva del camino de un turno vía la costura — si Sebas quiere el documento, se lo pide al Conductor, mismo principio de "nunca bypasear la costura" que ya rige el resto del sistema. El dispatch de tools (`_despachar_tool`) se extrajo del if/elif inline de `_run_loop` a una función propia para que ambos caminos lo reusen sin duplicar ~170 líneas — refactor verificado behavior-preserving corriendo los tests existentes sin cambios antes de sumar nada nuevo. | 2026-08-16 |

---

## 6. Estado del gate

**Estado actual:** ✅ LISTO

Decisiones A–H cerradas, ninguna abierta. El agente clona un patrón ya probado (evidence_generalista) —
no hay diseño nuevo de fondo, solo aplicación a un dominio distinto con el checklist anti-sesgo
como control explícito.

**Deuda intencional documentada:**
- Persistencia de lecciones de caso → backlog, misma deuda que evidence_generalista
- Tools de dominio específicas → solo si una corrida real las requiere
- BRENDA (cinética de enzimas) → Etapa 8 del plan
- El chat (decisión H) no escribe lecciones al cierre (a diferencia del Conductor, Etapa 9) — no
  pedido explícitamente para especialistas, mismo backlog que "persistencia de lecciones de caso"
