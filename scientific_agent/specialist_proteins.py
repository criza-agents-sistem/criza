"""
Agente Científico CRIZA v1.4-0
Analiza viabilidad técnica de producir proteínas por fermentación microbiana
y diseña variantes termoestables para aplicaciones de procesamiento.

Changelog v1.4-0:
- SEB-79: predict_structure_local — ESMFold corriendo localmente via fair-esm.
  Sin límite de longitud, sin timeout, sin API externa.
  Requiere: pip install fair-esm torch + GPU recomendada (Lambda Labs A10).
  Fallback automático a predict_structure() (API, 200aa) si no está instalado.

Changelog v1.3-0:
- SEB-78: predict_tm_change — predicción de ΔΔG y ΔTm via FoldX
  (Schymkowitz et al., 2005). Requiere FOLDX_PATH en .env.

Changelog v1.2-0:
- SEB-77: design_variants_mpnn — diseño ML de variantes via ProteinMPNN
  (Dauparas et al., Science 2022). Requiere PROTEINMPNN_PATH en .env.

Changelog v1.4.1:
- Migración search_literature: Semantic Scholar → OpenAlex como fuente primaria.
  Semantic Scholar tenía rate limiting persistente que degradaba análisis silenciosamente.
  OpenAlex: 250M+ papers, 10 req/seg, sin API key, fallback automático a SS si falla.
  Archivo: tools/openalex.py (drop-in replacement — output idéntico).
  Tests: 110 pasando (15 nuevos unit + 8 integration para OpenAlex).

Changelog v1.1-0:
- Migración search_pubmed → search_literature (Semantic Scholar)
  200M+ papers, todos los dominios, sin API key requerida.
  Nota: reemplazado en v1.4.1 por OpenAlex por problemas de rate limiting.
"""

import json
import os
import time
from pathlib import Path
from dotenv import load_dotenv

# CRÍTICO: cargar .env ANTES de importar tools.
# esmfold_local.py lee ESMFOLD_POD_URL al nivel de módulo (al importar).
# Si load_dotenv corre después, la URL queda como "" para siempre.
load_dotenv(Path(__file__).parent / ".env", override=True)

import anthropic
from tools import (
    search_literature,
    get_protein_sequence,
    predict_structure,
    predict_structure_local,
    analyze_stability,
    design_variants,
    compare_variants,
    design_variants_mpnn,
    predict_tm_change,
)


client = anthropic.Anthropic()

# ──────────────────────────────────────────────
# TOOL DEFINITIONS
# ──────────────────────────────────────────────

