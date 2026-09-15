import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="biotecnologo",
        titulo="Etapa 22 (cont.) — search_pubmed sumado a Biotecnólogo y Microbiólogo",
        decision=(
            "utils/pubmed.py::search_pubmed (nuevo) — wrapper de NCBI E-utilities (esearch + "
            "efetch), sin API key requerida para volumen bajo (NCBI_API_KEY opcional en .env, "
            "sube el rate limit de ~3 a 10 req/seg). Trunca abstracts a 600 caracteres por "
            "default -- misma lección de la Etapa 22 (contexto reventado sin truncar). Sumado "
            "como tool nueva en biotecnologo_agent.py (12avo tool) y microbiologo_agent.py "
            "(11avo tool), en ambos casos SIN mínimo obligatorio en el gate de exhaustividad -- "
            "tratado como consulta de precisión de dominio (mismo criterio que search_kegg/"
            "search_rhea/search_pubchem/search_chebi), no como otro pilar de búsqueda "
            "exhaustiva obligatoria como search_literature/buscar_web_tecnico. No reemplaza "
            "utils/openalex.py -- complementa con vocabulario MeSH biomédico más preciso para "
            "microbiología/bioquímica/toxicología."
        ),
        motivo=(
            "Sebas pidió investigar qué herramientas nuevas sumó Anthropic para agentes "
            "científicos (Claude Science / Claude for Life Sciences, anuncios de 2026-06-30 y "
            "2025-10-20) y evaluar si sirven para mejorar Biotecnólogo/Microbiólogo. Investigación "
            "real (WebFetch + WebSearch + pruebas reales con los plugins bio-research ya "
            "instalados en esta sesión) identificó PubMed como el conector de mejor relación "
            "esfuerzo/valor -- verificado con una búsqueda real ('digestate valorization "
            "value-added products'): 94 resultados reales relevantes al dominio de Helios, con "
            "expansión MeSH automática que OpenAlex no tiene. ChEMBL (otro conector nuevo) se "
            "descartó con la misma metodología -- probado real con 'struvite' y 'phytase', 0 "
            "resultados en ambos casos: indexa fármacos/moléculas con datos clínicos, no encaja "
            "con el dominio de bioprocesos/enzimas de CRIZA."
        ),
        alternativas_consideradas=[
            "ChEMBL -- descartado con evidencia real (0 resultados en 2 pruebas reales sobre "
            "compuestos del dominio de CRIZA), no solo por análisis a priori.",
            "Sumarle un mínimo obligatorio al gate de exhaustividad (como buscar_web_tecnico) -- "
            "descartado por ahora: search_pubmed es más análogo a search_kegg/rhea/pubchem/chebi "
            "(precisión de dominio) que a otro pilar de búsqueda exhaustiva; forzar un mínimo sin "
            "evidencia real de que el modelo lo saltea sería diseñar sin necesidad real.",
            "Depender del plugin MCP bio-research de esta sesión de Claude Code en vez de una "
            "integración Python propia -- descartado: los agentes corren headless contra la "
            "Messages API, no dentro de una sesión de Claude Code, así que el plugin no es "
            "accesible desde su loop autónomo.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
