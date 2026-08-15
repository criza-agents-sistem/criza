import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="ai_client",
        titulo="Capa de abstracción de proveedor de modelo por agente (LiteLLM)",
        decision=(
            "utils/ai_client.py (nuevo): complete()/complete_streaming() reemplazan "
            "client.messages.create()/.stream() de Anthropic. La interfaz pública queda en la "
            "forma nativa de Anthropic (bloques de contenido, tool_use/tool_result, "
            "stop_reason, usage.input_tokens/output_tokens) — cero diff en el loop agéntico de "
            "cada agente, el módulo traduce hacia/desde LiteLLM (formato OpenAI) por debajo. "
            "resolver_modelo() acepta 'proveedor/modelo' o solo 'modelo' (asume anthropic/, "
            "compatible con los .env existentes sin tocarlos). Migrados Evidence Generalista, "
            "Investigación Amplia y Armador (streaming, MAX_TOKENS 64000). Mercado excluido a "
            "propósito — usa la tool nativa web_search_20250305 de Anthropic, sin equivalente "
            "portable a otros proveedores todavía."
        ),
        motivo=(
            "PROPUESTA_DESTINO.md §8: elegir modelo y proveedor por agente desde un desplegable "
            "en la web. LiteLLM ya es la decisión de plataforma (platform-boundary.md, 'Stack "
            "base... LiteLLM — patrón, no código copiado'), no había que diseñar el mecanismo, "
            "solo adoptarlo y traducir el formato de respuesta que ya esperaban los agentes."
        ),
        alternativas_consideradas=[
            "Reescribir cada agente contra el formato OpenAI-nativo de LiteLLM directamente — "
            "descartada: mucho más diff y riesgo por agente (loop de tool-use, cache_control, "
            "truncado) para el mismo resultado.",
            "Migrar los 5 agentes de una — descartada: Mercado depende de una tool nativa de "
            "Anthropic sin equivalente portable; se migra solo cuando haga falta elegir otro "
            "proveedor para ese agente puntual.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