TOOLS = [
    {
        "name": "search_literature",
        "description": (
            "Search scientific literature via Semantic Scholar (200M+ papers, all domains).\n"
            "Broader than PubMed — covers biotech, chemistry, materials, food science, etc.\n"
            "Use for:\n"
            "- Expression systems documented for the target protein\n"
            "- Fermentation conditions (temperature, pH, yield, inducer)\n"
            "- Host microorganism comparison studies\n"
            "- Scale-up challenges and solutions\n"
            "- Thermal stability data and thermostable variants\n"
            "- Market and economic context for target molecules\n"
            "Always search in English. Run multiple targeted searches with different angles."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Search query. Examples:\n"
                        "- 'lactoferrin recombinant expression Pichia pastoris yield'\n"
                        "- 'bovine lactoferrin thermal stability denaturation temperature'\n"
                        "- 'lactoferrin thermostable variant engineering'\n"
                        "- 'precision fermentation high value proteins market'"
                    ),
                },
                "max_results": {
                    "type": "integer",
                    "description": "Results to fetch (default 10, max 100)",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_protein_sequence",
        "description": (
            "Retrieve amino acid sequence and metadata from UniProt.\n"
            "Use after identifying the target protein from literature.\n"
            "Returns: sequence, length, organism, functional annotation, signal peptide info."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "protein_name": {
                    "type": "string",
                    "description": "Protein name (e.g., 'lactoferrin', 'bovine lactoferrin')",
                },
                "organism": {
                    "type": "string",
                    "description": "Organism in Latin (e.g., 'Bos taurus'). Optional.",
                },
            },
            "required": ["protein_name"],
        },
    },
    {
        "name": "predict_structure",
        "description": (
            "Predict protein 3D structure confidence using ESMFold.\n"
            "Use AFTER retrieving sequence from UniProt.\n"
            "Returns pLDDT score AND per-residue pLDDT list — needed for analyze_stability.\n"
            "Saves PDB file to disk — needed for design_variants.\n"
            "IMPORTANT: For proteins > 200 aa, pass only the first 200 aa of the sequence.\n"
            "Interpretation:\n"
            "  ≥ 90 → very high confidence, well-defined structure\n"
            "  70-90 → high confidence, reliable\n"
            "  50-70 → medium, flexible regions present\n"
            "  < 50  → low, likely disordered"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sequence": {
                    "type": "string",
                    "description": "Amino acid sequence (single-letter code, max 200 aa for API reliability)",
                },
                "protein_name": {
                    "type": "string",
                    "description": "Protein name for reference",
                },
            },
            "required": ["sequence", "protein_name"],
        },
    },
    {
        "name": "predict_structure_local",
        "description": (
            "Predict protein 3D structure using ESMFold running LOCALLY — no length limit.\n"
            "Use this INSTEAD OF predict_structure when analyzing proteins > 200 aa.\n"
            "Requires fair-esm + torch installed (GPU recommended: Lambda Labs A10).\n"
            "If not installed, returns structure_obtained=False with setup_instructions\n"
            "→ in that case, fall back to predict_structure() with first 200 aa.\n"
            "\n"
            "Key advantage: analyzes the FULL sequence (e.g., lactoferrin 708 aa).\n"
            "Output is identical to predict_structure() — compatible with all downstream tools.\n"
            "\n"
            "Speed (A10 GPU): ~30s per protein regardless of length.\n"
            "Speed (CPU): ~20-30 min for sequences > 400 aa.\n"
            "\n"
            "Interpretation:\n"
            "  ≥ 90 → very high confidence, well-defined structure\n"
            "  70-90 → high confidence, reliable\n"
            "  50-70 → medium, flexible regions present\n"
            "  < 50  → low, likely disordered"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sequence": {
                    "type": "string",
                    "description": "Full amino acid sequence — no truncation needed",
                },
                "protein_name": {
                    "type": "string",
                    "description": "Protein name for reference",
                },
            },
            "required": ["sequence", "protein_name"],
        },
    },
    {
        "name": "analyze_stability",
        "description": (
            "Identify thermally unstable regions in a protein using per-residue pLDDT scores.\n"
            "Use AFTER predict_structure — requires per_residue_plddt from that output.\n"
            "Returns:\n"
            "- Weak regions: stretches of low-confidence residues that unfold first under heat\n"
            "- Engineering strategies: specific mutations to improve thermostability at each region\n"
            "  (proline substitutions, disulfide bonds, salt bridges)\n"
            "- Recommended next step for design_variants"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sequence": {
                    "type": "string",
                    "description": "Amino acid sequence analyzed by ESMFold (same truncated version)",
                },
                "per_residue_plddt": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "Per-residue pLDDT scores from predict_structure output",
                },
                "protein_name": {
                    "type": "string",
                    "description": "Protein name for reference",
                },
                "avg_plddt": {
                    "type": "number",
                    "description": "Average pLDDT from predict_structure (optional)",
                },
            },
            "required": ["sequence", "per_residue_plddt", "protein_name"],
        },
    },
    {
        "name": "design_variants",
        "description": (
            "Design thermostable protein variants based on stability analysis.\n"
            "Use AFTER analyze_stability — requires weak_regions from that output.\n"
            "Applies validated thermostabilization strategies:\n"
            "- Proline substitutions in flexible loops (+1-3°C per substitution)\n"
            "- Consensus mutations replacing chemically unstable residues (+1-5°C)\n"
            "- Combined multi-mutation variants for additive stabilization (+3-8°C)\n"
            "Returns top N candidate sequences ready for ESMFold validation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sequence": {
                    "type": "string",
                    "description": "Full amino acid sequence of the wildtype protein",
                },
                "weak_regions": {
                    "type": "array",
                    "description": "Weak regions list from analyze_stability output",
                },
                "protein_name": {
                    "type": "string",
                    "description": "Protein name for reference",
                },
                "n_variants": {
                    "type": "integer",
                    "description": "Number of top variants to return (default 5)",
                    "default": 5,
                },
                "target_application": {
                    "type": "string",
                    "description": "Optional: 'cooking', 'pasteurization', 'supplement'. Guides strategy prioritization.",
                },
            },
            "required": ["sequence", "weak_regions", "protein_name"],
        },
    },
    {
        "name": "compare_variants",
        "description": (
            "Validate designed variants by comparing ESMFold pLDDT against wildtype.\n"
            "Use AFTER design_variants — the final computational validation step.\n"
            "Runs ESMFold on each variant and ranks by structural quality improvement.\n"
            "Returns: ranked variants, lab candidates, and experimental recommendations.\n"
            "NOTE: Each ESMFold call takes ~30-60s. Limit to top 3-5 variants."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "wildtype_sequence": {
                    "type": "string",
                    "description": "Original protein sequence",
                },
                "wildtype_plddt": {
                    "type": "number",
                    "description": "Average pLDDT of wildtype from predict_structure",
                },
                "variants": {
                    "type": "array",
                    "description": "Variants list from design_variants output (use 'variants' key)",
                },
                "protein_name": {
                    "type": "string",
                    "description": "Protein name for reference",
                },
                "max_variants": {
                    "type": "integer",
                    "description": "Maximum variants to test via ESMFold (default 5, max 5 for API limits)",
                    "default": 5,
                },
            },
            "required": ["wildtype_sequence", "wildtype_plddt", "variants", "protein_name"],
        },
    },
    {
        "name": "design_variants_mpnn",
        "description": (
            "Design protein sequence variants from structure using ProteinMPNN (ML-based).\n"
            "Use AFTER predict_structure — requires the pdb_path from that output.\n"
            "ProteinMPNN (Dauparas et al., Science 2022) generates sequences optimized\n"
            "for structural compatibility via a message-passing neural network.\n"
            "Unlike design_variants (rule-based), explores the full sequence space —\n"
            "may find non-obvious thermostabilizing mutations.\n"
            "\n"
            "REQUIRES: PROTEINMPNN_PATH set in .env + PyTorch installed.\n"
            "If not configured, returns setup instructions. Fallback: use design_variants.\n"
            "\n"
            "Workflow integration:\n"
            "  Option A (rule-based only): design_variants → compare_variants\n"
            "  Option B (ML-based only):   design_variants_mpnn → compare_variants\n"
            "  Option C (best coverage):   design_variants + design_variants_mpnn → compare_variants\n"
            "\n"
            "Temperature guide:\n"
            "  0.1 → conservative (close to native-like, high accuracy)\n"
            "  0.3 → balanced (recommended for exploration)\n"
            "  1.0 → maximum diversity (broad sequence space)"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pdb_path": {
                    "type": "string",
                    "description": "Path to PDB file from predict_structure output (use the 'pdb_path' field)",
                },
                "protein_name": {
                    "type": "string",
                    "description": "Protein name for reference",
                },
                "n_sequences": {
                    "type": "integer",
                    "description": "Number of sequences to generate (default 10, max 50)",
                    "default": 10,
                },
                "temperature": {
                    "type": "number",
                    "description": "Sampling temperature: 0.1 (conservative) to 1.0 (diverse). Default 0.1.",
                    "default": 0.1,
                },
            },
            "required": ["pdb_path", "protein_name"],
        },
    },
    {
        "name": "predict_tm_change",
        "description": (
            "Predict ΔΔG and estimate ΔTm for designed variants using FoldX.\n"
            "Use AFTER design_variants or design_variants_mpnn.\n"
            "FoldX computes the thermodynamic free energy change (ΔΔG, kcal/mol)\n"
            "when mutations are introduced — more precise than pLDDT delta alone.\n"
            "\n"
            "Output per variant:\n"
            "  - ΔΔG (kcal/mol): negative = stabilizing, positive = destabilizing\n"
            "  - ΔTm estimate (°C): ΔTm ≈ -ΔΔG × 1.7 (±1-2°C uncertainty)\n"
            "  - Absolute Tm estimate if wildtype_tm is provided\n"
            "\n"
            "REQUIRES: FOLDX_PATH set in .env (download from foldxsuite.biocomputing.eu).\n"
            "No GPU needed. CPU-only, runs in seconds per variant.\n"
            "If not configured, returns setup instructions. Fallback: compare_variants.\n"
            "\n"
            "Best practice: combine with compare_variants for orthogonal evidence:\n"
            "  - Variants with ΔΔG < -0.5 kcal/mol AND delta_pLDDT > 0 → top wet lab candidates\n"
            "  - Variants with contradictory signals → test experimentally, uncertain epistasis"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "wildtype_pdb": {
                    "type": "string",
                    "description": "Path to wildtype PDB file from predict_structure output (use 'pdb_path' field)",
                },
                "variants": {
                    "type": "array",
                    "description": "Variants list from design_variants or design_variants_mpnn (use 'variants' key). Each variant must have 'mutations' list.",
                },
                "protein_name": {
                    "type": "string",
                    "description": "Protein name for reference",
                },
                "wildtype_tm": {
                    "type": "number",
                    "description": "Known wildtype Tm from literature (°C). Optional — if provided, estimates absolute Tm for each variant.",
                },
            },
            "required": ["wildtype_pdb", "variants", "protein_name"],
        },
    },
]

