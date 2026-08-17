"use client";

import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  crearSesionConductor,
  enviarMensajeConductor,
  cerrarSesionConductor,
  cerrarSesionConductorBeacon,
  listarModelos,
  listarSesionesConductor,
  obtenerSesionConductor,
  type ModeloDisponible,
  type SesionResumen,
} from "@/lib/api";

type Turno = { rol: "vos" | "conductor" | "error" | "sistema"; texto: string };

// Etapa 16 (2026-08-17) — bug real: Sebas volvió a /conductor más tarde y la respuesta que había
// recibido "desapareció". La página creaba una sesión nueva en cada carga sin guardar el
// session_id en ningún lado del browser — la conversación seguía intacta en el KM, pero no había
// forma de volver a encontrarla. Guardamos acá el id de la sesión activa para sobrevivir a un
// refresh, y el botón "Historial" (abajo) cubre el resto de los casos (otro navegador, localStorage
// borrado, etc.) leyendo directo del KM.
const SESSION_STORAGE_KEY = "criza_conductor_session_id";

function formatearFecha(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString("es-AR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export default function ConductorPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [turnos, setTurnos] = useState<Turno[]>([]);
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [cerrandoSesion, setCerrandoSesion] = useState(false);
  const [errorSesion, setErrorSesion] = useState<string | null>(null);
  const [modelos, setModelos] = useState<ModeloDisponible[]>([]);
  const [modeloElegido, setModeloElegido] = useState("");
  const [mostrarHistorial, setMostrarHistorial] = useState(false);
  const [historial, setHistorial] = useState<SesionResumen[]>([]);
  const [cargandoHistorial, setCargandoHistorial] = useState(false);
  const finRef = useRef<HTMLDivElement>(null);
  const sessionIdRef = useRef<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function guardarSesionActiva(id: string | null) {
    setSessionId(id);
    sessionIdRef.current = id;
    if (id) localStorage.setItem(SESSION_STORAGE_KEY, id);
    else localStorage.removeItem(SESSION_STORAGE_KEY);
  }

  async function crearYGuardarSesion(modelo?: string) {
    const id = await crearSesionConductor(modelo).catch((e) => {
      setErrorSesion(e.message);
      return null;
    });
    guardarSesionActiva(id);
    return id;
  }

  useEffect(() => {
    const guardada = localStorage.getItem(SESSION_STORAGE_KEY);
    if (guardada) {
      obtenerSesionConductor(guardada)
        .then((detalle) => {
          if (!detalle) {
            crearYGuardarSesion();
            return;
          }
          guardarSesionActiva(guardada);
          setModeloElegido(detalle.modelo ?? "");
          setTurnos(detalle.turnos.map((t) => ({ rol: t.rol as Turno["rol"], texto: t.texto })));
        })
        .catch(() => crearYGuardarSesion());
    } else {
      crearYGuardarSesion();
    }
    listarModelos().then((lista) => setModelos(lista ?? []));
  }, []);

  // Elegir modelo solo tiene sentido antes del primer mensaje (Etapa 15) — el modelo queda
  // fijado por sesión al crearla. Si ya hay conversación, cambiar exige "Nueva conversación".
  async function elegirModelo(modelo: string) {
    setModeloElegido(modelo);
    if (turnos.length > 0) return;
    await crearYGuardarSesion(modelo || undefined);
  }

  // Best-effort: si Sebas cierra la pestaña sin apretar "Nueva conversación", igual intentamos
  // evaluar la lección — sendBeacon no garantiza entrega, pero es lo más confiable disponible
  // en beforeunload (un fetch normal puede cortarse antes de salir).
  useEffect(() => {
    function alCerrar() {
      if (sessionIdRef.current) cerrarSesionConductorBeacon(sessionIdRef.current);
    }
    window.addEventListener("beforeunload", alCerrar);
    return () => window.removeEventListener("beforeunload", alCerrar);
  }, []);

  useEffect(() => {
    finRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turnos, enviando]);

  async function nuevaConversacion() {
    if (!sessionId || cerrandoSesion) return;
    setCerrandoSesion(true);
    try {
      const { leccion_guardada } = await cerrarSesionConductor(sessionId);
      if (leccion_guardada) {
        setTurnos((t) => [...t, { rol: "sistema", texto: "📝 El Conductor guardó una lección nueva de esta conversación." }]);
      }
    } catch {
      // best-effort — si falla, igual arrancamos la conversación nueva
    }
    await crearYGuardarSesion(modeloElegido || undefined);
    setTurnos([]);
    setCerrandoSesion(false);
  }

  async function toggleHistorial() {
    const abrir = !mostrarHistorial;
    setMostrarHistorial(abrir);
    if (!abrir) return;
    setCargandoHistorial(true);
    const lista = await listarSesionesConductor().catch(() => null);
    setHistorial(lista ?? []);
    setCargandoHistorial(false);
  }

  async function abrirSesionHistorial(id: string) {
    const detalle = await obtenerSesionConductor(id).catch((e) => {
      setErrorSesion(e.message);
      return null;
    });
    if (!detalle) return;
    guardarSesionActiva(id);
    setModeloElegido(detalle.modelo ?? "");
    setTurnos(detalle.turnos.map((t) => ({ rol: t.rol as Turno["rol"], texto: t.texto })));
    setMostrarHistorial(false);
  }

  function manejarTecla(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      enviar();
    }
    // Shift+Enter: comportamiento por default del textarea (salto de línea), no hace falta nada acá.
  }

  async function enviar() {
    const mensaje = texto.trim();
    if (!mensaje || !sessionId || enviando) return;

    setTurnos((t) => [...t, { rol: "vos", texto: mensaje }]);
    setTexto("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    setEnviando(true);
    try {
      const respuesta = await enviarMensajeConductor(sessionId, mensaje);
      setTurnos((t) => [...t, { rol: "conductor", texto: respuesta }]);
    } catch (e) {
      setTurnos((t) => [...t, { rol: "error", texto: e instanceof Error ? e.message : "Error desconocido" }]);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="flex h-[calc(100vh-140px)] flex-col">
      <div className="mb-1 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Conductor</h1>
        <div className="flex items-center gap-2">
          <select
            className="rounded-lg border border-neutral-300 px-2 py-1.5 text-sm text-neutral-600 disabled:opacity-40"
            value={modeloElegido}
            disabled={turnos.length > 0}
            title={turnos.length > 0 ? "Para cambiar de modelo, iniciá una nueva conversación" : "Modelo para esta conversación"}
            onChange={(e) => elegirModelo(e.target.value)}
          >
            <option value="">Modelo por defecto</option>
            {modelos.map((m) => (
              <option key={m.id} value={m.id}>
                {m.nombre}
              </option>
            ))}
          </select>
          <a
            href="/agentes/conductor"
            target="_blank"
            rel="noreferrer"
            className="rounded-lg border border-neutral-300 px-3 py-1.5 text-sm text-neutral-600 hover:bg-neutral-50"
          >
            ℹ️ Características
          </a>
          <div className="relative">
            <button
              className="rounded-lg border border-neutral-300 px-3 py-1.5 text-sm text-neutral-600 hover:bg-neutral-50"
              onClick={toggleHistorial}
            >
              🕘 Historial
            </button>
            {mostrarHistorial && (
              <div className="absolute right-0 z-10 mt-2 max-h-96 w-96 overflow-y-auto rounded-lg border border-neutral-200 bg-white p-2 shadow-lg">
                {cargandoHistorial ? (
                  <p className="p-2 text-sm text-neutral-400">Cargando...</p>
                ) : historial.length === 0 ? (
                  <p className="p-2 text-sm text-neutral-400">Todavía no hay conversaciones guardadas.</p>
                ) : (
                  historial.map((s) => (
                    <button
                      key={s.id}
                      className={`block w-full rounded-lg px-3 py-2 text-left text-sm hover:bg-neutral-50 ${s.id === sessionId ? "bg-neutral-50" : ""}`}
                      onClick={() => abrirSesionHistorial(s.id)}
                    >
                      <div className="truncate text-neutral-800">{s.primer_mensaje}</div>
                      <div className="text-xs text-neutral-400">{formatearFecha(s.actualizada_en)}</div>
                    </button>
                  ))
                )}
              </div>
            )}
          </div>
          <button
            className="rounded-lg border border-neutral-300 px-3 py-1.5 text-sm text-neutral-600 hover:bg-neutral-50 disabled:opacity-40"
            disabled={!sessionId || cerrandoSesion || turnos.length === 0}
            onClick={nuevaConversacion}
          >
            {cerrandoSesion ? "Cerrando..." : "Nueva conversación"}
          </button>
        </div>
      </div>
      <p className="mb-4 text-sm text-neutral-500">
        Puede invocar especialistas cuando se lo pedís — eso gasta tokens reales y escribe al KM.
      </p>

      {errorSesion && (
        <p className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          No se pudo conectar con la API ({errorSesion}). ¿Está corriendo <code>python api/run.py</code>?
        </p>
      )}

      <div className="flex-1 overflow-y-auto rounded-lg border border-neutral-200 bg-white p-4">
        {turnos.length === 0 && !errorSesion && (
          <p className="text-sm text-neutral-400">
            {sessionId ? "Escribí un mensaje para arrancar." : "Conectando..."}
          </p>
        )}
        <div className="flex flex-col gap-4">
          {turnos.map((t, i) =>
            t.rol === "sistema" ? (
              <div key={i} className="self-center rounded-lg bg-amber-50 border border-amber-200 px-3 py-1.5 text-xs text-amber-800">
                {t.texto}
              </div>
            ) : (
              <div key={i} className={t.rol === "vos" ? "self-end max-w-[80%]" : "self-start max-w-[80%]"}>
                <div
                  className={
                    t.rol === "vos"
                      ? "rounded-lg bg-neutral-900 px-4 py-2 text-sm text-white"
                      : t.rol === "error"
                        ? "rounded-lg bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-700"
                        : "prose prose-sm max-w-none rounded-lg bg-neutral-100 px-4 py-2"
                  }
                >
                  {t.rol === "conductor" ? (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{t.texto}</ReactMarkdown>
                  ) : (
                    t.texto
                  )}
                </div>
              </div>
            )
          )}
          {enviando && (
            <div className="self-start rounded-lg bg-neutral-100 px-4 py-2 text-sm text-neutral-400">
              Pensando... (puede tardar unos minutos si invoca un especialista)
            </div>
          )}
        </div>
        <div ref={finRef} />
      </div>

      <div className="mt-4 flex items-end gap-2">
        <textarea
          ref={textareaRef}
          className="max-h-48 min-h-[42px] flex-1 resize-none overflow-y-auto rounded-lg border border-neutral-300 px-4 py-2 text-sm leading-normal focus:border-neutral-500 focus:outline-none"
          placeholder="Escribí un mensaje... (Shift+Enter para salto de línea)"
          rows={1}
          value={texto}
          disabled={!sessionId || enviando}
          onChange={(e) => {
            setTexto(e.target.value);
            const el = e.target;
            el.style.height = "auto";
            el.style.height = `${el.scrollHeight}px`;
          }}
          onKeyDown={manejarTecla}
        />
        <button
          className="rounded-lg bg-neutral-900 px-4 py-2 text-sm text-white disabled:opacity-40"
          disabled={!sessionId || enviando || !texto.trim()}
          onClick={enviar}
        >
          Enviar
        </button>
      </div>
    </div>
  );
}
