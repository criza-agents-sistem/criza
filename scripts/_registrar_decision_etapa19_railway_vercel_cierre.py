import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.km_decisiones import registrar_decision


async def main():
    r = await registrar_decision(
        componente="web",
        titulo="Etapa 19 (cierre) -- Vercel/Railway funcionando de punta a punta, verificado real por Sebas",
        decision=(
            "Continuacion directa de la decision componente=infra de mas temprano hoy (Root "
            "Directory, knowledge_module como dependencia git). Con el backend de Railway ya "
            "levantando bien, el primer login real contra produccion (criza-chi.vercel.app) tiro "
            "un 500 en la home. Runtime error real (Vercel): 'API /casos respondio 401' -- "
            "diagnostico: web/lib/api.ts nunca mando Authorization en ningun fetch a la API. Nunca "
            "se habia notado porque en local, sin API_AUTH_USER/PASSWORD seteadas, la API no pide "
            "nada (mismo criterio que proxy.ts) -- recien con el backend real deployado (hoy) se vio. "
            "Fix no trivial: lib/api.ts es isomorfico, lo importan tanto paginas server component "
            "(home) como el client component del Conductor (chat en el browser). Agregar la "
            "password de API_AUTH directo en el archivo la hubiera expuesto en el Network tab de "
            "cualquiera con la sesion del sitio abierta -- le sacaba el sentido a tener API_AUTH "
            "como capa separada de SITE_AUTH (decision original de Etapa 19 hosting). Sebas eligio "
            "explicitamente la opcion correcta (proxy server-side) sobre la rapida (header directo "
            "en el cliente) cuando se le presentaron ambas con el tradeoff real explicado. "
            "Implementado: web/app/api/backend/[...path]/route.ts -- Route Handler nuevo que "
            "reenvia a Railway agregando el Authorization del lado del servidor, nunca visible en "
            "el browser. web/lib/api.ts reescrito: en el server (typeof window === undefined) "
            "sigue pegandole directo a Railway con el auth armado ahi (process.env.API_AUTH_* no "
            "prefijado NEXT_PUBLIC_, Next.js lo reemplaza por undefined en el bundle del cliente, "
            "no hay forma de que se filtre); en el browser, todo pasa por el proxy propio (mismo "
            "origen) -- el navegador solo manda las credenciales de SITE_AUTH que ya tiene "
            "cacheadas para ese origen, comportamiento normal de HTTP Basic Auth, sin codigo extra. "
            "urlDescargaDocumento (link de descarga) y cerrarSesionConductorBeacon (sendBeacon no "
            "soporta headers propios) van siempre por el proxy sin excepcion, no solo en el caso "
            "isomorfico. API_AUTH_USER/PASSWORD agregadas a Vercel (production, sin prefijo "
            "NEXT_PUBLIC_), mismos valores que Railway. De paso, SITE_AUTH_USER/PASSWORD de Vercel "
            "no coincidian con lo que Sebas tenia guardado ('no funciona usuario y contrasena') -- "
            "reseteadas a credenciales nuevas conocidas, mismo patron que la reset de "
            "API_AUTH_PASSWORD de mas temprano. Build local (npm run build) limpio antes de tocar "
            "produccion. Verificado real: Sebas entro a criza-chi.vercel.app con las credenciales "
            "nuevas, confirmo 'entre y funciona muy bien' -- lista de casos real, chat del "
            "Conductor respondiendo. Cadena completa verificada de punta a punta: Vercel -> proxy "
            "-> Railway -> Neon produccion."
        ),
        motivo=(
            "Sebas, ante el tradeoff explicado (header directo mas rapido pero le saca sentido a "
            "API_AUTH como capa separada vs. proxy server-side mas correcto): 'Correcto: proxy "
            "server-side (Recomendado)' -- eligio la opcion que preserva la garantia de seguridad "
            "original en vez de la mas rapida."
        ),
        alternativas_consideradas=[
            "Header de Authorization directo en lib/api.ts, mandado tambien desde el browser -- "
            "descartada explicitamente por Sebas: funcionaba ya, pero exponia la password de "
            "API_AUTH en el Network tab a cualquiera con la sesion del sitio abierta, anulando el "
            "proposito original de tener esa capa separada de SITE_AUTH.",
            "Server components tambien via el proxy propio (en vez de directo a Railway) -- "
            "descartada por simplicidad y performance: hubiera necesitado resolver la URL propia "
            "del deployment (VERCEL_URL) para un fetch auto-referencial desde el server, un salto "
            "de red extra sin beneficio de seguridad real (el codigo server-side ya es seguro "
            "por diseño, nunca se bundlea para el cliente).",
        ],
        quien="Sebas + Claude",
    )
    print(r)


if __name__ == "__main__":
    asyncio.run(main())
