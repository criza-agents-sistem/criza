"""
Agente Armador del Expediente — CRIZA (SEB-145)

NO investiga. NO elige. NO inventa. Ensambla el expediente de decisión desde
los props que los agentes investigadores ya escribieron en el KM.

Input : oportunidad del KM (props.mercado → cruces 1/3/4 + informe completo;
                             props.evidencia → cruce 2 si existe)
Output: expediente completo 6 bloques + informe rico (5-10 páginas) + write-back al KM

El resumen_markdown NO es un resumen. Es el documento completo de decisión:
incluye TODO el análisis que los agentes investigadores generaron, sin resumirlo.

Ver docs/DESIGN_GATE.md — decisiones A–F (2026-06-16).
"""

import json
import os
import time
from pathlib import Path

_ARMADOR_DIR = Path(__file__).parent
_CRIZA_DIR = _ARMADOR_DIR.parent

from dotenv import load_dotenv

load_dotenv(_ARMADOR_DIR / ".env", override=True)

import anthropic

from knowledge_module.motor import api as motor_api
import knowledge_module.aprendizaje as aprendizaje
from utils.token_tracker import TokenTracker
from knowledge_module.preflight import PreflightResult

DEFAULT_MODEL = os.getenv("ARMADOR_MODEL", "claude-sonnet-4-6")

# El expediente son 5-10 páginas de markdown viajando dentro del input de
# `submit_expediente`. Con 16.000 no entraba: la primera corrida real cortó
# exactamente en el techo y devolvió un expediente vacío. Con 32.000 la misma
# corrida usó 30.718 — quedó justo, así que se sube a 64.000 (el techo real del
# modelo para requests con streaming) en vez de ajustar al pixel contra una
# sola muestra. Arriba de ~16k el SDK exige streaming (si no, la request puede
# morir por timeout HTTP), por eso la llamada usa `messages.stream()` +
# `get_final_message()`.
MAX_TOKENS = 64000


# ──────────────────────────────────────────────
# VALIDACIÓN DE COBERTURA AGUAS ARRIBA
# (orchestration-layer.md Decisión 6 — el armador no tiene fuentes propias, así que su
# "pre-flight" es verificar que lo que va a ensamblar tiene cobertura suficiente.)
# ──────────────────────────────────────────────

def _validar_cobertura_upstream(props: dict) -> PreflightResult:
    """
    Sin mercado no hay nada que ensamblar → bloqueante.
    Sin evidencia el cruce_2 queda a-confirmar (SEB-149 pendiente) → advertencia, no bloqueante,
    el armador ensambla igual y lo marca.
    Cobertura declarada como 'parcial-por-falla-de-fuente' o ausente en cualquiera de los dos →
    advertencia — el expediente puede estar subinformado, pero el armador no es quien decide
    frenar un caso real por eso.
    """
    mercado = props.get("mercado") or {}
    evidencia = props.get("evidencia") or {}

    bloqueantes: list[str] = []
    advertencias: list[str] = []
    fuentes_ok: list[str] = []
    fuentes_no_disponibles: list[str] = []

    if not mercado:
        bloqueantes.append("mercado: ausente — no hay nada que ensamblar sin al menos demanda/competencia")
        fuentes_no_disponibles.append("mercado")
    else:
        fuentes_ok.append("mercado")
        cobertura = (mercado.get("fuentes_y_cobertura") or {}).get("cobertura_declarada")
        if cobertura is None:
            advertencias.append("mercado: sin fuentes_y_cobertura declarada (corrida previa a Decisión 6)")
        elif cobertura == "parcial-por-falla-de-fuente":
            advertencias.append("mercado: cobertura parcial por falla de fuente")

    if not evidencia:
        advertencias.append("evidencia: ausente — cruce_2 queda a-confirmar (Evidence Científica no corrió, SEB-149)")
        fuentes_no_disponibles.append("evidencia")
    else:
        fuentes_ok.append("evidencia")
        cobertura = (evidencia.get("fuentes_y_cobertura") or {}).get("cobertura_declarada")
        if cobertura is None:
            advertencias.append("evidencia: sin fuentes_y_cobertura declarada (corrida previa a Decisión 6)")
        elif cobertura == "parcial-por-falla-de-fuente":
            advertencias.append("evidencia: cobertura parcial por falla de fuente")

    return PreflightResult(
        ok=len(bloqueantes) == 0,
        bloqueantes=bloqueantes,
        advertencias=advertencias,
        fuentes_ok=fuentes_ok,
        fuentes_no_disponibles=fuentes_no_disponibles,
    )


