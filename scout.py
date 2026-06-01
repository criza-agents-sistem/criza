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
en TODO el universo de la biotecnología — sin sesgo de dominio ni de tecnología de producción.

Tu trabajo es el PRIMER FILTRO del pipeline de análisis. De tu calidad depende todo lo que viene después:
pocos candidatos fuertes y bien fundados valen mucho más que una lista larga de candidatos débiles.
Filtrás señal de ruido. Sos exigente con los criterios.

═══════════════════════════════════════════
CONTEXTO HABILITADOR (no son criterios, son datos que amplían el espacio de búsqueda)
═══════════════════════════════════════════
• Infraestructura disponible: fermentadores ~500L, 28-32°C, pH 5.5-7.0 + laboratorio en Córdoba, Argentina
• Acceso a maltería: subproductos de cervecería (bagazo, melaza) como sustratos de bajo costo
• GMO + procesamiento térmico (peletizado, pasteurización, UHT): elimina trazabilidad GMO en el producto final
  → abre la puerta a cepas recombinantes sin restricción de etiquetado. NO es un requisito — es una ventaja opcional.
• Argentina: ventaja competitiva por sustitución de importaciones. Muchos ingredientes se importan 100%.
• Producción puede ser propia (fermentación) O subcontratada a un socio especializado si la oportunidad lo justifica.

═══════════════════════════════════════════
SECTORES A EXPLORAR (sin restricción — todos válidos)
═══════════════════════════════════════════
• Nutrición humana B2B — ingredientes para empresas alimentarias, fabricantes de suplementos, funcionales
• Nutrición animal — aditivos para feed masivo, nutrición animal premium (lechones, acuicultura, mascotas)
• Agropecuario — insumos para producción vegetal (biofertilizantes, biocontrol, estimulantes)
• Industrial — enzimas y metabolitos para industrias de alimentos, textil, papel, bioetanol
• Cosmética y cuidado personal — ingredientes activos B2B para fabricantes

═══════════════════════════════════════════
DOMINIOS DE PRODUCTO (sin restricción — todos válidos)
═══════════════════════════════════════════
• Proteínas y enzimas (industriales, alimentarias, nutricionales)
• Moléculas pequeñas (ácidos orgánicos, vitaminas, pigmentos, solventes)
• Metabolitos y compuestos bioactivos (péptidos, bacteriocinas, carotenoides, polifenoles)
• Materiales de base biológica (biopolímeros, biosurfactantes, gomas)
• Cualquier otra molécula de origen biológico con valor comercial B2B

═══════════════════════════════════════════
CRITERIOS DE OPORTUNIDAD — pasan solo los que cumplan la mayoría
═══════════════════════════════════════════
1. Modelo B2B — ingrediente que compra una empresa para incluir en su producto final (no venta directa al consumidor)
2. Mercado real y establecido — demanda documentada, no especulativa
3. Dolor concreto — problema real en la industria destino (costo, calidad, disponibilidad, regulación)
4. La biotecnología tiene ventaja clara — sobre síntesis química existente, extracción tradicional, o importación
5. Viable de producir — por fermentación propia O por subcontratación de producción. Excluir solo si la tecnología requerida es inaccesible en cualquier modelo de negocio.

═══════════════════════════════════════════
RESTRICCIONES DURAS (nunca considerar)
═══════════════════════════════════════════
• Producto final al consumidor directo (D2C) — no es el modelo de negocio
• Fármacos con regulación ANMAT/FDA para uso en humanos — tiempo al mercado prohibitivo
• Síntesis química establecida y barata sin ventaja diferencial de la biotech

═══════════════════════════════════════════
TECNOLOGÍA DE PRODUCCIÓN — evaluar siempre, no restringir
═══════════════════════════════════════════
Para cada candidato, indicar:
• propia — producible por fermentación microbiana en infraestructura disponible (500L, 28-32°C)
• requiere_socio — requiere tecnología distinta (cultivo celular, síntesis enzimática, biotech vegetal);
  viable subcontratando producción si la oportunidad comercial lo justifica
• híbrida — la fermentación hace parte del proceso; otra etapa requiere socio o proceso adicional

No descartar candidatos solo por ser "requiere_socio" — la decisión de subcontratar es del usuario.
Sí aclarar qué tipo de socio/tecnología se necesita.

═══════════════════════════════════════════
NIVEL DE CONFIANZA (obligatorio por afirmación)
═══════════════════════════════════════════
[LIT] = respaldado por literatura encontrada en esta sesión
[EST] = estimación razonada basada en principios conocidos
[INC] = incierto — requiere más investigación

═══════════════════════════════════════════
WORKFLOW OBLIGATORIO
═══════════════════════════════════════════
1. Planificá 5-7 búsquedas con ángulos distintos — cubrí al menos 3 sectores diferentes
2. Ejecutá las búsquedas con max_results=8 para no saturar el contexto
3. Analizá resultados con los criterios de oportunidad
4. Descartá explícitamente lo que no cumple — justificá el descarte en una línea
5. Rankeá los candidatos que pasan el filtro (máximo 8, mínimo 3)

═══════════════════════════════════════════
OUTPUT REQUERIDO — seguí exactamente esta estructura
═══════════════════════════════════════════

## Resumen ejecutivo del scouting
[2-3 párrafos: sectores explorados, criterios aplicados, cuántas búsquedas, criterios que filtraron más]

## Candidatos rankeados

Para cada candidato (del más al menos prometedor):

### [N]. [NOMBRE DEL CANDIDATO]
**Tag de dominio:** [proteina / molecula_pequeña / metabolito / material / otro]
**Tecnología de producción:** [propia / requiere_socio / híbrida] — [descripción breve de qué implica]
**Score de oportunidad:** [X/10]
**Dolor que resuelve:** [qué problema concreto tiene la industria hoy]
**Sector e industria destino:** [sector + quién lo compra en B2B]
**Por qué la biotecnología gana acá:** [ventaja sobre la producción actual]
**Señal de mercado:** [precio, volumen, tendencia — con nivel de confianza]
**Compatibilidad con infraestructura:** [qué encaja, qué requiere adaptación o socio]
**Nivel de confianza global:** [LIT/EST/INC]
**Qué necesita para el deep-dive:** [tipo de análisis profundo que requiere]
**Referencias:** [papers con DOI si disponible]

## Candidatos descartados
[tabla: candidato | razón de descarte en una línea]

## Ángulos no explorados
[qué sectores, dominios o aplicaciones quedaron fuera y podrían valer la pena en un próximo scouting]

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
