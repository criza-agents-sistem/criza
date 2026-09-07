import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="financiero_agent",
        titulo="Etapa 21 -- Agente Financiero, construido de cero, con chequeo anti-sesgo explicito",
        decision=(
            "Sexto agente de la biblioteca -- el 'Modelo economico-financiero' que el propio "
            "Conductor identifico como gap sin cubrir (2026-08-24, ver market_agent Etapa 20). "
            "Sebas: 'vamos con el modelo economico-financiero, este tiene que ser muy "
            "profesional.' Preguntado nivel de rigor e input antes de codear: 'Modelo financiero "
            "completo' + 'las dos cosas, incluso el agente podria pedir que informacion necesita "
            "para trabajar.' Aprobado el plan con un pedido final explicito: 'Si, dale, solo te "
            "pido ultimo chequeo de que no tenga sesgos.' Primer especialista construido de cero "
            "desde el Biotecnologo (2026-08-17) -- a diferencia de Mercado (adaptado en Etapa "
            "20), aca no habia codigo previo. Construido con cliente nativo Anthropic (como "
            "Mercado, misma excepcion permanente por web_search -- comparables de costo/precio "
            "vigentes no estan en ningun corpus local). Dos capacidades nuevas: utils/bcra.py "
            "(API publica del BCRA, verificada real -- tipo de cambio, tasas de referencia, "
            "inflacion, sin auth) y utils/casos.py::crear_pendiente (hasta esta etapa NINGUN "
            "agente, ni el Conductor, podia crear un pendiente -- solo leerlos). Chequeo "
            "anti-sesgo documentado como tabla de riesgos + mitigacion concreta (Design Gate "
            "decision D), no como afirmacion generica: (1) tasa de descuento nunca un default de "
            "manual de finanzas -- siempre derivada de search_bcra + prima de riesgo justificada, "
            "test explicito verifica que el prompt no tenga un % hardcodeado; (2) costos/precios "
            "nunca 'recordados' del entrenamiento -- solo de busqueda real o declarados "
            "a-confirmar/pedidos via pedir_informacion_faltante; (3) analisis_sensibilidad exige "
            "un escenario pesimista genuinamente adverso, no 'base menos un poco'; (4) "
            "riesgo_cambiario es campo obligatorio (aunque la respuesta sea 'no aplica'), lee el "
            "alcance geografico que recomendo Mercado antes de fijar monedas; (5) el agente ARMA "
            "el modelo con sus numeros y gaps, nunca concluye 'conviene'/'no conviene' -- mismo "
            "limite que rige a los otros 5 (CLAUDE.md: 'el sistema ARMA, el humano ELIGE'); (6) "
            "checklist generico de siempre, cero menciones de caso concreto en el SYSTEM_PROMPT. "
            "3 bugs reales encontrados y arreglados durante la verificacion viva (ninguno via "
            "tests, todos via una corrida real contra produccion): (a) conductor.py::"
            "serializar_mensajes solo contemplaba ContentBlock (utils/ai_client.py) para "
            "persistir sesiones de chat, nunca los bloques nativos del SDK de Anthropic "
            "(TextBlock/ToolUseBlock, pydantic v2) que produce cualquier agente Anthropic-only -- "
            "revienta con TypeError al persistir CUALQUIER turno de chat con Mercado o "
            "Financiero; corregido generalizando a un helper que tambien llama .model_dump() si "
            "existe -- afecta retroactivamente tambien al chat de Mercado, que nunca habia "
            "ejercitado este camino completo (HTTP + persistencia) en su propia verificacion; (b) "
            "utils/bcra.py::search_bcra_variables exigia el query completo como substring "
            "literal -- un query natural como 'BADLAR bancos privados' no matcheaba la "
            "descripcion real ('Tasa de interes BADLAR DE bancos privados') por la palabra 'de' "
            "de mas, y el agente reportaba la tasa de descuento como a-confirmar en vez de "
            "fundamentarla en datos reales -- exactamente el chequeo anti-sesgo central de este "
            "agente; corregido con matching AND de palabras sueltas, reverificado directo contra "
            "el query real que fallo; (c) uvicorn --reload solo observa api/ -- un cambio en "
            "conductor/conductor.py o utils/bcra.py (fuera de ese arbol) no dispara reload, hay "
            "que matar y reiniciar el proceso completo (mismo gotcha ya documentado en la Etapa "
            "20). Regresion completa: 633 passed, 1 fallo preexistente no relacionado "
            "(sentence_transformers ausente del entorno). Verificado real de punta a punta: "
            "sesion de chat real via HTTP contra el Frente tecnico de Helios -- leyo 3 informes "
            "reales del Biotecnologo (struvita/ectoina/microalgas/PHA), uso search_bcra (6 "
            "consultas reales, encontro tipo de cambio real pero no tasas en esa corrida previa "
            "al fix), web_search real (precios ectoina/fertilizantes), buscar_corpus_cientifico "
            "(papers CONICET/INTA reales citados), y creo 3 pendientes reales via "
            "pedir_informacion_faltante (CAPEX real de planta struvita, costo actual de gestion "
            "del efluente, escala real de produccion prevista) -- verificados presentes en el KM "
            "despues de la corrida. Declaro honestamente tasa_descuento como a-confirmar cuando "
            "la busqueda no encontro la tasa (en vez de inventar un numero), exactamente el "
            "comportamiento anti-sesgo buscado incluso en el caso de falla de la herramienta."
        ),
        motivo=(
            "Sebas: 'vamos con el modelo económico-financiero, este tiene que ser muy "
            "profesional' ... 'Sí, dale, sólo te pido último chequeo de que no tenga sesgos.'"
        ),
        alternativas_consideradas=[
            "Traductor generico utils/ai_client.py en vez de cliente nativo Anthropic -- "
            "descartada porque el modelo financiero necesita web_search real para comparables de "
            "costo/inversion vigentes, sin equivalente en el traductor (misma excepcion ya "
            "decidida para Mercado).",
            "Asumir un default de tasa de descuento tipo manual de finanzas (10-12%) -- "
            "descartada explicitamente: distorsiona el VAN/TIR en el contexto de tasas reales "
            "argentinas, mucho mas altas. Se exige derivarla de search_bcra siempre.",
            "Bloquear el analisis completo si falta un dato critico -- descartada a favor de "
            "pedir_informacion_faltante (crea un pendiente real) + declarar el item a-confirmar, "
            "asi el modelo sigue siendo util aunque incompleto.",
            "Dejar pasar el bug de serializar_mensajes sin arreglarlo (via spawn_task, como el "
            "bug de hasattr en Mercado) -- descartada porque bloqueaba activamente la "
            "verificacion del propio agente que se estaba construyendo, no es deuda diferible.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