def _derive_cobertura_global(props: dict) -> str:
    """Rollup visible al humano: qué tan bien cubiertos estaban los cruces que alimentan el
    expediente. Calculado, no autoreportado por el modelo (veracidad por dato)."""
    señales = []
    for bloque in (props.get("mercado") or {}, props.get("evidencia") or {}):
        cobertura = (bloque.get("fuentes_y_cobertura") or {}).get("cobertura_declarada")
        if cobertura == "exhaustiva":
            señales.append(2)
        elif cobertura == "muestreada":
            señales.append(1)
        elif cobertura == "parcial-por-falla-de-fuente":
            señales.append(0)

    if not señales:
        return "bajo"
    promedio = sum(señales) / len(señales)
    if promedio >= 1.5:
        return "alto"
    if promedio >= 0.5:
        return "medio"
    return "bajo"


def _derive_nivel_confianza(bloque_3: dict) -> str:
    """`nivel_confianza` que devuelve `run()` al Motor — contado, no "¿produje un archivo?".

    Bug encontrado 2026-07-22: `run()` devolvía `"alto" if expediente else "bajo"`. La
    corrida real de metano calculó internamente `Confianza: MEDIO` en el propio
    resumen_markdown y `run()` reportó `alto` al Motor, que lo escribió en
    `pipeline_status` — un dato que miente sobre sí mismo.

    No usa `bloque_3.indice_confianza` tal cual: aunque el modelo lo llena siguiendo una
    regla explícita (SYSTEM_PROMPT, paso 5), sigue siendo autoreporte. Mismo criterio que
    ya se aplica acá arriba a `cobertura_global`: establecido > asumido (principio de
    veracidad por dato) — se cuenta, no se confía.
    """
    establecidos = len(bloque_3.get("establecidos") or [])
    asumidos = len(bloque_3.get("asumidos") or [])
    a_confirmar = len(bloque_3.get("a_confirmar") or [])
    total = establecidos + asumidos + a_confirmar

    if total == 0:
        return "bajo"
    if a_confirmar / total >= 0.5:
        return "bajo"
    if establecidos / total >= 0.5:
        return "alto"
    return "medio"

# ──────────────────────────────────────────────
# SYSTEM PROMPT
# ──────────────────────────────────────────────

_SPEC = (_CRIZA_DIR / "docs" / "expediente_decision_SPEC.md").read_text(encoding="utf-8")

