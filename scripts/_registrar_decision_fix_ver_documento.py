import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="conductor",
        titulo="Fix real: _tool_ver_documento tiraba abajo el turno con un ID inválido",
        decision=(
            "Encontrado real, verificando la Etapa 17 de web/ (adjuntar archivos): la primera "
            "corrida real completa con un archivo adjunto terminó en un 500. El Conductor llamó "
            "la tool ver_documento con documento_id='Frente técnico' (un nombre, no un UUID) sin "
            "haber llamado ver_caso primero. _tool_ver_documento hacía motor_api.obtener(id) sin "
            "try/except -- la query cruda del KM reventaba con un DataError de asyncpg (UUID "
            "inválido) sin capturar, y esa excepción se propagaba sin control hasta tirar abajo "
            "todo el turno (tokens del turno gastados, cero respuesta al usuario). A diferencia "
            "de _resolver_caso(), que YA capturaba exactamente este mismo problema (identificador "
            "que no es un UUID válido) desde antes. Corregido con el mismo patrón: try/except "
            "alrededor de motor_api.obtener, tratar la excepción igual que 'no encontrado' "
            "(mismo criterio que ya usan los endpoints de sesión de api/main.py para IDs de "
            "sesión inválidos). Test nuevo: "
            "test_tool_ver_documento_id_invalido_no_revienta_el_turno. Verificado real: reintentado "
            "el mismo flujo (archivo adjunto + pregunta) después del fix -- el Conductor respondió "
            "correctamente sin ningún error."
        ),
        motivo=(
            "No fue un pedido explícito de Sebas -- se encontró en el curso de verificar de "
            "punta a punta la Etapa 17 (adjuntar archivo). Se corrigió en el mismo pase porque es "
            "un bug real, aislado, de bajo riesgo, y del mismo tipo que un incidente anterior de "
            "la sesión (una respuesta 'perdida', Etapa 16) -- cualquier turno del Conductor puede "
            "pisar esta misma clase de error si el modelo adivina un ID en vez de resolverlo "
            "primero."
        ),
        alternativas_consideradas=[
            "Dejarlo para una sesión aparte -- descartado: es un fix de una línea con el patrón "
            "ya establecido en el mismo archivo (_resolver_caso), no ameritaba abrir una etapa "
            "separada ni demorar la corrección de un bug real ya encontrado.",
        ],
        quien="Claude (encontrado durante verificación real, corregido en el mismo pase)",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
