import type { UploadedDocument } from "../api/upload-document";

const statusLabels: Record<UploadedDocument["status"], string> = {
  uploaded: "Uploaded",
  processing: "Processing",
  ready: "Ready",
  failed: "Processing failed",
};

export default function UploadedDocumentDetails({ document }: { document: UploadedDocument }) {
  return (
    <section aria-label="Uploaded document" className="mt-6 rounded-xl border border-zinc-200 p-6 dark:border-zinc-800">
      <h2 className="text-lg font-semibold">Latest upload</h2>
      <p className="mt-3 break-words font-medium">{document.original_filename}</p>
      <dl className="mt-4 space-y-3 text-sm">
        <div>
          <dt className="text-zinc-600 dark:text-zinc-400">Status</dt>
          <dd>{statusLabels[document.status]}</dd>
        </div>
        <div>
          <dt className="text-zinc-600 dark:text-zinc-400">Size</dt>
          <dd>{new Intl.NumberFormat("en").format(document.size_bytes)} bytes</dd>
        </div>
        <div>
          <dt className="text-zinc-600 dark:text-zinc-400">Document ID</dt>
          <dd className="break-all font-mono">{document.id}</dd>
        </div>
      </dl>
      <p className="mt-4 text-sm text-zinc-600 dark:text-zinc-400">
        Your PDF has been saved. Document processing and question answering are not available yet.
      </p>
    </section>
  );
}
