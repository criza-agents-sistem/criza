import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="web",
        titulo="Etapa 16 (bug real) — historial de conversaciones + recordar sesión activa",
        decision=(
            "Bug reportado por Sebas: una respuesta del Conductor 'se perdió' al volver más "
            "tarde a /conductor. Investigado antes de tocar código: el dato NUNCA se perdió -- "
            "seguía intacto en el KM (conductor_sesiones), se le mostró de vuelta completo. La "
            "causa real: /conductor y /especialistas/[nombre] creaban una sesión nueva en cada "
            "carga de página y nunca guardaban el session_id en ningún lado del browser, así que "
            "volver más tarde siempre arrancaba una conversación vacía nueva, dejando la anterior "
            "huérfana (pero intacta) en el KM -- confirmado con 48 sesiones de Conductor creadas "
            "ese día, la mayoría vacías. Fix en dos piezas, ambas elegidas explícitamente por "
            "Sebas entre 3 opciones ('localStorage solo' / 'historial solo' / 'los dos'): (1) "
            "localStorage guarda el session_id activo (clave por página en el Conductor, clave "
            "por especialista+frente en el chat de especialistas) -- al montar, si hay uno "
            "guardado, hidrata el chat desde el KM en vez de crear uno nuevo; (2) botón "
            "'Historial' en ambas páginas -- 4 endpoints GET nuevos en api/main.py "
            "(/conductor/sesiones, /conductor/sesiones/{id}, /especialistas/sesiones?"
            "especialista=, /especialistas/sesiones/{id}), reconstruyen los turnos visibles vía "
            "_mensajes_a_turnos() (filtra pasos intermedios de tool-use/tool-result) sin campo "
            "nuevo en el KM -- la misma fuente que ya se guardaba alcanza. 12 tests nuevos, "
            "474/474 unit en verde, auditor sin hallazgos nuevos. Verificado real: con el "
            "session_id de la conversación reportada como perdida en localStorage, recargar "
            "/conductor la restauró completa (mismo texto, mismos 5 vectores blue ocean); el "
            "panel de Historial listó las 8 conversaciones reales del Conductor en orden correcto "
            "por fecha, reabrir una distinta funcionó; repetido en /especialistas/microbiologo "
            "con 7 sesiones reales y la etiqueta correcta (consulta libre / sobre un frente)."
        ),
        motivo=(
            "Sebas: 'tenemos un problema, le hice una pregunta al conductor, me respondió, cuando "
            "quise volver al rato, se había borrado lo que me respondió y se perdió eso, gasté "
            "tokens, perdí la información, no quedó registrada en ningún lugar visible.'"
        ),
        alternativas_consideradas=[
            "Solo localStorage (sin historial completo) -- descartada explícitamente por Sebas: "
            "no cubre cambiar de navegador/dispositivo ni un localStorage borrado.",
            "Solo historial completo (sin localStorage) -- descartada explícitamente por Sebas: "
            "no evita que una simple recarga de página arranque una sesión nueva por default.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
