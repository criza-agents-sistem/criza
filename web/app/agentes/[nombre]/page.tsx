import { notFound } from "next/navigation";
import { obtenerInfoAgente, ESPECIALISTAS } from "@/lib/api";

const LABELS: Record<string, string> = {
  conductor: "Conductor",
  ...Object.fromEntries(ESPECIALISTAS.map((e) => [e.nombre, e.label])),
};

export default async function AgenteInfoPage({
  params,
}: {
  params: Promise<{ nombre: string }>;
}) {
  const { nombre } = await params;
  const info = await obtenerInfoAgente(nombre);
  if (!info) notFound();

  const label = LABELS[nombre] ?? nombre;

  return (
    <div>
      <h1 className="text-2xl font-semibold mb-1">{label}</h1>
      <p className="mb-6 text-sm text-neutral-500">
        Leído en vivo del código del agente — se actualiza solo cuando cambian sus herramientas o
        su prompt, no es un documento que alguien tenga que mantener a mano.
      </p>

      <section className="mb-8">
        <h2 className="text-lg font-medium mb-3">Herramientas ({info.tools.length})</h2>
        <div className="flex flex-col gap-3">
          {info.tools.map((tool) => (
            <div key={tool.name} className="rounded-lg border border-neutral-200 bg-white p-4">
              <div className="flex items-center justify-between gap-2">
                <code className="text-sm font-medium">{tool.name}</code>
                {!tool.disponible_en_chat && (
                  <span
                    className="shrink-0 rounded-full bg-amber-50 border border-amber-200 px-2 py-0.5 text-xs text-amber-700"
                    title="Solo se usa en la corrida formal vía la costura — no disponible en el chat directo"
                  >
                    solo corrida formal
                  </span>
                )}
              </div>
              <p className="mt-1 text-sm text-neutral-600">{tool.description}</p>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-lg font-medium mb-3">Instrucciones (system prompt)</h2>
        <pre className="whitespace-pre-wrap rounded-lg border border-neutral-200 bg-neutral-50 p-4 text-xs text-neutral-700 max-h-[60vh] overflow-y-auto">
          {info.system_prompt}
        </pre>
      </section>
    </div>
  );
}
