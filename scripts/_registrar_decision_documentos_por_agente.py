import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="conductor",
        titulo="Etapa 19 (cont.) -- identificar el ultimo informe de cada especialista, con fecha real",
        decision=(
            "Sebas le preguntó al Conductor 'necesito descargar los últimos informes de cada "
            "agente, los que hicieron con los datos actualizados de los efluentes, cómo se "
            "cuáles son?' -- el Conductor no pudo responder con ids reales, solo describir "
            "cualitativamente y mandar a buscar en la web a mano. Diagnóstico real: "
            "_tool_ver_caso armaba el briefing con solo el conteo y el título del último "
            "documento por frente, sin ids ni fecha ni distinguir por especialista. Peor: "
            "docs[-1] ni siquiera era confiablemente 'el último' -- "
            "utils/casos.py::obtener_documentos_de_frente delegaba en motor_api.conexiones_de "
            "(genérico de knowledge_module), que no ordena por fecha ni expone created_at. "
            "Desbloqueo inmediato: se consultó la base directo (ficha.created_at, no expuesto "
            "por motor_api.obtener()) para darle a Sebas los 4 links de descarga reales de los "
            "informes más recientes de Helios (uno por especialista, de 13 documentos totales). "
            "Fix real después: obtener_documentos_de_frente reescrita con su propia consulta SQL "
            "(ORDER BY created_at ASC, expone creado_en) -- anotado como candidato a promover a "
            "knowledge_module.motor.api.conexiones_de (order_by genérico) si otra instancia lo "
            "necesita, no antes (regla de capa). _tool_ver_caso ahora incluye "
            "documentos_producidos_detalle (id+titulo+agente+fecha) por frente, con la nota del "
            "briefing instruyendo explícitamente usar el último elemento de cada agente distinto "
            "y el id real para armar /documentos/{id}/descargar. GET /casos/{id} (api/main.py) "
            "también suma agente+creado_en por documento, gratis para la web. Verificado real de "
            "punta a punta: _tool_ver_caso('Helios') identificó los mismos 4 ids que la consulta "
            "manual directa a la base. Regresión completa: 539 passed (excluyendo "
            "scientific_agent, colección rota desde antes, no relacionado)."
        ),
        motivo=(
            "Sebas: 'necesito descargar los últimos informes de cada agente, los que hicieron "
            "con los datos actualizados de los efluentes, cómo se cuáles son?' -- resuelto ahora "
            "en vez de anotado como pendiente, por la urgencia real de necesitar los archivos."
        ),
        alternativas_consideradas=[
            "Tool nueva 'listar_documentos_de_frente' en vez de extender ver_caso -- descartada: "
            "el Conductor ya llama ver_caso como primer paso casi siempre, una tool aparte "
            "hubiera sido una llamada extra evitable para algo que cabe en el mismo briefing.",
            "Promover el ordenamiento a knowledge_module.motor.api.conexiones_de (order_by "
            "genérico) ahora mismo -- deferida, no descartada: es candidato real a plataforma, "
            "pero solo CRIZA lo pidió hasta ahora (regla de capa, CLAUDE.md) -- se resuelve en "
            "utils/casos.py (Capa 2) hasta que otra instancia lo necesite de verdad.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
