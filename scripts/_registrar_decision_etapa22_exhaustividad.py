import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="biotecnologo",
        titulo="Etapa 22 (2026-09-14) -- busqueda genuinamente exhaustiva, con gate real en codigo",
        decision=(
            "Sebas, retomando los agentes de Helios ('quiero tener todo el equipo funcionando'), "
            "planteo un problema nuevo: ve en redes sociales/revistas especializadas productos de "
            "biorefineria/valorizacion que no van a estar en OpenAlex/CONICET/INTA por ser "
            "internacionales o comerciales, no academicos -- pregunto si se puede armar un agente "
            "que revise eso. Explorado: no un agente nuevo, sino sumarle herramientas nuevas "
            "(Bright Data: SERP multilenguaje + Instagram estructurado) al Biotecnologo existente, "
            "que ya tiene el rol de mapear rutas de valorizacion. Bloqueado en la cuenta de Bright "
            "Data que Sebas todavia no armo -- pero en el medio, Sebas planteo una preocupacion mas "
            "fundamental y previa: 'me preocupa que el agente decida que no es importante y no "
            "busque exhaustivamente... me preocupa el sesgo que tienen a simplificar y hacer "
            "muestreo sin ser exhaustivo'. Confirmado contra el codigo real: no existia NINGUN "
            "mecanismo que forzara exhaustividad -- el unico precedente (cobertura_declarada de "
            "investigacion_amplia) es autodeclarado por el modelo, nadie lo verifica. Sebas, tras "
            "presentarle el tradeoff de costo real ('esto va a costar mas tokens'): 'la probabilidad "
            "de encontrar aumenta y por ende de exito, estamos ante un problema que no sabemos si "
            "alguien encontro solucion... si no somos exhaustivos el proyecto fracasa y por ende el "
            "resultado del menor gasto en tokens sera inutil' -- prioridad explicita de cobertura "
            "sobre costo para este caso especifico. Implementado en Biotecnologo (empezando ahi, no "
            "en los 6 agentes -- alcance acotado explicitamente acordado con Sebas): "
            "search_literature_exhaustivo (utils/openalex.py, nueva, pagina de verdad en vez de "
            "top-N, no reemplaza search_literature que siguen usando los otros 3 especialistas); "
            "las 3 tools de busqueda (search_literature/buscar_corpus_cientifico/search_corpus_inta) "
            "ya no dejan que el modelo elija el limite, el codigo lo fija; gate real que bloquea "
            "submit_evaluacion_tecnica en codigo (no en el prompt) si no hubo al menos 4 consultas "
            "genuinamente distintas en search_literature + 1 en cada corpus local, con valvula de "
            "seguridad de 3 rechazos para no quedar en loop infinito. 2 bugs reales encontrados con "
            "corridas reales, no con analisis a priori: (1) el primer diseño (max_total=200 sin "
            "truncar abstract, limits de 1000-2000 en los corpus) revento el limite de contexto de "
            "Claude (1.5M+ tokens > 1M) en el turno 5 de una corrida real -- corregido bajando "
            "limites (max_total=40, abstract truncado a 250 caracteres, corpus a 150 fijo); (2) "
            "incluso con limites bajados, una corrida real de 8 busquedas (el doble del minimo) "
            "llego al 96% del limite de contexto -- la API de mensajes reenvia la conversacion "
            "completa en cada turno, con busqueda exhaustiva real eso crece rapido. Corregido con "
            "poda de historial: los tool_results de turnos ya 'leidos' por el modelo (el turno "
            "donde se genero la respuesta siguiente) se reemplazan por un resumen corto antes del "
            "turno que sigue -- nunca el ultimo batch, que el modelo todavia no proceso. Verificado "
            "real dos veces (antes y despues del fix de poda), sin persistir al KM (no toca el caso "
            "real de Helios): la segunda corrida hizo 22 turnos reales, 30 variantes de "
            "search_literature (7x el minimo exigido -- el modelo siguio mas alla del piso porque "
            "el problema lo ameritaba, exactamente lo que Sebas pidio), mas KEGG/Rhea/PubChem/ChEBI "
            "cruzados en profundidad. Ningun turno individual supero 100K tokens de contexto (vs. "
            "960K/1M antes de la poda). ~10.4 minutos, ~730K tokens totales sumados, costo real "
            "estimado ~USD 2-3 por corrida asi de exhaustiva -- costo real, aceptado explicitamente "
            "por Sebas. 19 tests nuevos. Regresion completa: 530 passed. Commiteado localmente en "
            "la rama etapa-21-agente-financiero (nunca pusheada, sin PR) -- push/PR pendiente de "
            "confirmar con Sebas, no asumido."
        ),
        motivo=(
            "Sebas: 'la probabilidad de encontrar aumenta y por ende de exito, estamos ante un "
            "problema que no sabemos si alguien encontro solucion en Argentina nadie, por lo que si "
            "no somos exhaustivos el proyecto fracasa y por ende el resultado del menor gasto en "
            "tokens sera inutil'."
        ),
        alternativas_consideradas=[
            "Aplicar el estandar de exhaustividad a los 6 especialistas de una vez -- descartada "
            "por ahora, acordado explicitamente con Sebas empezar acotado por Biotecnologo (el caso "
            "real de hoy) y extender despues, dado el tamaño real del cambio (cada agente tiene "
            "fuentes distintas) y el riesgo de romper algo que ya funciona bien en los otros 5.",
            "Agregar la instruccion de exhaustividad solo en el prompt ('buscá bien') -- descartada "
            "explicitamente: CLAUDE.md ya establece que el sesgo se atrapa con estructura, no con "
            "prompts de 'tenelo en cuenta', y el propio Sebas identifico el riesgo de que el modelo "
            "decida por su cuenta que ya busco suficiente.",
            "Mantener max_total alto (200) confiando en que alcanzaria -- descartada tras la "
            "corrida real que revento el contexto; el numero se ajusto con dato real, no estimado.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
