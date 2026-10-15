"use client";

import { useQuery } from "@tanstack/react-query";

import { listDocuments } from "../api/list-documents";

const pageSize = 10;
const statusLabels = {
  uploaded: "Uploaded",
  processing: "Processing",
  ready: "Ready",
  failed: "Failed",
};

export default function DocumentList({ page, onPageChange }: { page: number; onPageChange: (page: number) => void }) {
  const documents = useQuery({
    queryKey: ["documents", { limit: pageSize, offset: page * pageSize }],
    queryFn: ({ signal }) => listDocuments(pageSize, page * pageSize, signal),
    staleTime: 30000,
    retry: false,
  });

  return (
    <section aria-labelledby="saved-documents-heading" className="mt-10 rounded-xl border border-zinc-200 p-6 dark:border-zinc-800">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h2 id="saved-documents-heading" className="text-xl font-semibold">Saved documents</h2>
        <button
          type="button"
          onClick={() => void documents.refetch()}
          disabled={documents.isFetching}
          className="rounded-md border border-zinc-300 px-4 py-2 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-50 dark:border-zinc-700"
        >
          Refresh list
        </button>
      </div>
      <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">Newest uploads first.</p>
      {documents.isFetching && <p role="status" className="mt-4 text-sm">Loading documents…</p>}
      {documents.isError && <p role="alert" className="mt-4 text-sm text-red-700 dark:text-red-400">Could not load the latest documents. Use Refresh list to try again.</p>}
      {documents.data && (
        <>
          {documents.data.items.length === 0 ? (
            <p className="mt-6 text-zinc-600 dark:text-zinc-400">
              {page === 0 ? "No documents yet. Upload a PDF to get started." : "No documents on this page. Return to the previous page."}
            </p>
          ) : (
            <ul className="mt-6 divide-y divide-zinc-200 dark:divide-zinc-800">
              {documents.data.items.map((document) => (
                <li key={document.id} className="py-5 first:pt-0">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <h3 className="min-w-0 break-all font-medium">{document.original_filename}</h3>
                    <span className="rounded-full bg-zinc-100 px-3 py-1 text-xs font-medium text-zinc-800">{statusLabels[document.status]}</span>
                  </div>
                  <dl className="mt-3 flex flex-wrap gap-x-8 gap-y-2 text-sm text-zinc-600 dark:text-zinc-400">
                    <div><dt>Size</dt><dd>{new Intl.NumberFormat("en").format(document.size_bytes)} bytes</dd></div>
                    <div><dt>Uploaded (UTC)</dt><dd><time dateTime={document.created_at}>{new Date(document.created_at).toISOString().slice(0, 10)}</time></dd></div>
                  </dl>
                  <p className="mt-2 break-all text-xs text-zinc-500">ID: {document.id}</p>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
      <nav aria-label="Document pages" className="mt-6 flex items-center justify-between gap-3">
        <button type="button" onClick={() => onPageChange(page - 1)} disabled={page === 0 || documents.isFetching} className="rounded-md border border-zinc-300 px-4 py-2 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-50 dark:border-zinc-700">Previous</button>
        <span className="text-sm">Page {page + 1}</span>
        <button type="button" onClick={() => onPageChange(page + 1)} disabled={!documents.data?.has_more || documents.isFetching || documents.isError} className="rounded-md border border-zinc-300 px-4 py-2 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-50 dark:border-zinc-700">Next</button>
      </nav>
    </section>
  );
}
