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

export async function cerrarSesionConductor(sessionId: string): Promise<{ leccion_guardada: boolean; id: string | null }> {
  const res = await fetch(`${API_URL}/conductor/sesiones/${sessionId}/cerrar`, { method: "POST" });
  if (!res.ok) throw new Error(`No se pudo cerrar la sesión (${res.status})`);
  return res.json();
}

// `sendBeacon` (no fetch) porque se llama desde `beforeunload` — a esa altura el browser puede
// matar cualquier fetch en curso antes de que salga; sendBeacon está pensado justo para esto
// (entrega best-effort, no garantizada, pero no bloquea ni se cancela al cerrar la pestaña).
export function cerrarSesionConductorBeacon(sessionId: string): void {
  navigator.sendBeacon(`${API_URL}/conductor/sesiones/${sessionId}/cerrar`, new Blob());
}

// ── Chat con un especialista puntual (Etapa 10) ─────────────────────────────────
// Distinto del Conductor: acá se habla directo con un especialista sobre un frente concreto —
// mismo conocimiento/herramientas, pero sin producir un documento_caso formal (eso sigue siendo
// exclusivo de correr_especialista vía el Conductor).

export const ESPECIALISTAS = [
  { nombre: "microbiologo", label: "Microbiólogo" },
  { nombre: "ingeniero_ambiental", label: "Ingeniero Ambiental" },
  { nombre: "agronomo", label: "Ingeniero Agrónomo" },
] as const;

export async function crearSesionEspecialista(nombre: string, frenteId: string): Promise<string> {
  const res = await fetch(`${API_URL}/especialistas/${nombre}/sesiones`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ frente_id: frenteId }),
  });
  if (!res.ok) {
    const detalle = await res.json().catch(() => ({}));
    throw new Error(detalle.detail || `No se pudo crear la sesión (${res.status})`);
  }
  const data = await res.json();
  return data.session_id as string;
}

export async function enviarMensajeEspecialista(sessionId: string, texto: string): Promise<string> {
  const res = await fetch(`${API_URL}/especialistas/sesiones/${sessionId}/mensajes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ texto }),
  });
  if (!res.ok) {
    const detalle = await res.json().catch(() => ({}));
    throw new Error(detalle.detail || `El especialista respondió ${res.status}`);
  }
  const data = await res.json();
  return data.respuesta as string;
}
