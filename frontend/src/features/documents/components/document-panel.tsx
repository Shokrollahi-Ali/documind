import type { DocumentMetadata } from "../lib/document";
import { getDocumentStage } from "../lib/document-status";

export default function DocumentPanel({ document }: { document: DocumentMetadata | null }) {
  if (!document) {
    return (
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        Select a document from the list, or upload a new one.
      </p>
    );
  }

  const stage = getDocumentStage(document.status);

  return (
    <section aria-labelledby="selected-document-heading">
      <h2 id="selected-document-heading" className="break-all text-base font-medium">
        {document.original_filename}
      </h2>
      {stage === "preparing" && (
        <p role="status" className="mt-3 text-sm text-zinc-600 dark:text-zinc-400">
          This document is still being prepared. This page updates by itself, and you can ask questions once it’s ready.
        </p>
      )}
      {stage === "failed" && (
        <>
          <p className="mt-3 text-sm text-red-700 dark:text-red-400">
            This document couldn’t be processed, so it can’t answer questions. Scanned or password-protected PDFs often cause this.
          </p>
          <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
            Delete it from the list and upload a different file.
          </p>
        </>
      )}
    </section>
  );
}
