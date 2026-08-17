import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Etapa 19 (2026-08-17) — Sebas quiere hostear la web pública. Hoy no hay login real
// (config/plantillas/usuarios.yaml, un solo usuario) — sin esto, cualquiera que encuentre la URL
// vería casos reales (Helios, MicroBigs) y podría gastar tokens reales de la cuenta de Anthropic.
// Contraseña compartida simple (HTTP Basic Auth) como primera barrera — elegida explícitamente
// por Sebas sobre "sin login" y sobre "login real con usuario/contraseña" (más trabajo, no
// justificado todavía con un solo usuario real).
//
// Sin `SITE_AUTH_USER`/`SITE_AUTH_PASSWORD` configuradas (desarrollo local), no pide nada — el
// mismo criterio que ya usa la autenticación de la API (api/main.py).
const _USER = process.env.SITE_AUTH_USER;
const _PASSWORD = process.env.SITE_AUTH_PASSWORD;

function _tieneCredencialesValidas(request: NextRequest): boolean {
  const authHeader = request.headers.get("authorization");
  if (!authHeader?.startsWith("Basic ")) return false;
  try {
    const decoded = atob(authHeader.slice("Basic ".length));
    const separador = decoded.indexOf(":");
    if (separador === -1) return false;
    const user = decoded.slice(0, separador);
    const password = decoded.slice(separador + 1);
    return user === _USER && password === _PASSWORD;
  } catch {
    return false;
  }
}

export function proxy(request: NextRequest) {
  if (!_USER || !_PASSWORD) return NextResponse.next();

  if (_tieneCredencialesValidas(request)) return NextResponse.next();

  return new NextResponse("Autenticación requerida", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="CRIZA"' },
  });
}

export const config = {
  // Todo excepto assets estáticos — mismo patrón que la doc de Next.js 16 recomienda para no
  // bloquear CSS/JS/imágenes por accidente.
  matcher: "/((?!_next/static|_next/image|favicon.ico).*)",
};