SYSTEM_PROMPT = (
    _SPEC
    + """

---

## Sos el Agente Armador del Expediente (CRIZA)

Tu único rol es ENSAMBLAR el expediente a partir de los datos que los agentes investigadores
ya levantaron. No investigás, no elegís, no inventás.

**Qué significa ENSAMBLAR:** incluís TODA la información que los agentes generaron. No la resumís
en pocas frases. El resultado tiene que tener profundidad suficiente para que Sebas pueda ir a
hablar con un científico, un experto de mercado y un abogado de PI con preguntas concretas.

### Lo que NO hacés
- No buscás en internet, bases de datos ni APIs externas.
- No elegís el producto ni recomendás "ir" / "no ir".
- No inventás números. No generás timelines propios (el modelo sobreestima tiempos).
- No completás con datos que no tenés — los marcás `a-confirmar` con dónde conseguirlos.

### Tu proceso (en orden, sin saltear pasos)

**Paso 1 — Leer TODO el material.**
El mensaje inicial contiene los informes completos de los agentes investigadores (sección
"Informe completo del Agente de Mercado") y/o sus datos estructurados. Leé todo antes de escribir.

**Paso 2 — Cruce 2 (Capacidad/Tecnología).**
- Si los datos de evidencia existen → usarlos tal como están, manteniendo sus estados.
- Si están ausentes → construir cruce_2 completo con estado `a-confirmar` en cada campo,
  `donde_confirmar`: "Agente de Evidencia Científica (SEB-149, por construir)".

**Paso 3 — Bloque 1: Tesis + puerta.**
Sintetizar en 2-3 frases: qué producto/solución, para quién, por qué ahora.
Solo lo afirmable con los datos disponibles.

**Paso 4 — Bloque 2: Los 4 cruces (JSON estructurado).**
Copiar fielmente los cruces de los agentes. No alterés campos ni estados.
Si un cruce entero falta → campo `a-confirmar` para cada sub-campo.
Este bloque es para lectura máquina — el KM lo guarda en formato estructurado.

**Paso 5 — Bloque 3: Mapa de confianza.**
Recorrer TODOS los campos de TODOS los cruces. Clasificar en:
- `establecidos`: datos con fuente verificada (estado=establecido)
- `asumidos`: supuestos con peso (estado=asumido)
- `a_confirmar`: no se pudo establecer (estado=a-confirmar)
Regla de `indice_confianza`:
- "bajo" → mayoría de campos clave son a-confirmar o cruce 2 entero falta
- "alto" → mayoría de campos de cruce_1 y cruce_3 establecidos
- "medio" → resto

**Paso 6 — Bloque 4: Nivel de madurez.**
- `hipotesis_de_screening`: cruce 1 (demanda) mayormente a-confirmar O cruce 3 sin datos
- `parcialmente_validado`: cruce 1 y 3 con datos, pero cruce 2 ausente o cruce 4 con gaps
- `listo_para_decision`: cruces 1 y 3 con datos establecidos, cruce 4 razonable, gaps acotados

**Paso 7 — Bloque 5: Qué falta para decidir.**
Tomar los a-confirmar de mayor impacto en la decisión del bloque 3.
Priorizarlos. Incluir solo los que cambiarían el análisis si se resuelven.

**Paso 8 — Bloque 6: Factores de ejecución.**
Usar `bloque_6_anclas` del market agent si existe. Completar:
- `inversion`: costos conocidos + comparables. Si no → "a estimar con [fuente/experto]"
- `tiempo_a_mercado`: anclado en comparables reales. NUNCA un número tuyo.
  Si no hay comparable → {"valor": "a juicio humano", "estado": "a-confirmar"}
- `capacidades`: qué se requiere vs qué hay disponible (CONICET/red/socios/equipo)
- `regulatorio`: encuadre aplicable + anclas históricas. Plazo = incógnita conocida.

**Paso 9 — Escribir el `resumen_markdown` (el expediente completo).**

El `resumen_markdown` NO es un resumen. Es el documento completo que Sebas va a leer para
tomar la decisión de invertir y luego salir a validar con profesionales. Tiene que tener
profundidad real — 5 a 10 páginas de markdown rico.

**Regla absoluta:** si tenés el informe completo de un agente, lo reproducís íntegramente
como sección del expediente. No lo resumís. No lo sintetizás en 3 líneas. Lo incluís entero.
El expediente vale por su profundidad, no por su brevedad.

Estructura del `resumen_markdown`:

```
# EXPEDIENTE DE DECISIÓN — [Nombre]
[Fecha] | Madurez: [nivel] | Confianza: [índice]

## RESUMEN EJECUTIVO
[2-3 párrafos: tesis, estado actual de la oportunidad, decisión que se le pide a Sebas.
Para quien tiene 2 minutos. Solo esto es un resumen — el resto es el análisis completo.]

## ANÁLISIS DE DEMANDA
[Reproducí íntegramente el análisis de demanda del Agente de Mercado. Todo: datos de
SENASA, series consultadas, papeles del corpus, razonamiento completo, fuentes usadas.
Nada omitido. Si el informe completo está disponible, lo copiás tal cual en esta sección.]

## ANÁLISIS DE COMPETENCIA
[Reproducí íntegramente el análisis competitivo. Jugadores con todos sus detalles, estado
de patentes con fuentes, análisis de intensidad, barreras de entrada. Todo, sin abreviar.]

## VIABILIDAD EN CONTEXTO
[Reproducí íntegramente: encuadre regulatorio completo, acceso a mercado, estimaciones
de costo, canales de distribución. Si hay anclas de ejecución, incluirlas aquí también.]

## EVALUACIÓN TÉCNICA / CIENTÍFICA
[Si hay informe del Agente de Evidencia: reproducirlo íntegramente.]
[Si no hay: "No investigado. Agente de Evidencia Científica pendiente (SEB-149).
Gaps que hay que cerrar antes de decidir:
- [Listar qué información técnica se necesita saber]
- [A quién preguntarle: científico CONICET, INTA Castelar, etc.]"]

## MAPA DE CONFIANZA
[Lista completa: qué está verificado (con fuente), qué es supuesto (con peso asignado),
qué falta confirmar (con dónde y quién). Índice de confianza global: alto/medio/bajo.]

## PRÓXIMOS PASOS POR AUDIENCIA
[Para cada tipo de profesional con quien Sebas va a hablar:]

**Para el científico/tecnólogo:**
[Preguntas concretas a hacer. Qué necesita validar técnicamente. Qué asumir hasta entonces.]

**Para el experto de mercado:**
[Qué validar sobre el tamaño real, quién lo sufre, canales. Qué está asumido en el análisis.]

**Para el abogado de PI / regulatorio:**
[Qué revisar: encuadre SENASA, estado de patentes (Novozymes, etc.), plazos reales actuales.]

**Para un potencial inversor / socio estratégico:**
[Qué mostrarle. Cuál es el pitch con los datos actuales. Qué preguntas esperarse.]

## FACTORES DE EJECUCIÓN
[Inversión: rangos con fuente y comparables. Sin números del modelo.
Regulatorio: encuadre + plazos históricos reales (no proyecciones).
Capacidades: mapa completo de lo que se requiere vs lo que hay disponible.
Timing: anclas reales disponibles, sin timelines inventados.]
```

**Paso 10 — Llamar a `submit_expediente`.**
SIEMPRE como último paso. Con el expediente completo (incluyendo el `resumen_markdown` rico
que escribiste en el Paso 9). No te detengas antes de llamarlo.

### Regla de veracidad (no negociable)
Cada dato lleva: `establecido` (con fuente) | `asumido` (con peso) | `a-confirmar` (con dónde).
Gap declarado > inferencia disfrazada de hecho. Nunca un número sin fuente.
"""
)

