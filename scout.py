"""
Scout Científico Multidominio — CRIZA / EMPRESAS-IA
Agente de primer filtro: barre el universo de productos posibles y devuelve
candidatos rankeados con tag de dominio. NO decide quién los analiza después
— eso es responsabilidad del Orquestador (o del usuario por ahora).

Diseño intencional:
- Solo usa search_literature (OpenAlex). Sin herramientas pesadas = barato en tokens.
- No tiene sesgo de dominio: proteínas, moléculas pequeñas, metabolitos, materiales, etc.
- Modelo configurable (default: claude-sonnet-4-6). El especialista profundo usa Opus.
- Output estructurado: candidatos rankeados + tag_dominio + rationale + confianza.
- Sigue la FORMA del contrato estándar de agentes (SEB-115) sin hardcodear routing.
"""

import json
import os
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=True)

import anthropic
from tools import search_literature

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────

DEFAULT_MODEL = os.getenv("SCOUT_MODEL", "claude-sonnet-4-6")

# ──────────────────────────────────────────────
# TOOLS (solo búsqueda de literatura)
# ──────────────────────────────────────────────

TOOLS = [
    {
        "name": "search_literature",
        "description": (
            "Search scientific literature via OpenAlex (250M+ papers, all domains).\n"
            "Use for:\n"
            "- Identifying biotechnology products with commercial potential\n"
            "- Market signals: price, demand, production challenges\n"
            "- Production feasibility via microbial fermentation\n"
            "- Pain points in target industries\n"
            "Always search in English. Run multiple searches with different angles.\n"
            "Use max_results=8 to keep context manageable."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Search query in English. Examples:\n"
                        "- 'high value fermentation products animal feed market'\n"
                        "- 'biosurfactants microbial production cost industrial'\n"
                        "- 'carotenoids fermentation Escherichia yeast commercial'\n"
                        "Be specific about domain, application, and production angle."
                    ),
                },
                "max_results": {
                    "type": "integer",
                    "description": "Results to fetch (default 8, max 15 for scouting)",
                    "default": 8,
                },
            },
            "required": ["query"],
        },
    },
]

# ──────────────────────────────────────────────
# SYSTEM PROMPT
# ──────────────────────────────────────────────

SYSTEM_PROMPT = """Sos el Scout Científico de CRIZA, especializado en identificar oportunidades de producto
en TODO el universo de la biotecnología y la química aplicada — sin sesgo de dominio.

Tu trabajo es el PRIMER FILTRO del pipeline de análisis. De tu calidad depende todo lo que viene después:
pocos candidatos fuertes y bien fundados valen mucho más que una lista larga de candidatos débiles.
Filtrás señal de ruido. Sos exigente con los criterios.

DOMINIOS QUE EXPLORÁS (no te limitás a ninguno):
• Proteínas y enzimas (industriales, alimentarias, farmacéuticas)
• Moléculas pequeñas (ácidos orgánicos, solventes, precursores)
• Metabolitos y compuestos bioactivos (bacteriocinas, péptidos, pigmentos, vitaminas)
• Materiales de base biológica (biopolímeros, biosurfactantes, biomateriales)
• Ingredientes funcionales para alimentos, feed, cosmética, agricultura
• Cualquier otro producto que pueda producirse por fermentación microbiana

CRITERIOS DE OPORTUNIDAD — solo pasan candidatos que cumplan la mayoría:
1. Mercado grande y establecido — hay demanda real, no especulativa
2. Se usa en pequeñas cantidades con alto impacto en el producto final
3. Actualmente caro de producir o con limitaciones de abastecimiento
4. La biotecnología / fermentación microbiana puede mejorar costo, rendimiento o disponibilidad
5. Hay un dolor concreto en la industria destino (calidad, costo, consistencia, regulación)
6. Viable por fermentación en escala media (fermentadores ~500L, 28-32°C, pH 5.5-7.0)

WORKFLOW OBLIGATORIO:
1. Planificá 4-6 búsquedas con ángulos distintos antes de arrancar
   (no repetir el mismo concepto, explorar dominios diferentes)
2. Ejecutá las búsquedas con max_results=8 para no saturar el contexto
3. Analizá los resultados con los criterios de oportunidad
4. Descartá explícitamente lo que no cumple — justificá el descarte
5. Rankeá los candidatos que pasan el filtro (máximo 8, mínimo 3)

NIVEL DE CONFIANZA (obligatorio por afirmación):
[LIT] = respaldado por literatura encontrada en esta sesión
[EST] = estimación razonada basada en principios conocidos
[INC] = incierto — requiere más investigación

TAG DE DOMINIO (obligatorio por candidato):
• proteina — proteínas, enzimas (requiere especialista de proteínas para deep-dive)
• molecula_pequeña — compuestos orgánicos, ácidos, solventes
• metabolito — péptidos bioactivos, pigmentos, vitaminas, bacteriocinas
• material — biopolímeros, biosurfactantes, biomateriales
• otro — si no encaja en los anteriores

OUTPUT REQUERIDO — seguí exactamente esta estructura:

## Resumen ejecutivo del scouting
[2-3 párrafos: contexto del barrido, criterios aplicados, cuántas búsquedas]

## Candidatos rankeados

Para cada candidato (del más al menos prometedor):

### [N]. [NOMBRE DEL CANDIDATO]
**Tag de dominio:** [tag]
**Score de oportunidad:** [X/10]
**Dolor que resuelve:** [qué problema concreto tiene la industria hoy]
**Industria destino:** [quién lo compra, B2B]
**Por qué la biotecnología gana acá:** [qué ventaja da sobre la producción actual]
**Señal de mercado:** [precio, volumen, tendencia — con nivel de confianza]
**Viabilidad de fermentación:** [factibilidad técnica en el setup disponible]
**Nivel de confianza global:** [LIT/EST/INC]
**Qué necesita para el deep-dive:** [qué tipo de análisis profundo requiere — sin decir quién lo hace]
**Referencias:** [papers encontrados, con DOI si disponible]

## Candidatos descartados
[lista de lo que se encontró pero no pasó los criterios, con una línea de por qué]

## Ángulos no explorados
[qué dominios o aplicaciones quedaron fuera de este scouting y podrían valer la pena]

## Gaps y limitaciones
[qué no se pudo determinar solo con literatura]

Sé riguroso. Citá siempre las fuentes. Preferí NO incluir un candidato antes de incluir uno débil.
"""

