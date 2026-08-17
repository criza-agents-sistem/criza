import Link from "next/link";
import { listarCasos } from "@/lib/api";

export default async function CasosPage() {
  const casos = await listarCasos();

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Casos</h1>
        <Link
          href="/casos/nuevo"
          className="rounded-lg bg-neutral-900 px-3 py-1.5 text-sm text-white hover:bg-neutral-800"
        >
          + Nuevo caso
        </Link>
      </div>

      {!casos || casos.length === 0 ? (
        <p className="text-neutral-500">No hay casos cargados todavía.</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {casos.map((caso) => (
            <li key={caso.id}>
              <Link
                href={`/casos/${caso.id}`}
                className="block rounded-lg border border-neutral-200 bg-white p-4 hover:border-neutral-400 transition-colors"
              >
                <div className="flex items-center justify-between gap-4">
                  <h2 className="font-medium">{caso.nombre}</h2>
                  {caso.estadio && (
                    <span className="shrink-0 rounded-full bg-neutral-100 px-2.5 py-0.5 text-xs text-neutral-600">
                      {caso.estadio}
                    </span>
                  )}
                </div>
                {caso.descripcion && (
                  <p className="mt-1 text-sm text-neutral-500 line-clamp-2">{caso.descripcion}</p>
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
