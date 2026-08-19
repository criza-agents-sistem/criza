// Proxy server-side hacia api/main.py (Railway) — agrega el Basic Auth de la API acá, nunca en
// el browser. Sin esto, cualquier fetch de un client component (conductor/page.tsx, formularios)
// le pegaría directo a Railway y la password de API_AUTH quedaría visible en el Network tab de
// cualquiera con la sesión del sitio abierta — le sacaría el sentido a tener API_AUTH como
// segunda capa separada de SITE_AUTH (ver web/proxy.ts). El browser sigue mandando el Basic Auth
// de SITE_AUTH acá porque este route vive en el mismo origen que el resto de la app — no hace
// falta código extra para eso, es el comportamiento normal del navegador con credenciales
// cacheadas para un origen.
import type { NextRequest } from "next/server";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function authHeaders(): HeadersInit {
  const user = process.env.API_AUTH_USER;
  const password = process.env.API_AUTH_PASSWORD;
  if (!user || !password) return {};
  const credenciales = Buffer.from(`${user}:${password}`).toString("base64");
  return { Authorization: `Basic ${credenciales}` };
}

async function reenviar(request: NextRequest, path: string[]): Promise<Response> {
  const destino = `${API_URL}/${path.join("/")}${request.nextUrl.search}`;

  const headers = new Headers(authHeaders());
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);

  const tieneBody = request.method !== "GET" && request.method !== "HEAD";

  const res = await fetch(destino, {
    method: request.method,
    headers,
    body: tieneBody ? await request.arrayBuffer() : undefined,
    cache: "no-store",
  });

  const resHeaders = new Headers();
  const contentTypeRes = res.headers.get("content-type");
  const contentDisposition = res.headers.get("content-disposition");
  if (contentTypeRes) resHeaders.set("content-type", contentTypeRes);
  if (contentDisposition) resHeaders.set("content-disposition", contentDisposition);

  return new Response(res.body, { status: res.status, headers: resHeaders });
}

export async function GET(request: NextRequest, ctx: RouteContext<"/api/backend/[...path]">) {
  const { path } = await ctx.params;
  return reenviar(request, path);
}

export async function POST(request: NextRequest, ctx: RouteContext<"/api/backend/[...path]">) {
  const { path } = await ctx.params;
  return reenviar(request, path);
}
