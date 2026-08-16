"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { crearSesionConductor, enviarMensajeConductor } from "@/lib/api";

type Turno = { rol: "vos" | "conductor" | "error"; texto: string };

export default function ConductorPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [turnos, setTurnos] = useState<Turno[]>([]);
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [errorSesion, setErrorSesion] = useState<string | null>(null);
  const finRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    crearSesionConductor()
      .then(setSessionId)
      .catch((e) => setErrorSesion(e.message));
  }, []);

  useEffect(() => {
    finRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turnos, enviando]);

  async function enviar() {
    const mensaje = texto.trim();
    if (!mensaje || !sessionId || enviando) return;

    setTurnos((t) => [...t, { rol: "vos", texto: mensaje }]);
    setTexto("");
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
      <h1 className="text-2xl font-semibold mb-1">Conductor</h1>
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
          {turnos.map((t, i) => (
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
          ))}
          {enviando && (
            <div className="self-start rounded-lg bg-neutral-100 px-4 py-2 text-sm text-neutral-400">
              Pensando... (puede tardar unos minutos si invoca un especialista)
            </div>
          )}
        </div>
        <div ref={finRef} />
      </div>

      <div className="mt-4 flex gap-2">
        <input
          className="flex-1 rounded-lg border border-neutral-300 px-4 py-2 text-sm focus:border-neutral-500 focus:outline-none"
          placeholder="Escribí un mensaje..."
          value={texto}
          disabled={!sessionId || enviando}
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              enviar();
            }
          }}
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
