import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="casos",
        titulo="Etapa 22 (cont.) — agentes leen Excel real de un caso (no solo texto extraído)",
        decision=(
            "utils/archivos.py (nuevo): codificar_archivo (bytes->base64, tope 8MB), "
            "previsualizar_excel (texto legible de hojas/columnas/primeras filas para mostrar en "
            "chat), leer_serie_de_excel (decodifica + pandas, devuelve [{'fecha','valor'}], con "
            "header_fila y filtro_columna/filtro_valor explícitos -- nunca adivina estructura). "
            "utils/casos.py extendido: guardar_documento_aportado acepta "
            "archivo_original_b64/archivo_nombre opcionales (mismo prop JSONB, sin migración de "
            "schema); guardar_documento_aportado_desde_excel (nueva, lee un .xlsx real de disco y "
            "lo persiste con preview + archivo original); obtener_archivo_original_de_documento_"
            "aportado (nueva, deliberadamente separada de obtener_documento_por_id -- esa "
            "alimenta ver_informe_especialista, si devolviera el base64 ahí inflaria el contexto "
            "del modelo con datos binarios cada vez que se lee un informe). Tool nueva "
            "'leer_serie_de_documento_aportado' sumada a 5 agentes: biotecnologo_agent.py (17 "
            "tools), microbiologo_agent.py (16), ingeniero_ambiental_agent.py (11) -- estos 3 ya "
            "tenian utils/estadistica.py de ayer -- y financiero_agent.py + market_agent.py, que "
            "ademas sumaron las 4 tools de estadistica (no las tenian). Conductor y "
            "agronomo_agent.py quedan afuera -- sin necesidad real mostrada todavia. Fuera de "
            "alcance deliberado: el endpoint web de subida (api/main.py /archivos/extraer) sigue "
            "sin soportar .xlsx -- hoy la unica forma de adjuntar un Excel real a un caso es via "
            "guardar_documento_aportado_desde_excel desde un script/sesion de Claude Code, no "
            "desde el chat web. Verificado real (no solo mocks): el Excel real de T401 (el mismo "
            "caso de Helios) se adjunto de verdad al Frente tecnico real, y el Biotecnologo lo "
            "leyo del KM real (sin mockear nada) -- primero la hoja limpia (n=813 pH, coincide "
            "exacto con el analisis manual de hace 2 dias), despues la hoja con 4 codigos de "
            "digestor mezclados usando el filtro (n=154 filtrado a T401, coincide con el conteo "
            "real), encadenado con analizar_estabilidad_serie real (CV=0.69%, ESTABLE)."
        ),
        motivo=(
            "Sebas, sobre el caso real de Helios (T401 se sigue muestreando cada mes): 'los "
            "agentes no se pueden auto-abastecer... necesitan que yo le pida a Claude Science o a "
            "vos esos datos, con los riesgos que eso tiene (sesgos, contexto, etc.)'. Depender de "
            "una extraccion manual cada vez que el dato de un caso se actualiza no escala ni es "
            "auditable -- exactamente el tipo de paso no estructurado que el CLAUDE.md de "
            "plataforma senala como riesgo de sesgo. Pedido explicito de alcance amplio: 'que lo "
            "tengan todos los que lo pueden llegar a necesitar' -- acotado con evidencia real "
            "(Financiero/Mercado: el propio Sebas confirmo 'hay mucho Excel en esas funciones'), "
            "no en abstracto (Conductor/Agronomo excluidos explicitamente por el propio Sebas al "
            "no haber necesidad real mostrada)."
        ),
        alternativas_consideradas=[
            "Dárselo a los 7 agentes (incluido Conductor y Agrónomo) -- descartado explícitamente "
            "por Sebas después de discutir el costo real de sumar tools sin necesidad "
            "(\"no queda gratis, generalmente asume mal cuándo usarla\").",
            "Extender api/main.py para soportar upload de .xlsx desde el chat web ahora -- "
            "descartado por alcance: toca infraestructura compartida (Conductor + los 4 "
            "especialistas viejos) y necesita cambios de frontend para probarse de punta a "
            "punta; el entry point real usado hoy en este proyecto (Sebas comparte la ruta del "
            "archivo directo en una sesión de Claude Code) ya cubre la necesidad actual.",
            "Guardar el archivo original en blob storage en vez de base64 en el mismo prop JSONB "
            "-- descartado por ahora: los Excel reales de este proyecto son de unos pocos MB, "
            "JSONB alcanza; blob storage real solo se justifica si aparecen archivos mucho más "
            "grandes.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
