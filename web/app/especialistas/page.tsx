import Link from "next/link";
import { ESPECIALISTAS } from "@/lib/api";

export default function EspecialistasPage() {
  return (
    <div>
      <h1 className="text-2xl font-semibold mb-1">Especialistas</h1>
      <p className="mb-6 text-sm text-neutral-500">
        "Consulta libre" es una pregunta puntual, sin caso asociado — rápida y barata en tokens.
        Para hablar sobre un caso real (con contexto completo), entrá desde ese caso
        (<Link href="/" className="text-blue-600 hover:underline">Casos</Link>) y elegí el frente.
      </p>

      <div className="flex flex-col gap-3">
        {ESPECIALISTAS.map((esp) => (
          <div key={esp.nombre} className="rounded-lg border border-neutral-200 bg-white p-4">
            <h2 className="font-medium">{esp.label}</h2>
            <div className="mt-2 flex gap-3 text-sm">
              <Link href={`/especialistas/${esp.nombre}`} className="text-blue-600 hover:underline">
                💬 Consulta libre
              </Link>
              <Link href={`/agentes/${esp.nombre}`} className="text-neutral-500 hover:underline">
                ℹ️ Características
              </Link>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
