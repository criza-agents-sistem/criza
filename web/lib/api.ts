// Cliente delgado de la API de CRIZA (api/main.py, Etapa 6) — server components hacen fetch
// directo acá, sin capa de estado cliente para las páginas de solo lectura v1.

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type CasoResumen = {
  id: string;
  nombre: string;
  descripcion: string;
  estadio: string | null;
};

export type Documento = {
  id: string;
  titulo: string | null;
  modo: string | null;
  estado: string | null;
  agente?: string | null;
  contenido?: string | null;
};

export type ArtefactoExterno = {
  id: string;
  titulo: string | null;
  tipo: string | null;
  url: string | null;
};

export type Frente = {
  id: string;
  nombre: string | null;
  estado: string | null;
  documentos: Documento[];
  artefactos_externos: ArtefactoExterno[];
};

export type Pendiente = {
  id: string;
  descripcion: string | null;
  estado: string | null;
};

export type CasoDetalle = {
  id: string;
  nombre: string;
  descripcion: string;
  estadio: string | null;
  fecha_inicio: string | null;
  participantes: { usuario_nombre: string; rol_en_caso: string }[];
  frentes: Frente[];
  pendientes: Pendiente[];
};

async function apiFetch<T>(path: string): Promise<T | null> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`API ${path} respondió ${res.status}`);
  return res.json();
}

export function listarCasos(): Promise<CasoResumen[] | null> {
  return apiFetch<CasoResumen[]>("/casos");
}

export function obtenerCaso(id: string): Promise<CasoDetalle | null> {
  return apiFetch<CasoDetalle>(`/casos/${id}`);
}

export function obtenerDocumento(id: string): Promise<Documento | null> {
  return apiFetch<Documento>(`/documentos/${id}`);
}

// ── Conductor (chat) ─────────────────────────────────────────────────────────
// A diferencia de listarCasos/obtenerCaso/obtenerDocumento (server components, GET,
// cache: "no-store"), estas se llaman desde un client component — el Conductor puede tardar
// varios minutos si invoca un especialista, y necesita mantener la sesión entre mensajes.

export async function crearSesionConductor(): Promise<string> {
  const res = await fetch(`${API_URL}/conductor/sesiones`, { method: "POST" });
  if (!res.ok) throw new Error(`No se pudo crear la sesión del Conductor (${res.status})`);
  const data = await res.json();
  return data.session_id as string;
}

export async function enviarMensajeConductor(sessionId: string, texto: string): Promise<string> {
  const res = await fetch(`${API_URL}/conductor/sesiones/${sessionId}/mensajes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ texto }),
  });
  if (!res.ok) {
    const detalle = await res.json().catch(() => ({}));
    throw new Error(detalle.detail || `El Conductor respondió ${res.status}`);
  }
  const data = await res.json();
  return data.respuesta as string;
}