# ──────────────────────────────────────────────
# TOOLS
# ──────────────────────────────────────────────

TOOLS = [
    {
        "name": "submit_expediente",
        "description": (
            "Registra el expediente de decisión completo. "
            "LLAMAR SIEMPRE como último paso. "
            "Captura el output estructurado para KM write-back e informe markdown."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "bloque_1": {
                    "type": "object",
                    "description": "Tesis + puerta de entrada",
                    "properties": {
                        "tesis": {"type": "string", "description": "1-2 frases: qué, para quién, por qué ahora"},
                        "puerta_de_entrada": {
                            "type": "string",
                            "enum": ["sector", "dolor", "tecnologia", "planta-recurso", "necesidad-empresario"],
                        },
                        "disparador": {"type": "string", "description": "El input concreto que originó la oportunidad"},
                        "oportunidad_nombre": {"type": "string"},
                    },
                    "required": ["tesis", "puerta_de_entrada", "oportunidad_nombre"],
                },
                "bloque_2": {
                    "type": "object",
                    "description": "Los 4 cruces del blue ocean (con estados por campo)",
                    "properties": {
                        "cruce_1": {"type": "object", "description": "Demanda: dolor, quién, tamaño, urgencia, evidencia"},
                        "cruce_2": {"type": "object", "description": "Capacidad/Tecnología: solución, factibilidad, estado desarrollo, ventaja, evidencia"},
                        "cruce_3": {"type": "object", "description": "Competencia: qué existe, registros, intensidad, evidencia"},
                        "cruce_4": {"type": "object", "description": "Viabilidad en contexto: regulatorio, accesibilidad, factibilidad de costo, evidencia"},
                    },
                    "required": ["cruce_1", "cruce_2", "cruce_3", "cruce_4"],
                },
                "bloque_3": {
                    "type": "object",
                    "description": "Mapa de confianza — síntesis transversal de estados",
                    "properties": {
                        "establecidos": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Lista de datos con estado=establecido (con su fuente)",
                        },
                        "asumidos": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "dato": {"type": "string"},
                                    "peso": {"type": "string", "enum": ["alto", "medio", "bajo"]},
                                },
                                "required": ["dato", "peso"],
                            },
                        },
                        "a_confirmar": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "dato": {"type": "string"},
                                    "donde_confirmar": {"type": "string"},
                                    "impacto_en_decision": {"type": "string", "enum": ["alto", "medio", "bajo"]},
                                },
                                "required": ["dato", "donde_confirmar", "impacto_en_decision"],
                            },
                        },
                        "indice_confianza": {
                            "type": "string",
                            "enum": ["alto", "medio", "bajo"],
                        },
                        "cobertura_global": {
                            "type": "string",
                            "enum": ["alto", "medio", "bajo"],
                            "description": (
                                "Calculado por el Armador a partir de fuentes_y_cobertura de mercado/evidencia — "
                                "no lo completes vos, se sobrescribe automáticamente. Distinto de indice_confianza: "
                                "esto es cobertura de fuentes, no confianza por dato."
                            ),
                        },
                    },
                    "required": ["establecidos", "asumidos", "a_confirmar", "indice_confianza"],
                },
                "bloque_4": {
                    "type": "object",
                    "description": "Nivel de madurez de la oportunidad",
                    "properties": {
                        "nivel": {
                            "type": "string",
                            "enum": ["hipotesis_de_screening", "parcialmente_validado", "listo_para_decision"],
                        },
                        "justificacion": {"type": "string"},
                    },
                    "required": ["nivel", "justificacion"],
                },
                "bloque_5": {
                    "type": "object",
                    "description": "Qué falta para decidir — gaps priorizados",
                    "properties": {
                        "gaps": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "descripcion": {"type": "string"},
                                    "como_confirmar": {"type": "string"},
                                    "quien_o_fuente": {"type": "string"},
                                    "prioridad": {"type": "string", "enum": ["alta", "media", "baja"]},
                                },
                                "required": ["descripcion", "como_confirmar", "prioridad"],
                            },
                        }
                    },
                    "required": ["gaps"],
                },
                "bloque_6": {
                    "type": "object",
                    "description": "Factores de ejecución — sin timelines del modelo",
                    "properties": {
                        "inversion": {"type": "object"},
                        "tiempo_a_mercado": {"type": "object"},
                        "capacidades": {"type": "object"},
                        "regulatorio": {"type": "object"},
                    },
                    "required": ["inversion", "tiempo_a_mercado", "capacidades", "regulatorio"],
                },
                "trazabilidad": {
                    "type": "object",
                    "properties": {
                        "agentes_que_contribuyeron": {"type": "array", "items": {"type": "string"}},
                        "fuentes_usadas": {"type": "array", "items": {"type": "string"}},
                        "fecha": {"type": "string"},
                    },
                    "required": ["agentes_que_contribuyeron", "fecha"],
                },
                "resumen_markdown": {
                    "type": "string",
                    "description": (
                        "El expediente completo en markdown rico (5-10 páginas). "
                        "NO es un resumen — incluye TODO el análisis de cada agente sin abreviar. "
                        "Estructura: RESUMEN EJECUTIVO (único bloque breve) + ANÁLISIS DE DEMANDA "
                        "(informe completo del market agent) + ANÁLISIS DE COMPETENCIA + "
                        "VIABILIDAD EN CONTEXTO + EVALUACIÓN TÉCNICA/CIENTÍFICA + "
                        "MAPA DE CONFIANZA + PRÓXIMOS PASOS POR AUDIENCIA + FACTORES DE EJECUCIÓN."
                    ),
                },
                "lecciones_caso": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lecciones aprendidas de este caso para guardar_leccion_caso()",
                },
            },
            "required": [
                "bloque_1", "bloque_2", "bloque_3", "bloque_4",
                "bloque_5", "bloque_6", "trazabilidad", "resumen_markdown",
            ],
        },
    }
]

