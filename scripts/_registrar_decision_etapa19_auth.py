import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="web",
        titulo="Etapa 19 -- hostear la web publicamente: Vercel + Railway, contrasena compartida",
        decision=(
            "Sebas: 'Por lo que veo por el momento solo los puedo usar en local, que falta para "
            "subirlo a una web hosteada.' Primera vez que el sistema sale de localhost. Decisiones "
            "tomadas con Sebas, en orden: (1) barrera de acceso -- preguntado entre 'sin login' / "
            "'contrasena compartida simple' / 'login real', eligio contrasena compartida simple "
            "('recomendado para arrancar'). Mas tarde pregunto si convenia autenticacion "
            "biometrica (huella/Face ID, WebAuthn) en su lugar -- evaluado: WebAuthn es un sistema "
            "de login real completo (credenciales por dispositivo, servidor que las "
            "registra/verifica), mas trabajo del justificado con un solo usuario real hoy, queda "
            "anotado como upgrade si se suma mas gente, no se construyo ahora. (2) hosting -- "
            "frontend a Vercel (equipo sebabizzi-7494's projects ya existe, sin infra propia que "
            "mantener), backend a Railway y no Vercel serverless porque una corrida de "
            "especialista real puede tardar varios minutos (~5 min la del Biotecnologo), excede "
            "el timeout tipico de una funcion serverless; Sebas ya tiene cuenta de Railway "
            "conectada a su GitHub con otros proyectos, no hace falta alta de cuenta. Construido: "
            "api/main.py -- middleware @app.middleware('http') de HTTP Basic Auth, registrado "
            "ANTES de app.add_middleware(CORSMiddleware, ...) a proposito (en Starlette el ultimo "
            "agregado queda mas externo, asi CORS envuelve al de auth y le suma sus headers "
            "tambien a un 401, no solo a las respuestas exitosas -- confirmado con un test "
            "dedicado, no asumido). API_AUTH_USER/API_AUTH_PASSWORD, hmac.compare_digest (no "
            "==). Sin las env vars (dev local), no pide nada. web/proxy.ts -- mismo patron del "
            "lado del frontend, SITE_AUTH_USER/SITE_AUTH_PASSWORD. Archivo nuevo, no "
            "middleware.ts: Next.js 16 depreco middleware.js/.ts, lo renombro a proxy.js/.ts "
            "(encontrado leyendo node_modules/next/dist/docs/, siguiendo la instruccion explicita "
            "de web/AGENTS.md de leer ahi antes de escribir codigo Next.js en este proyecto). "
            "5 tests nuevos en api/tests/test_main.py. Verificado real de punta a punta (no solo "
            "tests): env vars reales seteadas temporalmente contra ambos servers corriendo "
            "localmente, curl real confirmando 401 sin credenciales / 200 con correctas / 401 con "
            "incorrectas / OPTIONS pasa siempre / el 401 lleva headers CORS en un pedido "
            "cross-origin, en las dos capas (api/ y web/proxy.ts), incluido que favicon.ico no "
            "pide auth (excluido por el matcher). Env vars retiradas y ambos servers reiniciados "
            "al terminar -- el dev local sigue sin pedir nada. npm run build limpio, proxy.ts "
            "aparece como Proxy (Middleware) en la tabla de rutas. Regresion completa del "
            "backend: 537 passed, 2 skipped. Fix relacionado el mismo dia (Etapa 17c): "
            "_MAX_CARACTERES_ARCHIVO subido de 60.000 a 400.000 caracteres tras encontrar real que "
            "una transcripcion real de una reunion de Helios excedia el cap viejo -- Sebas pidio "
            "explicitamente priorizarlo ('ajustalo ahora porque necesito subir esa "
            "transcripcion'), se solto el trabajo de auth en curso, se corrigio en el momento, se "
            "retomo el trabajo de auth despues."
        ),
        motivo=(
            "Sebas: 'Por lo que veo por el momento solo los puedo usar en local, que falta para "
            "subirlo a una web hosteada.'"
        ),
        alternativas_consideradas=[
            "Sin login -- descartada explicitamente por Sebas: expondria casos reales (Helios, "
            "MicroBigs) y el token real de Anthropic a cualquiera con la URL.",
            "Login real (usuario/contrasena por persona) -- descartada por ahora: mas trabajo no "
            "justificado con un solo usuario real hoy; queda como upgrade si se suma mas gente.",
            "Autenticacion biometrica (WebAuthn/huella) -- evaluada a pedido explicito de Sebas y "
            "descartada por ahora: es un sistema de login real completo (registro/verificacion de "
            "credenciales, tabla de claves publicas), ademas queda atada a cada dispositivo por "
            "separado (recargar desde otro navegador exige registrar de nuevo) -- friccion mayor "
            "que compartir una contrasena con un solo usuario real.",
            "Vercel serverless para el backend tambien -- descartada: una corrida de especialista "
            "real puede tardar varios minutos, excede el timeout tipico de una funcion "
            "serverless; Railway corre el proceso como servicio persistente.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