# ──────────────────────────────────────────────
# SYSTEM PROMPT
# ──────────────────────────────────────────────

SYSTEM_PROMPT = """Sos el Agente Científico de CRIZA v1, especializado en biotecnología, producción de proteínas por fermentación microbiana e ingeniería de proteínas para aplicaciones industriales.

Tu misión: comprimir años de trabajo experimental en semanas de análisis computacional.
Analizás la viabilidad técnica de producir una proteína específica, evaluás su estabilidad térmica
y diseñás variantes mejoradas cuando la aplicación lo requiere.

CONTEXTO DEL PRODUCTOR (caso Andrés — Buenas Maltas):
• Fermentadores tipo cervecero, ~500 litros
• Temperatura operativa: 28–32°C
• Rango de pH: 5.5–7.0
• Experiencia: fermentación industrial (cerveza artesanal) — NO tiene capacidad de ingeniería genética
• Necesita: un socio científico que haya desarrollado el microorganismo a escala de laboratorio
• Restricción clave: preferir hosts GRAS (Generally Recognized As Safe) para uso alimentario

WORKFLOW OBLIGATORIO v1.1 — seguir este orden:
1. LITERATURE SCAN: mínimo 3 búsquedas en Semantic Scholar con queries distintos
   (sistemas de expresión, condiciones de fermentación, rendimientos, estabilidad térmica)
   Semantic Scholar cubre 200M+ papers — incluye biotech, química, ciencias de alimentos y más.
2. SEQUENCE: recuperar secuencia desde UniProt del candidato más prometedor
3. STRUCTURE: intentar predict_structure_local con la secuencia completa.
   Si retorna structure_obtained=False (fair-esm no instalado): usar predict_structure
   con solo los primeros 200 aa (límite confiable de la API pública).
   → guardar per_residue_plddt, avg_plddt y pdb_path para los siguientes pasos
   → si se usó predict_structure_local, indicarlo en el brief: "estructura analizada completa (Xaa)"
4. STABILITY: correr analyze_stability con la secuencia y per_residue_plddt de ESMFold
   → identifica regiones débiles y estrategias de ingeniería
5. VARIANTS: correr design_variants con la secuencia completa y las weak_regions
   → genera candidatas termoestables (rule-based: prolinas, consenso, combinadas)
   OPCIONAL: si PROTEINMPNN_PATH está configurado, correr también design_variants_mpnn
   con el pdb_path de ESMFold para candidatas ML-based adicionales.
   Si design_variants_mpnn falla por falta de setup, continuar con las rule-based.
6. TM PREDICTION (OPCIONAL): si FOLDX_PATH está configurado, correr predict_tm_change
   con el wildtype_pdb y las variantes diseñadas.
   → convierte estimaciones genéricas en ΔΔG específico por variante (kcal/mol) y ΔTm (°C)
   → usar wildtype_tm de literatura si está disponible para Tm absoluta estimada
   Si FoldX no está disponible, continuar con compare_variants como validación.
7. COMPARE: correr compare_variants con top 3-5 candidatas
   → valida estructuralmente (pLDDT delta). Combinar con FoldX ΔΔG si disponible.
   Candidatos ideales: ΔΔG < -0.5 kcal/mol Y delta_pLDDT > 0.
7. BRIEF: sintetizar el output final

OUTPUT REQUERIDO — brief técnico estructurado:

## Proteína analizada
[nombre, función, por qué es candidata]

## Sistema de expresión recomendado
[microorganismo host + justificación basada en literatura]

## Condiciones de fermentación
[temperatura, pH, medio de cultivo, inductor, tiempo de inducción]

## Compatibilidad con el setup de Andrés
[análisis honesto: qué encaja, qué requiere adaptación, qué es un riesgo real]

## Rendimiento esperado
[rango basado en literatura, en g/L o unidades relevantes]

## Análisis estructural y estabilidad térmica
[pLDDT wildtype, regiones débiles identificadas, Tm estimada de literatura]

## Variantes termoestables diseñadas
[top 3 candidatas con mutaciones, delta_plddt vs wildtype, delta_Tm esperado]

## Experimentos concretos para el laboratorio
[3–5 experimentos específicos y ordenados por prioridad, incluyendo validación de variantes]

## Limitaciones del análisis computacional
[qué NO puede predecirse sin wet lab — ser honesto]

## Fuentes
[Papers citados con título, año, DOI o URL — priorizá papers con open access PDF]

Sé riguroso. Citá siempre las fuentes. Si algo es incierto, decilo.
El objetivo es darle al laboratorio hipótesis ya filtradas, no respuestas definitivas."""