# ──────────────────────────────────────────────
# INPUT BUILDER
# ──────────────────────────────────────────────


def build_input(oportunidad_id: str, oportunidad: dict) -> str:
    props = oportunidad.get("props") or {}

    # nombre/descripcion pueden estar al top level (casos de test) o dentro de props (KM real)
    nombre = (
        oportunidad.get("nombre")
        or props.get("nombre")
        or (oportunidad.get("texto", "") or "")[:80]
    )
    descripcion = (
        oportunidad.get("descripcion")
        or props.get("descripcion")
        or oportunidad.get("texto", "")
    )

    # Separar el informe narrativo de los datos estructurados del market agent
    mercado_raw = dict(props.get("mercado") or {})
    mercado_informe = mercado_raw.pop("informe_completo", "")
    mercado_datos = mercado_raw  # datos estructurados sin el informe

    # Idem para evidencia
    evidencia_raw = dict(props.get("evidencia") or {})
    evidencia_informe = evidencia_raw.pop("informe_completo", "")
    evidencia_datos = evidencia_raw

    lines = [
        "## Oportunidad a armar",
        f"**Nombre:** {nombre}",
        f"**ID:** {oportunidad_id}",
        f"**Descripción:** {descripcion}",
        "",
        "---",
        "",
        "## Informe completo del Agente de Mercado",
        "(Incluir ÍNTEGRAMENTE en el expediente — no resumir)",
        "",
    ]

    if mercado_informe:
        lines.append(mercado_informe)
    elif mercado_datos:
        lines += [
            "[Informe narrativo no disponible — se incluyen solo datos estructurados]",
            "",
            json.dumps(mercado_datos, ensure_ascii=False, indent=2),
        ]
    else:
        lines.append("[NO DISPONIBLE — Market Agent no corrió sobre esta oportunidad]")

    if mercado_datos and mercado_informe:
        lines += [
            "",
            "---",
            "",
            "## Datos estructurados del Agente de Mercado (cruces 1/3/4 + bloque_6_anclas)",
            "(Usar para completar bloque_2 de submit_expediente)",
            "",
            json.dumps(mercado_datos, ensure_ascii=False, indent=2),
        ]

    lines += [
        "",
        "---",
        "",
        "## Informe completo del Agente de Evidencia Científica (cruce 2)",
        "",
    ]

    if evidencia_informe:
        lines.append(evidencia_informe)
        if evidencia_datos:
            lines += [
                "",
                "### Datos estructurados de evidencia",
                json.dumps(evidencia_datos, ensure_ascii=False, indent=2),
            ]
    elif evidencia_datos:
        lines += [
            "[Informe narrativo no disponible — se incluyen solo datos estructurados]",
            "",
            json.dumps(evidencia_datos, ensure_ascii=False, indent=2),
        ]
    else:
        lines.append(
            "[NO DISPONIBLE — Evidence Agent pendiente (SEB-149). "
            "Completar cruce_2 con estado a-confirmar en todos los campos.]"
        )

    otras_props = {k: v for k, v in props.items() if k not in ("mercado", "evidencia")}
    if otras_props:
        lines += [
            "",
            "---",
            "",
            "## Contexto adicional del KM",
            json.dumps(otras_props, ensure_ascii=False, indent=2),
        ]

    return "\n".join(lines)


