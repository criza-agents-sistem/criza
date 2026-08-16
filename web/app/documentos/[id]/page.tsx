import { notFound } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { obtenerDocumento } from "@/lib/api";

export default async function DocumentoPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const doc = await obtenerDocumento(id);
  if (!doc) notFound();

  return (
    <div>
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold">{doc.titulo}</h1>
        <span className="shrink-0 rounded-full bg-neutral-100 px-2.5 py-0.5 text-xs text-neutral-600">
          {doc.estado}
        </span>
      </div>
      {doc.agente && <p className="mt-1 text-sm text-neutral-500">Producido por: {doc.agente}</p>}

      <article className="prose prose-neutral prose-sm mt-6 max-w-none rounded-lg border border-neutral-200 bg-white p-6 leading-relaxed">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{doc.contenido}</ReactMarkdown>
      </article>
    </div>
  );
}
