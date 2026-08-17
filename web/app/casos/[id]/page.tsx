import Link from "next/link";
import { notFound } from "next/navigation";
import { obtenerCaso, ESPECIALISTAS } from "@/lib/api";

export default async function CasoDetallePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const caso = await obtenerCaso(id);
  if (!caso) notFound();

  return (
    <div>
      <Link href="/" className="text-sm text-neutral-500 hover:underline">
        ← Casos
      </Link>

      <div className="mt-2 flex items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold">{caso.nombre}</h1>
        {caso.estadio && (
          <span className="shrink-0 rounded-full bg-neutral-100 px-2.5 py-0.5 text-xs text-neutral-600">
            {caso.estadio}
          </span>
        )}
      </div>
      {caso.descripcion && <p className="mt-2 text-neutral-600">{caso.descripcion}</p>}

      <section className="mt-8">
        <h2 className="text-lg font-medium mb-3">Frentes</h2>
        {caso.frentes.length === 0 ? (
          <p className="text-sm text-neutral-500">Sin frentes definidos todavía.</p>
        ) : (
          <div className="flex flex-col gap-4">
            {caso.frentes.map((frente) => (
              <div key={frente.id} className="rounded-lg border border-neutral-200 bg-white p-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-medium">{frente.nombre}</h3>
                  <span className="text-xs text-neutral-500">{frente.estado}</span>
                </div>

                {frente.documentos.length === 0 ? (
                  <p className="mt-2 text-sm text-neutral-400">Sin documentos producidos todavía.</p>
                ) : (
                  <ul className="mt-2 flex flex-col gap-1">
                    {frente.documentos.map((doc) => (
                      <li key={doc.id}>
                        <Link
                          href={`/documentos/${doc.id}`}
                          className="text-sm text-blue-600 hover:underline"
                        >
                          {doc.titulo} <span className="text-neutral-400">({doc.estado})</span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}

                <div className="mt-3 flex flex-wrap gap-2">
                  {ESPECIALISTAS.map((esp) => (
                    <Link
                      key={esp.nombre}
                      href={`/especialistas/${esp.nombre}?frente=${frente.id}`}
                      className="rounded-full border border-neutral-200 px-2.5 py-1 text-xs text-neutral-600 hover:bg-neutral-50"
                    >
                      💬 {esp.label}
                    </Link>
                  ))}
                </div>

                {frente.artefactos_externos.length > 0 && (
                  <ul className="mt-2 flex flex-col gap-1">
                    {frente.artefactos_externos.map((art) => (
                      <li key={art.id} className="text-sm">
                        <a
                          href={art.url ?? "#"}
                          target="_blank"
                          rel="noreferrer"
                          className="text-neutral-500 hover:underline"
                        >
                          ↗ {art.titulo} ({art.tipo})
                        </a>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="mt-8">
        <h2 className="text-lg font-medium mb-3">Pendientes</h2>
        {caso.pendientes.length === 0 ? (
          <p className="text-sm text-neutral-500">Sin pendientes registrados.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {caso.pendientes.map((p) => (
              <li key={p.id} className="flex items-start gap-2 text-sm">
                <span
                  className={
                    p.estado === "resuelto"
                      ? "mt-1 h-2 w-2 shrink-0 rounded-full bg-green-400"
                      : "mt-1 h-2 w-2 shrink-0 rounded-full bg-amber-400"
                  }
                />
                <span className={p.estado === "resuelto" ? "text-neutral-400 line-through" : ""}>
                  {p.descripcion}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