# ──────────────────────────────────────────────
# TOOL DISPATCHER
# ──────────────────────────────────────────────

def dispatch_tool(name: str, inputs: dict) -> str:
    if name == "search_literature":
        result = search_literature(inputs["query"], inputs.get("max_results", 10))
    elif name == "get_protein_sequence":
        result = get_protein_sequence(inputs["protein_name"], inputs.get("organism"))
    elif name == "predict_structure":
        result = predict_structure(inputs["sequence"], inputs["protein_name"])
    elif name == "predict_structure_local":
        result = predict_structure_local(inputs["sequence"], inputs["protein_name"])
    elif name == "analyze_stability":
        result = analyze_stability(
            sequence=inputs["sequence"],
            per_residue_plddt=inputs["per_residue_plddt"],
            protein_name=inputs["protein_name"],
            avg_plddt=inputs.get("avg_plddt"),
        )
    elif name == "design_variants":
        result = design_variants(
            sequence=inputs["sequence"],
            weak_regions=inputs["weak_regions"],
            protein_name=inputs["protein_name"],
            n_variants=inputs.get("n_variants", 5),
            target_application=inputs.get("target_application"),
        )
    elif name == "compare_variants":
        result = compare_variants(
            wildtype_sequence=inputs["wildtype_sequence"],
            wildtype_plddt=inputs["wildtype_plddt"],
            variants=inputs["variants"],
            protein_name=inputs["protein_name"],
            max_variants=inputs.get("max_variants", 5),
        )
    elif name == "design_variants_mpnn":
        result = design_variants_mpnn(
            pdb_path=inputs["pdb_path"],
            protein_name=inputs["protein_name"],
            n_sequences=inputs.get("n_sequences", 10),
            temperature=inputs.get("temperature", 0.1),
        )
    elif name == "predict_tm_change":
        result = predict_tm_change(
            wildtype_pdb=inputs["wildtype_pdb"],
            variants=inputs["variants"],
            protein_name=inputs["protein_name"],
            wildtype_tm=inputs.get("wildtype_tm"),
        )
    else:
        result = {"error": f"Unknown tool: {name}"}
    return json.dumps(result, ensure_ascii=False, indent=2)


