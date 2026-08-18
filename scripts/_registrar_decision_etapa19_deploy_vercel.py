import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="web",
        titulo="Etapa 19 (cont.) -- deploy real del frontend en Vercel: organizacion GitHub, repo publico",
        decision=(
            "Continuacion de la decision de auth (mismo componente, sesion del 2026-08-17). Sebas "
            "pregunto si convenia armar una organizacion de GitHub en vez de dejar el repo en la "
            "cuenta personal sebasbizzi, para separar CRIZA de sus otros proyectos y no compartir "
            "limites gratuitos de Vercel/Railway. Creada la organizacion criza-agents-sistem "
            "(GitHub), repo transferido ahi via gh api (sebasbizzi/criza -> "
            "criza-agents-sistem/criza), remote local actualizado. Intento de crear una cuenta de "
            "Vercel separada (criza.dev@gmail.com) para aislamiento total -- fallo real, "
            "documentado en detalle: el GitHub App de Vercel instalado en la organizacion nunca "
            "quedo vinculado a esa cuenta (multiples intentos: Add GitHub Account, reinstalar la "
            "app, sacar restriccion de OAuth app policy de la org -- ninguno resolvio). Al loguear "
            "esa sesion de browser via 'Continue with GitHub' como sebasbizzi, Vercel identifico y "
            "uso la cuenta personal ya existente (sebabizzi-7494's projects) en vez de crear una "
            "nueva -- se abandono el objetivo de cuenta 100% separada, aceptado explicitamente por "
            "Sebas ('lo dejemos por ahora') dado el costo ya invertido en diagnosticar. Bloqueador "
            "real encontrado ahi: Vercel Hobby (gratis) no permite deployar desde una organizacion "
            "PRIVADA de GitHub ('Deploying from a private GitHub organization requires a Vercel "
            "Pro plan') -- explica retroactivamente por que ningun intento anterior de vincular la "
            "organizacion funcionaba, no era un problema de permisos sino de plan. Sebas eligio "
            "explicitames entre 3 opciones (pasar a Pro / repo publico / volver a cuenta personal "
            "de GitHub) -- eligio repo publico (opcion 1): sin secretos reales expuestos (API keys "
            "en .env, gitignored), mantiene la organizacion, sigue gratis. Repo pasado a publico "
            "via gh api. Proyecto Vercel creado (equipo sebabizzi-7494's projects, rootDirectory "
            "web). Dos bugs reales encontrados y resueltos durante la verificacion: (1) el primer "
            "deploy quedo con Framework Preset 'Other' en vez de 'Next.js' -- el cambio de Root "
            "Directory de './' a 'web' en el wizard no re-disparo la deteccion automatica de "
            "framework, causando 404 NOT_FOUND en TODAS las rutas (confirmado con "
            "framework:null en el proyecto y X-Vercel-Error:NOT_FOUND en cada request, sin logs "
            "de la app -- el pedido nunca llegaba a Next.js). Arreglado corrigiendo el preset a "
            "mano en Settings y forzando un redeploy. (2) Vercel Authentication (SSO Protection), "
            "activada por default en proyectos nuevos, bloqueaba el dominio *.vercel.app a nivel "
            "de plataforma -- desactivada porque el proyecto ya tiene su propia barrera "
            "(SITE_AUTH_USER/PASSWORD via web/proxy.ts, Decision O) y las dos juntas eran "
            "redundantes. Verificado real: https://criza-chi.vercel.app responde 401 "
            "'Autenticacion requerida' (nuestro proxy.ts funcionando), confirmando el frontend "
            "esta desplegado y sirviendo correctamente. Pendiente, no bloqueante para cerrar esta "
            "sesion: NEXT_PUBLIC_API_URL sigue apuntando a localhost -- el sitio publico no puede "
            "hablar con el backend real todavia. Backend (api/) sigue sin desplegar en Railway. "
            "Sebas pidio explicitamente cerrar la sesion aca y continuar Railway + wiring de URLs "
            "reales en la proxima sesion."
        ),
        motivo=(
            "Sebas: 'Vercel podemos usar una cuenta nueva solo para criza' -> tras el bloqueo real "
            "de plan, eligio explicitamente 'repo publico' entre 3 opciones presentadas (Pro / "
            "publico / cuenta personal de GitHub)."
        ),
        alternativas_consideradas=[
            "Pasar a Vercel Pro -- descartada explicitamente por Sebas ('no quiero pasar a pro'), "
            "es plata y no estaba planeado.",
            "Volver a un repo bajo una cuenta personal de GitHub (no organizacion) -- no elegida: "
            "hubiera mantenido el repo privado y gratis, pero perdia la estructura de organizacion "
            "recien armada.",
            "Cuenta de Vercel 100% separada (criza.dev@gmail.com) para aislamiento total de "
            "limites gratuitos -- abandonada tras diagnostico extenso sin exito; el login via "
            "GitHub siempre resuelve a la cuenta personal ya existente de sebasbizzi. Documentado "
            "como limitacion conocida, no como bug propio a resolver.",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
