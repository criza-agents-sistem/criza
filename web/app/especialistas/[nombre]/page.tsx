"use client";

import { use, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { crearSesionEspecialista, enviarMensajeEspecialista, ESPECIALISTAS } from "@/lib/api";

type Turno = { rol: "vos" | "especialista" | "error"; texto: string };

export default function EspecialistaChatPage({
  params,
}: {
  params: Promise<{ nombre: string }>;
}) {
  const { nombre } = use(params);
  const searchParams = useSearchParams();
  const frenteId = searchParams.get("frente");
  const label = ESPECIALISTAS.find((e) => e.nombre === nombre)?.label ?? nombre;

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [turnos, setTurnos] = useState<Turno[]>([]);
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [errorSesion, setErrorSesion] = useState<string | null>(null);
  const finRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!frenteId) {
      setErrorSesion("Falta el frente sobre el que hablar — entrá a este chat desde la página de un caso.");
      return;
    }
    crearSesionEspecialista(nombre, frenteId)
      .then(setSessionId)
      .catch((e) => setErrorSesion(e.message));
  }, [nombre, frenteId]);

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
      const respuesta = await enviarMensajeEspecialista(sessionId, mensaje);
      setTurnos((t) => [...t, { rol: "especialista", texto: respuesta }]);
    } catch (e) {
      setTurnos((t) => [...t, { rol: "error", texto: e instanceof Error ? e.message : "Error desconocido" }]);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="flex h-[calc(100vh-140px)] flex-col">
      <div className="mb-1 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{label}</h1>
        <a
          href={`/agentes/${nombre}`}
          target="_blank"
          rel="noreferrer"
          className="rounded-lg border border-neutral-300 px-3 py-1.5 text-sm text-neutral-600 hover:bg-neutral-50"
        >
          ℹ️ Características
        </a>
      </div>
      <p className="mb-4 text-sm text-neutral-500">
        Chat directo con el especialista sobre este frente — mismo conocimiento que una corrida
        formal, pero esto NO produce un documento persistido. Para eso, pedíselo al Conductor.
      </p>

      {errorSesion && (
        <p className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {errorSesion}
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
                {t.rol === "especialista" ? (
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{t.texto}</ReactMarkdown>
                ) : (
                  t.texto
                )}
              </div>
            </div>
          ))}
          {enviando && (
            <div className="self-start rounded-lg bg-neutral-100 px-4 py-2 text-sm text-neutral-400">
              Pensando...
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
