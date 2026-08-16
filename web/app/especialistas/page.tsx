import Link from "next/link";
import { ESPECIALISTAS } from "@/lib/api";

export default function EspecialistasPage() {
  return (
    <div>
      <h1 className="text-2xl font-semibold mb-1">Especialistas</h1>
      <p className="mb-6 text-sm text-neutral-500">
        Para chatear con uno, entrá desde un caso (<Link href="/" className="text-blue-600 hover:underline">Casos</Link>) y elegí el frente sobre el que querés hablar — cada especialista necesita saber contra qué frente está trabajando. Acá podés ver qué puede hacer cada uno.
      </p>

      <div className="flex flex-col gap-3">
        {ESPECIALISTAS.map((esp) => (
          <Link
            key={esp.nombre}
            href={`/agentes/${esp.nombre}`}
            className="block rounded-lg border border-neutral-200 bg-white p-4 hover:border-neutral-300"
          >
            <h2 className="font-medium">{esp.label}</h2>
            <p className="mt-1 text-sm text-neutral-500">Ver características →</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
