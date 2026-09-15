import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="conductor",
        titulo="Etapa 22 (cont.) — previsualización de Excel confiable + freno anti-fabricación en el Conductor",
        decision=(
            "Bug real encontrado en producción: al preguntarle al Conductor (sesión real, no "
            "prueba) el rango de fechas de T401, inventó 'desde febrero 2022' — una fecha que no "
            "existía en ningún tool output real disponible. Causa raíz: previsualizar_excel "
            "(utils/archivos.py) leía ciegamente las primeras 5 filas sin detectar dónde está el "
            "header real, y no calculaba ningún hecho (filas, rango de fechas) — le daba al "
            "Conductor una previsualización sin sustancia, así que completó con un valor "
            "plausible. Fix de dos partes: (1) previsualizar_excel ahora detecta el header real "
            "por hoja (heurística: fracción de celdas no-nulas * fracción de texto, sobre las "
            "primeras 15 filas) y calcula en Python — nunca deja que el modelo adivine — cantidad "
            "de filas y, si hay columna de fecha reconocible, su rango real (min/max). (2) Se "
            "agregó un párrafo explícito a la descripción de la tool ver_documento en el "
            "SYSTEM_PROMPT del Conductor, citando el incidente real por nombre ('no vuelvas a "
            "hacer eso') e instruyendo a decir 'no sé' en vez de completar con un valor plausible "
            "cuando la previsualización no trae el dato exacto pedido. Dos bugs adicionales "
            "encontrados corriendo el fix contra los 3 Excel reales de Helios (antes de tocar el "
            "Conductor): (a) df.columns no se reasignaba con los nombres ya 'stripeados' -> "
            "KeyError apenas un header tenía un \\n o espacios, rompía toda la previsualización "
            "(reventaba con 'Base de datos Logística.xlsx' real); (b) con varias columnas que "
            "contienen 'fecha' en el nombre (el archivo real de T401 tiene 6: presupuesto, envío, "
            "aprobación, recepción, análisis, muestreo), tomar la PRIMERA que matcheaba agarraba "
            "una columna administrativa casi vacía (25 de 893 filas) en vez de la fecha de "
            "muestreo real — un rango técnicamente calculado pero igual de engañoso que uno "
            "inventado. Corregido: se evalúan todas las columnas candidatas y se reporta la más "
            "completa (más fechas válidas), con nota explícita de que puede no ser la única. "
            "Se regeneró el 'contenido' (texto de previsualización) de los 3 documento_aportado "
            "ya subidos al Frente técnico real de Helios, sin tocar el archivo original guardado."
        ),
        motivo=(
            "Sebas, tras ver la fabricación real en producción: 'es que no me genera confianza "
            "esa visión parcial que tiene el conductor de los archivos excel, me parece que es "
            "parte del problema' y, después de la primera ronda de arreglos: 'no me termina de "
            "convencer que con esa información el conductor pueda tomar buenas decisiones de cuál "
            "es el paso siguiente, lo probamos si querés, pero siento que está ciego o ve poco'. "
            "Decisión de diseño explícita (no nueva, reconfirmada acá): NO darle al Conductor las "
            "tools de cómputo real (leer_serie_de_excel, utils/estadistica.py) — esa capacidad ya "
            "vive en los 5 especialistas por decisión previa (ver decisión 'agentes leen Excel "
            "real de un caso'), y el Conductor orquesta, no calcula. Con esa restricción ya fija, "
            "quedaban dos palancas: mejorar lo que el Conductor SÍ ve (previsualización real) y "
            "reforzar que no rellene con un valor plausible lo que no ve — se aplicaron las dos, "
            "belt-and-suspenders, porque ninguna sola garantiza que no fabrique otra cosa distinta "
            "más adelante."
        ),
        alternativas_consideradas=[
            "Darle al Conductor las tools reales de lectura/cómputo de Excel — descartado: ya "
            "decidido explícitamente que el Conductor orquesta y los especialistas calculan (ver "
            "decisión previa, Conductor y Agrónomo excluidos a pedido de Sebas). Revertir esa "
            "frontera no se justificaba por este bug puntual.",
            "Solo el freno de prompt en el Conductor, sin mejorar previsualizar_excel — "
            "descartado: el freno evita que invente, pero seguía dejando al Conductor sin ningún "
            "hecho real para citar (tendría que decir 'no sé' incluso cuando el dato SÍ estaba "
            "calculable de forma determinística, como el rango de fechas de una hoja completa).",
            "Solo mejorar previsualizar_excel, sin el freno de prompt — descartado: no cubre el "
            "caso de un dato que la previsualización sigue sin traer explícito (ej. un total "
            "filtrado por código específico) — sin el freno, el modelo puede seguir completando "
            "ese resto con un valor plausible.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