# ──────────────────────────────────────────────
# AGENTIC LOOP
# ──────────────────────────────────────────────

DEFAULT_MODEL = os.getenv("SPECIALIST_MODEL", "claude-sonnet-4-6")


def run_agent(
    user_input: str,
    verbose: bool = True,
    model: str = DEFAULT_MODEL,
) -> str:
    """
    Run the scientific agent (specialist) until it produces a final analysis.

    Args:
        user_input: Description of the protein/objective to analyze
        verbose: Print tool calls as they happen
        model: Claude model to use. Default: SPECIALIST_MODEL from .env,
               fallback to claude-sonnet-4-6. For deep analysis, use claude-opus-4-5.

    Returns:
        Final text analysis (technical brief)
    """
    if verbose:
        print("\n" + "=" * 60)
        print(f"  ESPECIALISTA CIENTIFICO CRIZA (proteinas) — {model}")
        print("=" * 60 + "\n")

    messages = [{"role": "user", "content": user_input}]

    while True:
        # Retry con backoff si Anthropic retorna 429 (rate limit de tokens/min)
        for attempt in range(4):
            try:
                response = client.messages.create(
                    model=model,
                    max_tokens=16000,
                    system=SYSTEM_PROMPT,
                    tools=TOOLS,
                    messages=messages,
                )
                break  # éxito, salir del retry loop
            except anthropic.RateLimitError:
                if attempt == 3:
                    raise  # re-lanzar si agotamos los intentos
                wait = 20 * (attempt + 1)  # 20s, 40s, 60s
                if verbose:
                    print(f"  [rate limit Anthropic — esperando {wait}s antes de reintentar...]\n")
                time.sleep(wait)

        # Add assistant turn to history
        messages.append({"role": "assistant", "content": response.content})

        # ── Final answer ──
        if response.stop_reason in ("end_turn", "max_tokens"):
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return "Analisis completado sin texto."

        # ── Tool calls ──
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
            # Unexpected stop reason
            break

    return "Analisis interrumpido."
