import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="web",
        titulo="Etapa 11 — panel de características por agente, leído en vivo del código",
        decision=(
            "GET /agentes/{nombre} en api/main.py -- devuelve system_prompt y tools (name/"
            "description/disponible_en_chat) leídos directo de los objetos de módulo ya cargados "
            "en la Etapa 10 (_mod_conductor/_mod_microbiologo/_mod_ingeniero_ambiental/"
            "_mod_agronomo) -- no hay copia ni doc paralelo que se desincronice, es la misma lista "
            "que el agente usa para operar. disponible_en_chat se deriva comparando contra "
            "TOOLS_CHAT (Etapa 10) para marcar qué tools son exclusivas de la corrida formal "
            "(submit_evaluacion_tecnica). Página /agentes/[nombre] (Server Component, solo "
            "lectura) con las tools y el prompt completo. Link 'ℹ️ Características' en /conductor "
            "y en /especialistas/[nombre], target=_blank -- Sebas pidió explícitamente 'puede ser "
            "con un acceso a otra ventana'. 3 tests nuevos, 439/439 unit en verde, auditor sin "
            "hallazgos nuevos. Verificado real contra el servidor corriendo: GET /agentes/"
            "conductor (5 tools reales) y GET /agentes/microbiologo (9 tools reales, incluidas las "
            "4 bioquímicas, submit_evaluacion_tecnica correctamente marcada como solo-corrida-"
            "formal). Página verificada en el navegador con get_page_text."
        ),
        motivo=(
            "Tercer y último pedido de Sebas en el mismo hilo donde se resolvió la persistencia de "
            "sesiones del Conductor (junto con lecciones -- Etapa 9 -- y chat por especialista -- "
            "Etapa 10): 'que en la ventana de cada agente figure, puede ser con un acceso a otra "
            "ventana, las características del agente, qué puede hacer y a qué herramientas está "
            "conectado, con una descripción de cada herramienta y que esto se actualice cuando hay "
            "cambios de características o de herramientas a las que está conectado'."
        ),
        alternativas_consideradas=[
            "Documento Markdown mantenido a mano por agente -- descartado de entrada: es "
            "exactamente el tipo de desincronización silenciosa que CLAUDE.md ya identificó como "
            "causa raíz de deuda documental en este proyecto (ver decisión del 15/08 sobre "
            "agents.md generado). El pedido explícito de Sebas ('que se actualice solo') excluía "
            "esta opción directamente.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
