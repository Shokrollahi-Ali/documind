"use client";

import { useMutation } from "@tanstack/react-query";
import { useId, useRef } from "react";

import Button from "@/components/button";
import { deleteDocument } from "../api/delete-document";
import type { DocumentMetadata } from "../lib/document";

export default function DocumentDelete({ document, onDeleted }: {
  document: DocumentMetadata;
  onDeleted: (documentId: string) => Promise<void>;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const cancelButton = useRef<HTMLButtonElement>(null);
  const titleId = useId();
  const descriptionId = useId();
  const deletion = useMutation({
    mutationFn: () => deleteDocument(document.id),
    onSuccess: () => onDeleted(document.id),
    retry: false,
  });

  function openDialog() {
    deletion.reset();
    dialog.current?.showModal();
    cancelButton.current?.focus();
  }

  return (
    <>
      <Button variant="danger-outline" onClick={openDialog} aria-label={`Delete ${document.original_filename}`} className="mt-4">
        Delete
      </Button>
      <dialog
        ref={dialog}
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        onCancel={(event) => {
          if (deletion.isPending) event.preventDefault();
        }}
        className="fixed inset-0 m-auto w-[calc(100%-2rem)] max-w-xl rounded-xl border border-zinc-200 bg-background p-6 text-foreground shadow-xl backdrop:bg-black/50 dark:border-zinc-700"
      >
        <h2 id={titleId} className="text-xl font-semibold">Delete document?</h2>
        <p id={descriptionId} className="mt-3 wrap-break-word text-sm">Delete “{document.original_filename}”? This permanently removes the uploaded file.</p>
        <div className="mt-6 flex justify-end gap-3">
          <Button ref={cancelButton} disabled={deletion.isPending} onClick={() => dialog.current?.close()}>
            Cancel
          </Button>
          <Button variant="danger" disabled={deletion.isPending} onClick={() => deletion.mutate()}>
            {deletion.isPending ? "Deleting…" : "Confirm deletion"}
          </Button>
        </div>
        {deletion.isPending && <p role="status" className="mt-3 text-sm">Deleting document…</p>}
        {deletion.isError && <p role="alert" className="mt-3 text-sm text-red-700 dark:text-red-400">{deletion.error.message}</p>}
      </dialog>
    </>
  );
}
