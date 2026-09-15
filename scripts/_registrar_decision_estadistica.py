import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="biotecnologo",
        titulo="Etapa 22 (cont.) — utils/estadistica.py: cómputo numérico real para Biotecnólogo, Microbiólogo e Ingeniero Ambiental",
        decision=(
            "utils/estadistica.py (nuevo) — 4 funciones sobre series temporales [{'fecha','valor'}]: "
            "analizar_estabilidad (media/SD/CV%/tendencia Kendall/clasificación), "
            "detectar_cambios_de_regimen (Mann-Whitney entre períodos consecutivos, exige que el "
            "cambio se sostenga N períodos, filtra blips), correlacion_con_desfase (Pearson barriendo "
            "desfase, SIEMPRE con chequeo de robustez por series diferenciadas -- no es opcional), "
            "comparar_fuentes (detecta sesgo sistemático entre dos fuentes que deberían medir lo "
            "mismo). Sumadas como 4 tools nuevas en biotecnologo_agent.py (16 tools), "
            "microbiologo_agent.py (15) e ingeniero_ambiental_agent.py (10) -- agronomo_agent.py "
            "deliberadamente excluido, sin necesidad real visible todavía. pandas/numpy/scipy "
            "sumados a requirements.txt (no estaban declarados, solo instalados globalmente). "
            "16 tests unitarios con series sintéticas de propiedad conocida (estable real, "
            "tendencia real, quiebre real vs. blip filtrado, correlación real con desfase vs. "
            "espuria por tendencia compartida, fuentes comparables vs. sesgo sistemático). "
            "Verificado real (no solo mocks): dispatch real (sin mockear la función) en los 3 "
            "agentes con la misma serie da el mismo resultado; y una corrida real vía chat/consulta "
            "libre del Biotecnólogo (llamada real a la API, no mock) con una pregunta en lenguaje "
            "natural sobre estabilidad de FOS/TAC hizo que el modelo llamara solo, sin que se le "
            "dijera qué tool usar, analizar_estabilidad_serie y detectar_cambios_de_regimen, y dio "
            "una interpretación de dominio correcta (identificó el mismo outlier que después "
            "confirmó el informe independiente de Claude Science sobre el caso real de Helios)."
        ),
        motivo=(
            "Sebas pidió explícitamente desarrollar estas funciones después de una sesión completa "
            "de análisis real del efluente T401 de Helios donde quedó demostrado en la práctica que "
            "ningún agente podía hacer cómputo numérico -- solo podían 'leer' una tabla como texto y "
            "estimar a ojo. El caso real también dejó una lección concreta que el módulo incorpora "
            "como obligatoria: una correlación 'fuerte' (r=-0.71) que calculé a mano sin chequeo de "
            "robustez resultó espuria (un informe independiente, hecho en Claude Science, la "
            "corrigió diferenciando las series: r=0.09, no significativa) -- por eso "
            "correlacion_con_desfase no permite omitir ese chequeo."
        ),
        alternativas_consideradas=[
            "Un especialista nuevo 'de estadística' en vez de sumar tools a los 3 existentes -- "
            "descartado, mismo criterio que search_pubmed: no diseñar un agente nuevo cuando el "
            "gap es una capacidad, no un dominio nuevo.",
            "Que las tools lean el archivo original (Excel/CSV) en vez de recibir puntos "
            "[{'fecha','valor'}] ya extraídos -- descartado por ahora: documentos_aportados hoy "
            "persiste solo texto extraído, no el archivo original: resolver eso es un cambio de "
            "arquitectura más grande (cómo se almacenan los adjuntos), fuera de alcance de esta "
            "sesión. El especialista extrae los puntos del texto que ya tiene disponible.",
            "Sumar las tools también a agronomo_agent.py -- descartado, sin un caso real que lo "
            "pida todavía (mismo criterio 'no diseñar sin necesidad real' que el resto de la sesión).",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
