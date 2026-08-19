import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="infra",
        titulo="Etapa 19 (cont.) -- Railway estaba CRASHED, no online: Root Directory=api es incompatible con api/main.py",
        decision=(
            "Sesion anterior (2026-08-18, misma fecha) habia dejado el deploy de Railway dado por "
            "'online, confirmado por Sebas' con Root Directory=api como fix. Sebas pidio "
            "'continuemos' -- railway logs (CLI ya logueado en la maquina, no hizo falta esperar "
            "el conector MCP sin autorizar) mostro el deployment real en CRASHED, sin dominio "
            "publico generado. Causa raiz real: ModuleNotFoundError: No module named 'docx' -- "
            "Root Directory=api hace que Railway copie SOLO api/ al contenedor, el "
            "requirements.txt de la raiz nunca estuvo disponible para el build. Mas grave: "
            "api/main.py importa conductor/conductor.py y utils/casos.py directo via "
            "sys.path.insert (reuso de codigo) -- con Root Directory=api esas carpetas hermanas "
            "tampoco existen dentro del contenedor. Root Directory=api es estructuralmente "
            "incompatible con este backend, no un ajuste menor. Intento intermedio "
            "(api/requirements.txt con '-r ../requirements.txt') confirmo esto en la practica: "
            "'Could not open requirements file: /requirements.txt' -- revertido. Fix real: "
            "railway.json en la raiz del repo (buildCommand: pip install -r requirements.txt; "
            "startCommand: cd api && uvicorn main:app --host 0.0.0.0 --port $PORT), reemplaza la "
            "autodeteccion de Railpack (causa del fallo original de anteayer, antes de que Root "
            "Directory=api 'solucionara' el sintoma equivocado) por comandos explicitos -- no "
            "depende de que Railpack adivine bien en un monorepo con Python (raiz + market_agent/ "
            "+ scientific_agent/) y Node (web/) mezclados. Pendiente manual, no seteable por el "
            "Railway CLI v5.23.1 (probado: 'service', 'config' pide un SDK de TypeScript no "
            "publicado en npm, 404): Sebas tiene que borrar 'Root Directory' (api -> vacio) en el "
            "dashboard de Railway, Settings > Build, para que railway.json entre en efecto. "
            "Ademas, de las 10 variables que la sesion anterior daba por subidas al servicio de "
            "Railway, solo 8 estaban realmente ahi -- faltaban DATABASE_URL y ANTHROPIC_API_KEY "
            "(sin DATABASE_URL la API no hubiera arrancado ni arreglando el resto), cargadas "
            "ahora desde api/.env local via 'railway variables --set' (el valor nunca aparecio "
            "en el texto de los comandos -- command substitution en el propio shell). "
            "API_AUTH_PASSWORD tenia el placeholder literal 'elegi-una-contrasena-aca' sin "
            "completar nunca -- reemplazada por una contrasena real generada. Dominio publico "
            "generado (railway domain): https://criza-production.up.railway.app. De paso: "
            "'vercel link' re-linkeo el proyecto web/ (necesario para leer/pushear env vars por "
            "CLI) y agrego .vercel + .env* a web/.gitignore. Confirmado con 'vercel env pull' que "
            "NEXT_PUBLIC_API_URL y SITE_AUTH_USER/PASSWORD en Vercel estan vacios todavia -- no "
            "es fuga de secreto, son placeholders sin valor puesto (confirmado ademas que el auth "
            "de la app SI esta activo en produccion via curl directo a criza-chi.vercel.app "
            "devolviendo 401 con el WWW-Authenticate de proxy.ts, con otros valores que si estan "
            "cargados)."
        ),
        motivo=(
            "railway logs mostro el crash real -- las notas de la sesion anterior daban el "
            "deploy por 'online' sin haber verificado con un pedido real contra la URL publica "
            "(que ademas no existia todavia)."
        ),
        alternativas_consideradas=[
            "Curar un api/requirements.txt propio con subset de dependencias -- descartada tras "
            "confirmar que api/main.py necesita el mismo set de deps que conductor/ y utils/ "
            "(no un subset acotado), y que ademas Root Directory=api ni siquiera deja ver esas "
            "carpetas hermanas en el contenedor -- el problema no era solo el requirements.txt.",
            "Reverse-engineer la mutation de GraphQL de Railway para setear Root Directory por "
            "API directa -- descartada por riesgo de tocar infra de produccion a ciegas sin "
            "documentacion confirmada del schema; se opto por pedirle a Sebas el cambio manual "
            "de 2 clicks en el dashboard.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
