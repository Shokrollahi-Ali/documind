"use client";

import { useQueryClient } from "@tanstack/react-query";
import type { UseQueryResult } from "@tanstack/react-query";

import { useEffect, useRef, useState } from "react";

import Button from "@/components/button";
import { RefreshIcon } from "@/components/icons";
import type { DocumentPage } from "../api/list-documents";
import { documentsQueryKey, getDocumentsQueryKey } from "../hooks/use-documents";
import { useFittingPageSize } from "../hooks/use-fitting-page-size";
import type { DocumentMetadata } from "../lib/document";
import DocumentListItem from "./document-list-item";
import DocumentPagination from "./document-pagination";
import DocumentUpload from "./document-upload";

const noticeDurationMs = 5000;

type DocumentListProps = {
  documents: UseQueryResult<DocumentPage>;
  page: number;
  pageSize: number;
  onPageSizeChange: (pageSize: number) => void;
  selectedDocumentId?: string;
  onPageChange: (page: number) => void;
  onSelect: (document: DocumentMetadata) => void;
  onUploaded: (document: DocumentMetadata) => void;
  onDeleted: (documentId: string) => void;
  onSessionExpired?: () => void;
};

export default function DocumentList({
  documents,
  page,
  pageSize,
  onPageSizeChange,
  selectedDocumentId,
  onPageChange,
  onSelect,
  onUploaded,
  onDeleted,
  onSessionExpired,
}: DocumentListProps) {
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
    onDeleted(documentId);
    const currentPage = queryClient.getQueryData<DocumentPage>(getDocumentsQueryKey(page, pageSize));
    if (page > 0 && currentPage?.items.length === 0) onPageChange(page - 1);
    await queryClient.invalidateQueries({ queryKey: documentsQueryKey });
  }

  const items = (documents.data?.items ?? []).slice(0, pageSize);
  const panelRef = useFittingPageSize(items.length > 0, onPageSizeChange);
  const isRefreshing = documents.isFetching && !documents.isLoading;
  const canGoPrevious = page > 0 && !documents.isFetching;
  const canGoNext = Boolean(documents.data?.has_more) && !documents.isFetching && !documents.isError;
  const emptyMessage = page === 0
    ? "No documents yet. Upload a PDF to get started."
    : "No documents on this page. Return to the previous page.";

  return (
    <section ref={panelRef} aria-labelledby="your-documents-heading" className="min-w-0 self-start">
      <div className="flex flex-wrap items-center gap-1.5">
        <h2 ref={heading} id="your-documents-heading" tabIndex={-1} className="mr-auto text-lg font-medium focus:outline-none">Your documents</h2>
        <Button
          size="icon"
          aria-label={isRefreshing ? "Refreshing…" : "Refresh list"}
          title="Refresh list"
          onClick={() => void documents.refetch()}
          disabled={documents.isFetching}
        >
          <RefreshIcon className={isRefreshing ? "animate-spin" : ""} />
        </Button>
        <DocumentUpload onUploaded={onUploaded} onSessionExpired={onSessionExpired} />
      </div>
      {deletionNotice && <p role="status" className="mt-3 text-sm">{deletionNotice.message}</p>}
      {documents.isLoading && <p role="status" className="mt-3 text-sm">Loading documents…</p>}
      {documents.isError && <p role="alert" className="mt-3 text-sm text-red-700 dark:text-red-400">Could not load the latest documents. Use Refresh list to try again.</p>}
      {documents.data && items.length === 0 && (
        <p className="mt-4 text-base text-zinc-600 dark:text-zinc-400">{emptyMessage}</p>
      )}
      {items.length > 0 && (
        <ul className="mt-4 flex flex-col gap-2">
          {items.map((document) => (
            <DocumentListItem
              key={document.id}
              document={document}
              isSelected={document.id === selectedDocumentId}
              onSelect={onSelect}
              onDeleted={handleDeleted}
            />
          ))}
        </ul>
      )}
      <DocumentPagination page={page} canGoPrevious={canGoPrevious} canGoNext={canGoNext} onPageChange={onPageChange} />
    </section>
  );
}