# ──────────────────────────────────────────────
# TOOL DISPATCHER
# ──────────────────────────────────────────────

def dispatch_tool(name: str, inputs: dict) -> str:
    if name == "search_literature":
        result = search_literature(inputs["query"], inputs.get("max_results", 8))
    else:
        result = {"error": f"Tool not available in scout: {name}"}
    return json.dumps(result, ensure_ascii=False, indent=2)


# ──────────────────────────────────────────────
# AGENTIC LOOP
# ──────────────────────────────────────────────

def run_scout(
    user_input: str,
    model: str = DEFAULT_MODEL,
    verbose: bool = True,
) -> str:
    """
    Corre el Scout Científico Multidominio.

    Args:
        user_input: Descripción del objetivo del scouting (sector, criterios, contexto)
        model: Modelo de Claude a usar (default: SCOUT_MODEL de .env o claude-sonnet-4-6)
        verbose: Muestra tool calls en consola

    Returns:
        Informe de scouting estructurado con candidatos rankeados y tags de dominio
    """
    client = anthropic.Anthropic()

    if verbose:
        print("\n" + "=" * 60)
        print(f"  SCOUT CIENTIFICO MULTIDOMINIO — CRIZA")
        print(f"  Modelo: {model}")
        print("=" * 60 + "\n")

    messages = [{"role": "user", "content": user_input}]

    while True:
        # Retry con backoff ante rate limit de Anthropic
        for attempt in range(4):
            try:
                response = client.messages.create(
                    model=model,
                    max_tokens=8000,
                    system=SYSTEM_PROMPT,
                    tools=TOOLS,
                    messages=messages,
                )
                break
            except anthropic.RateLimitError:
                if attempt == 3:
                    raise
                wait = 20 * (attempt + 1)
                if verbose:
                    print(f"  [rate limit — esperando {wait}s...]\n")
                time.sleep(wait)

        messages.append({"role": "assistant", "content": response.content})

        # Respuesta final
        if response.stop_reason in ("end_turn", "max_tokens"):
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return "Scouting completado sin texto."

        # Tool calls
        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    if verbose:
                        print(f"-> {block.name}")
                        preview = json.dumps(block.input, ensure_ascii=False)
                        print(f"  {preview[:120]}{'...' if len(preview) > 120 else ''}")

                    result_str = dispatch_tool(block.name, block.input)

                    if verbose:
                        print(f"  done\n")

                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": block.id,
                        "content":     result_str,
                    })

            messages.append({"role": "user", "content": tool_results})
        else:
            break

    return "Scout interrumpido inesperadamente."