# ──────────────────────────────────────────────
# AGENTIC LOOP
# ──────────────────────────────────────────────


async def run_agent(
    oportunidad_id: str | None,
    oportunidad_dict: dict | None = None,
    model: str = DEFAULT_MODEL,
    verbose: bool = True,
) -> tuple[str, dict, list[str]]:
    """
    Corre el Armador. Devuelve (resumen_markdown, expediente_dict, lecciones_auto).

    Si oportunidad_id se provee → lee del KM.
    Si oportunidad_dict se provee → lo usa directamente (testing sin KM).
    """
    client = anthropic.Anthropic()

    if verbose:
        print(f"\n{'='*60}\n  ARMADOR DEL EXPEDIENTE — CRIZA\n  Modelo: {model}\n{'='*60}\n")

    if oportunidad_dict is None:
        if oportunidad_id is None:
            raise ValueError("Se requiere oportunidad_id o oportunidad_dict")
        oportunidad_dict = await motor_api.obtener(oportunidad_id, tenant="criza")
        if not oportunidad_dict:
            raise ValueError(f"Oportunidad {oportunidad_id} no encontrada en el KM")

    # Validación de cobertura aguas arriba (el armador no tiene fuentes propias — ver
    # orchestration-layer.md Decisión 6). Sin mercado no hay nada que ensamblar.
    props = oportunidad_dict.get("props") or {}
    cobertura_check = _validar_cobertura_upstream(props)
    if verbose:
        for adv in cobertura_check.advertencias:
            print(f"  ⚠️  {adv}")
    if not cobertura_check.ok:
        raise RuntimeError(
            "Validación de cobertura bloqueante — Armador no puede ensamblar:\n"
            + "\n".join(cobertura_check.bloqueantes)
        )

    lecciones_prompt = await aprendizaje.bloque_lecciones_para_prompt(agente="armador", tenant="criza")

    user_input = build_input(oportunidad_id or "test", oportunidad_dict)
    if lecciones_prompt:
        user_input = lecciones_prompt + "\n\n---\n\n" + user_input

    messages = [{"role": "user", "content": user_input}]
    expediente_result: dict | None = None
    tracker = TokenTracker(agent="armador", oportunidad_id=oportunidad_id or "test", model=model)

    # Prompt caching — ver market_agent.py. SYSTEM_PROMPT acá es 100% estático (carga
    # expediente_decision_SPEC.md, sin lecciones inyectadas — esas van al user_input),
    # así que además del ahorro dentro del loop, cachea entre corridas distintas.
    system_blocks = [{
        "type": "text",
        "text": SYSTEM_PROMPT,
        "cache_control": {"type": "ephemeral"},
    }]

    while True:
        for attempt in range(5):
            try:
                with client.messages.stream(
                    model=model,
                    max_tokens=MAX_TOKENS,
                    system=system_blocks,
                    tools=TOOLS,
                    messages=messages,
                ) as stream:
                    resp = stream.get_final_message()
                break
            except anthropic.RateLimitError:
                if attempt == 4:
                    raise
                wait = min(30 * (attempt + 1), 90)
                if verbose:
                    print(f"  [rate limit — espero {wait}s]")
                time.sleep(wait)

        messages.append({"role": "assistant", "content": resp.content})
        tracker.add(resp.usage)

        if verbose:
            print(
                f"  [{tracker.calls}] stop={resp.stop_reason} | "
                f"tokens in={resp.usage.input_tokens} out={resp.usage.output_tokens}"
            )

        # max_tokens NO es terminación normal. Va ANTES de procesar los bloques:
        # un `submit_expediente` que viene en una respuesta truncada trae el JSON
        # cortado, y más abajo `expediente_result is not None` lo daría por bueno
        # (fue exactamente lo que pasó: stop=max_tokens + "expediente capturado",
        # y el expediente salió vacío con nivel_confianza "alto").
        # Un resultado capturado en un turno ANTERIOR sí es válido — de ahí el `is None`.
        if resp.stop_reason == "max_tokens" and expediente_result is None:
            raise RuntimeError(
                f"Respuesta truncada por max_tokens (MAX_TOKENS={MAX_TOKENS}, "
                f"output={resp.usage.output_tokens}) antes de completar submit_expediente. "
                "El expediente está incompleto — no se entrega."
            )

        tool_results = []
        for block in resp.content:
            if block.type == "tool_use":
                if block.name == "submit_expediente":
                    expediente_result = block.input
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps({"success": True, "message": "Expediente registrado."}),
                    })
                    if verbose:
                        print("  -> submit_expediente: expediente capturado")
                else:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps({"error": f"Tool no disponible en el Armador: {block.name}"}),
                    })

        if expediente_result is not None:
            break

        if resp.stop_reason in ("end_turn", "max_tokens"):
            break

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

    tracker.log(verbose)
    if oportunidad_id:
        existing = (oportunidad_dict.get("props") or {}).get("token_usage") or {}
        existing["armador"] = tracker.to_dict()
        await motor_api.actualizar_props(oportunidad_id, {"token_usage": existing}, tenant="criza")

    if expediente_result is None:
        raw = "".join(b.text for b in resp.content if hasattr(b, "text"))
        return raw or "El agente no llamó submit_expediente.", {}, []

    # cobertura_global se calcula, no se confía en que el modelo lo autoreporte bien
    # (veracidad por dato — establecido > asumido).
    expediente_result.setdefault("bloque_3", {})["cobertura_global"] = _derive_cobertura_global(props)

    resumen = expediente_result.get("resumen_markdown", "")
    lecciones_auto = expediente_result.get("lecciones_caso") or []

    return resumen, expediente_result, lecciones_auto


# ── Contrato estándar (SEB-115) ───────────────────────────────────────────────

async def run(
    contract_input: dict,
    verbose: bool = False,
    model: str = DEFAULT_MODEL,
) -> dict:
    """Interfaz de contrato estándar para el Orquestador (SEB-115)."""
    conocimiento = contract_input.get("conocimiento") or {}
    oportunidad_id = conocimiento.get("oportunidad_id") if isinstance(conocimiento, dict) else None

    if not oportunidad_id:
        raise ValueError("Armador requiere 'oportunidad_id' en contract_input.conocimiento")

    resumen, expediente, lecciones = await run_agent(
        oportunidad_id=oportunidad_id,
        model=model,
        verbose=verbose,
    )

    return {
        "análisis": {
            "expediente": resumen,  # _extract_expediente en motor.py lee análisis.expediente
            "resultado": expediente,
        },
        "nivel_confianza": _derive_nivel_confianza(expediente.get("bloque_3") or {}),
        "recomendaciones": [],
        "próximo_agente": None,
        "nuevo_conocimiento": lecciones,
    }
