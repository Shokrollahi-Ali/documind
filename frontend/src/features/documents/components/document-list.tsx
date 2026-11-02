"use client";

import { useQueryClient } from "@tanstack/react-query";

import { useEffect, useRef, useState } from "react";

import Button from "@/components/button";
import { RefreshIcon } from "@/components/icons";
import type { DocumentPage } from "../api/list-documents";
import { documentsQueryKey, getDocumentsQueryKey, useDocuments } from "../hooks/use-documents";
import DocumentListItem from "./document-list-item";
import DocumentPagination from "./document-pagination";

const noticeDurationMs = 5000;

export default function DocumentList({ page, onPageChange }: { page: number; onPageChange: (page: number) => void }) {
  const queryClient = useQueryClient();
  const heading = useRef<HTMLHeadingElement>(null);
  const [deletionNotice, setDeletionNotice] = useState<{ message: string } | null>(null);

  useEffect(() => {
    if (!deletionNotice) return;
    heading.current?.focus();
    const timer = setTimeout(() => setDeletionNotice(null), noticeDurationMs);
    return () => clearTimeout(timer);
  }, [deletionNotice]);

  async function handleDeleted(documentId: string) {
    await queryClient.cancelQueries({ queryKey: documentsQueryKey });
    queryClient.setQueriesData<DocumentPage>({ queryKey: documentsQueryKey }, (cachedPage) => {
      if (!cachedPage) return cachedPage;
      return { ...cachedPage, items: cachedPage.items.filter((item) => item.id !== documentId) };
    });
    setDeletionNotice({ message: "Document deleted." });
    const currentPage = queryClient.getQueryData<DocumentPage>(getDocumentsQueryKey(page));
    if (page > 0 && currentPage?.items.length === 0) onPageChange(page - 1);
    await queryClient.invalidateQueries({ queryKey: documentsQueryKey });
  }

  const documents = useDocuments(page);
  const items = documents.data?.items ?? [];
  const isRefreshing = documents.isFetching && !documents.isLoading;
  const canGoPrevious = page > 0 && !documents.isFetching;
  const canGoNext = Boolean(documents.data?.has_more) && !documents.isFetching && !documents.isError;
  const emptyMessage = page === 0
    ? "No documents yet. Upload a PDF to get started."
    : "No documents on this page. Return to the previous page.";

  return (
    <section aria-labelledby="saved-documents-heading" className="mt-10 max-w-md">
      <div className="flex items-center justify-between gap-2">
        <h2 ref={heading} id="saved-documents-heading" tabIndex={-1} className="text-base font-medium focus:outline-none">Saved documents</h2>
        <Button
          size="icon"
          aria-label={isRefreshing ? "Refreshing…" : "Refresh list"}
          title="Refresh list"
          onClick={() => void documents.refetch()}
          disabled={documents.isFetching}
        >
          <RefreshIcon className={isRefreshing ? "animate-spin" : ""} />
        </Button>
      </div>
      {deletionNotice && <p role="status" className="mt-3 text-xs">{deletionNotice.message}</p>}
      {documents.isLoading && <p role="status" className="mt-3 text-xs">Loading documents…</p>}
      {documents.isError && <p role="alert" className="mt-3 text-xs text-red-700 dark:text-red-400">Could not load the latest documents. Use Refresh list to try again.</p>}
      {documents.data && items.length === 0 && (
        <p className="mt-4 text-sm text-zinc-600 dark:text-zinc-400">{emptyMessage}</p>
      )}
      {items.length > 0 && (
        <ul className="mt-4 flex flex-col gap-2">
          {items.map((document) => (
            <DocumentListItem key={document.id} document={document} onDeleted={handleDeleted} />
          ))}
        </ul>
      )}
      <DocumentPagination page={page} canGoPrevious={canGoPrevious} canGoNext={canGoNext} onPageChange={onPageChange} />
    </section>
  );
}
