import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="financiero_agent",
        titulo="Etapa 21 (cont.) -- COMTRADE sumado + 4o bug real de serializacion",
        decision=(
            "Sebas, al ver el resultado de la primera corrida: 'esta bueno que no tenga sesgo y "
            "que avise cuando no pudo acceder a determinada informacion, pero es importante que "
            "pueda acceder a toda la informacion necesaria para cumplir sus funciones.' Revisado "
            "que fuente real, ya verificada y con key configurada, faltaba: COMTRADE "
            "(market_agent/tools/comtrade.py, ya existia, con key real configurada) -- "
            "importaciones reales de Argentina por codigo HS. Mercado la excluyo explicitamente "
            "(decision H de su Design Gate) porque sesga la eleccion de PRODUCTO hacia "
            "sustitucion de importaciones -- ese motivo no aplica a Financiero, que no elige "
            "producto, solo lo cotiza. Verificada real antes de sumarla (get_import_data('3105') "
            "-> datos reales de 2023, USD 805M importado). Sumada como tool search_comtrade, con "
            "instruccion explicita de no usarla para razonar sobre conveniencia de importar/"
            "sustituir. Key copiada de market_agent/.env a api/.env (el proceso real que corre "
            "los especialistas). Al reverificar con la tool nueva, aparecio un 4o bug real: el "
            "fix anterior (.model_dump() sin mas) no alcanzaba -- server_tool_use/"
            "web_search_tool_result incluyen un campo text:None que la API de Anthropic rechaza "
            "como 'Extra inputs are not permitted' al reenviar ese bloque como historial en el "
            "turno SIGUIENTE al que lo genero (no revienta al guardar, revienta un turno despues "
            "-- por eso no se vio en la primera verificacion, que solo tuvo 1 turno real con "
            "web_search). Corregido con model_dump(exclude_none=True). Reverificado real con una "
            "sesion nueva de punta a punta: search_bcra, search_comtrade, web_search, "
            "buscar_corpus_cientifico y pedir_informacion_faltante en una sola corrida, sin "
            "ningun error de serializacion en ningun turno subsiguiente. Regresion completa: 640 "
            "passed."
        ),
        motivo=(
            "Sebas: 'ya tiene acceso a toda la información que necesita, porque está bueno que no "
            "tenga sesgo y que avise cuando no pudo acceder a determinada información, pero es "
            "importante que pueda acceder a toda la información necesaria para cumplir sus "
            "funciones.'"
        ),
        alternativas_consideradas=[
            "No sumar COMTRADE, dejar los gaps de precio/costo como a-confirmar siempre -- "
            "descartada porque la fuente existe, ya esta verificada y pagada (key real), y el "
            "motivo por el que Mercado la excluyo (sesgo de eleccion de producto) no aplica a un "
            "agente que no elige producto.",
            "Reusar comtrade.py vía market_agent/tools (paquete) en vez de importar el submódulo "
            "directo -- descartada porque el __init__.py de ese paquete no lo exporta a "
            "propósito (decisión H de Mercado); importar el submódulo directo documenta bien por "
            "qué Financiero sí puede usarla sin reabrir esa decisión.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
