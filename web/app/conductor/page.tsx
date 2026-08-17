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
  type ModeloDisponible,
} from "@/lib/api";

type Turno = { rol: "vos" | "conductor" | "error" | "sistema"; texto: string };

export default function ConductorPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [turnos, setTurnos] = useState<Turno[]>([]);
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [cerrandoSesion, setCerrandoSesion] = useState(false);
  const [errorSesion, setErrorSesion] = useState<string | null>(null);
  const [modelos, setModelos] = useState<ModeloDisponible[]>([]);
  const [modeloElegido, setModeloElegido] = useState("");
  const finRef = useRef<HTMLDivElement>(null);
  const sessionIdRef = useRef<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    crearSesionConductor()
      .then((id) => {
        setSessionId(id);
        sessionIdRef.current = id;
      })
      .catch((e) => setErrorSesion(e.message));
    listarModelos().then((lista) => setModelos(lista ?? []));
  }, []);

  // Elegir modelo solo tiene sentido antes del primer mensaje (Etapa 15) — el modelo queda
  // fijado por sesión al crearla. Si ya hay conversación, cambiar exige "Nueva conversación".
  async function elegirModelo(modelo: string) {
    setModeloElegido(modelo);
    if (turnos.length > 0) return;
    const nuevoId = await crearSesionConductor(modelo || undefined).catch((e) => {
      setErrorSesion(e.message);
      return null;
    });
    setSessionId(nuevoId);
    sessionIdRef.current = nuevoId;
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
    const nuevoId = await crearSesionConductor(modeloElegido || undefined).catch((e) => {
      setErrorSesion(e.message);
      return null;
    });
    setSessionId(nuevoId);
    sessionIdRef.current = nuevoId;
    setTurnos([]);
    setCerrandoSesion(false);
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
