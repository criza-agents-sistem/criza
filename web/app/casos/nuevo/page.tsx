"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { crearCaso } from "@/lib/api";

export default function NuevoCasoPage() {
  const router = useRouter();
  const [nombre, setNombre] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [estadio, setEstadio] = useState("");
  const [notas, setNotas] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function enviar() {
    if (!nombre.trim() || !descripcion.trim() || enviando) return;
    setEnviando(true);
    setError(null);
    try {
      const casoId = await crearCaso({
        nombre: nombre.trim(),
        descripcion: descripcion.trim(),
        estadio: estadio.trim() || undefined,
        notas: notas.trim() || undefined,
      });
      router.push(`/casos/${casoId}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error desconocido");
      setEnviando(false);
    }
  }

  return (
    <div className="max-w-xl">
      <h1 className="text-2xl font-semibold mb-1">Nuevo caso</h1>
      <p className="mb-6 text-sm text-neutral-500">
        Nombre y descripción son lo único obligatorio — el resto se puede completar después.
        Podés sumar frentes una vez creado el caso.
      </p>

      {error && (
        <p className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </p>
      )}

      <div className="flex flex-col gap-4">
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium">Nombre *</span>
          <input
            className="rounded-lg border border-neutral-300 px-3 py-2 text-sm focus:border-neutral-500 focus:outline-none"
            placeholder="ej. Efluentes biogás (Helios)"
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
          />
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium">Descripción *</span>
          <textarea
            className="min-h-28 rounded-lg border border-neutral-300 px-3 py-2 text-sm focus:border-neutral-500 focus:outline-none"
            placeholder="Quién, qué problema, contexto relevante..."
            value={descripcion}
            onChange={(e) => setDescripcion(e.target.value)}
          />
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium">Estadío</span>
          <input
            className="rounded-lg border border-neutral-300 px-3 py-2 text-sm focus:border-neutral-500 focus:outline-none"
            placeholder="ej. desde_cero, validado_escalando"
            value={estadio}
            onChange={(e) => setEstadio(e.target.value)}
          />
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium">Notas</span>
          <textarea
            className="min-h-20 rounded-lg border border-neutral-300 px-3 py-2 text-sm focus:border-neutral-500 focus:outline-none"
            placeholder="Opcional"
            value={notas}
            onChange={(e) => setNotas(e.target.value)}
          />
        </label>

        <button
          className="self-start rounded-lg bg-neutral-900 px-4 py-2 text-sm text-white disabled:opacity-40"
          disabled={!nombre.trim() || !descripcion.trim() || enviando}
          onClick={enviar}
        >
          {enviando ? "Creando..." : "Crear caso"}
        </button>
      </div>
    </div>
  );
}
