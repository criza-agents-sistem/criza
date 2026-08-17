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

// Etapa 14 (2026-08-17) — descargar el informe como .md. Link directo (<a href>), no fetch: el
// Content-Disposition del server dispara la descarga, no hace falta JS del lado del cliente.
export function urlDescargaDocumento(id: string): string {
  return `${API_URL}/documentos/${id}/descargar`;
}

// Etapa 15 (2026-08-17) — elegir modelo por sesión de chat. Lista curada, ver
// utils/ai_client.py::MODELOS_DISPONIBLES (única fuente, esto solo la lee).
export type ModeloDisponible = {
  id: string;
  nombre: string;
  nota: string;
};

export function listarModelos(): Promise<ModeloDisponible[] | null> {
  return apiFetch<ModeloDisponible[]>("/modelos");
}

// Etapa 13 (2026-08-17) — crear un caso, no solo leerlos. Client component (formulario), por
// eso devuelve/lanza en vez de usar apiFetch (que trata 404 como "no encontrado", no aplica acá).
export async function crearCaso(input: {
  nombre: string;
  descripcion: string;
  estadio?: string;
  fecha_inicio?: string;
  notas?: string;
}): Promise<string> {
  const res = await fetch(`${API_URL}/casos`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) {
    const detalle = await res.json().catch(() => ({}));
    throw new Error(detalle.detail || `No se pudo crear el caso (${res.status})`);
  }
  const data = await res.json();
  return data.caso_id as string;
}

// Etapa 16 (2026-08-17) — historial de conversaciones. Bug real: la página creaba una sesión
// nueva en cada carga sin guardar el session_id en ningún lado del browser, así que volver más
// tarde a /conductor mostraba un chat vacío aunque la conversación anterior seguía intacta en
// el KM. Estas funciones son la mitad "encontrarla" del fix (la otra mitad, recordar la sesión
// activa entre cargas, vive en las páginas de chat vía localStorage).
export type TurnoPersistido = { rol: "vos" | "conductor" | "especialista"; texto: string };

export type SesionResumen = {
  id: string;
  iniciada_en: string | null;
  actualizada_en: string | null;
  primer_mensaje: string;
  modelo: string | null;
};

export function listarSesionesConductor(): Promise<SesionResumen[] | null> {
  return apiFetch<SesionResumen[]>("/conductor/sesiones");
}

export type SesionConductorDetalle = { id: string; modelo: string | null; turnos: TurnoPersistido[] };

export function obtenerSesionConductor(id: string): Promise<SesionConductorDetalle | null> {
  return apiFetch<SesionConductorDetalle>(`/conductor/sesiones/${id}`);
}

export type SesionEspecialistaResumen = SesionResumen & { frente_id: string | null };

export function listarSesionesEspecialista(nombre: string): Promise<SesionEspecialistaResumen[] | null> {
  return apiFetch<SesionEspecialistaResumen[]>(`/especialistas/sesiones?especialista=${encodeURIComponent(nombre)}`);
}

export type SesionEspecialistaDetalle = {
  id: string;
  especialista: string;
  frente_id: string | null;
  modelo: string | null;
  turnos: TurnoPersistido[];
};

export function obtenerSesionEspecialista(id: string): Promise<SesionEspecialistaDetalle | null> {
  return apiFetch<SesionEspecialistaDetalle>(`/especialistas/sesiones/${id}`);
}

// ── Conductor (chat) ─────────────────────────────────────────────────────────
// A diferencia de listarCasos/obtenerCaso/obtenerDocumento (server components, GET,
// cache: "no-store"), estas se llaman desde un client component — el Conductor puede tardar
// varios minutos si invoca un especialista, y necesita mantener la sesión entre mensajes.

// modelo ausente/undefined = default del agente (Etapa 15) — ver listarModelos().
export async function crearSesionConductor(modelo?: string): Promise<string> {
  const res = await fetch(`${API_URL}/conductor/sesiones`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(modelo ? { modelo } : {}),
  });
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

// frenteId ausente = "consulta libre" (Etapa 12) — sin caso, sin ese contexto que armar.
// modelo ausente/undefined = default del agente (Etapa 15) — ver listarModelos().
export async function crearSesionEspecialista(nombre: string, frenteId?: string, modelo?: string): Promise<string> {
  const res = await fetch(`${API_URL}/especialistas/${nombre}/sesiones`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...(frenteId ? { frente_id: frenteId } : {}),
      ...(modelo ? { modelo } : {}),
    }),
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

// ── Características de un agente (Etapa 11) ─────────────────────────────────────
// Leído en vivo desde TOOLS/SYSTEM_PROMPT del módulo del agente en el server — no un doc
// paralelo, se actualiza solo cuando cambian las herramientas o el prompt.

export type ToolInfo = {
  name: string;
  description: string;
  disponible_en_chat: boolean;
};

export type InfoAgente = {
  nombre: string;
  system_prompt: string;
  tools: ToolInfo[];
};

export function obtenerInfoAgente(nombre: string): Promise<InfoAgente | null> {
  return apiFetch<InfoAgente>(`/agentes/${nombre}`);
}
