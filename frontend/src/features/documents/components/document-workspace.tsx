"use client";

import { QueryClient, QueryClientProvider, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import { SessionExpiredError } from "@/lib/client/session-expired";

import { documentsPageSize, documentsQueryKey, useDocuments } from "../hooks/use-documents";
import { useSelectedDocument } from "../hooks/use-selected-document";
import type { DocumentMetadata } from "../lib/document";
import DocumentList from "./document-list";
import DocumentPanel from "./document-panel";

function WorkspaceContent({ onSessionExpired }: { onSessionExpired?: () => void }) {
  const queryClient = useQueryClient();
  const [{ page, pageSize }, setPagination] = useState({ page: 0, pageSize: documentsPageSize });
  const documents = useDocuments(page, pageSize);

  function setPage(nextPage: number) {
    setPagination((current) => ({ ...current, page: nextPage }));
  }

  const handlePageSizeChange = useCallback((nextPageSize: number) => {
    setPagination((current) => current.pageSize === nextPageSize
      ? current
      : { page: 0, pageSize: nextPageSize });
  }, []);
  const { selectedDocument, selectDocument, clearSelection } = useSelectedDocument(documents.data?.items);

  function handleUploaded(uploadedDocument: DocumentMetadata) {
    setPage(0);
    selectDocument(uploadedDocument);
    void queryClient.invalidateQueries({ queryKey: documentsQueryKey });
  }

  function handleDeleted(documentId: string) {
    if (selectedDocument?.id === documentId) clearSelection();
  }

  return (
    <div className="mt-8 grid gap-8 md:grid-cols-[20rem_minmax(0,1fr)]">
      <DocumentList
        documents={documents}
        page={page}
        pageSize={pageSize}
        onPageSizeChange={handlePageSizeChange}
        selectedDocumentId={selectedDocument?.id}
        onPageChange={setPage}
        onSelect={selectDocument}
        onUploaded={handleUploaded}
        onDeleted={handleDeleted}
        onSessionExpired={onSessionExpired}
      />
      <DocumentPanel document={selectedDocument} />
    </div>
  );
}

export default function DocumentWorkspace({ onSessionExpired }: { onSessionExpired?: () => void }) {
  const mounted = useRef(true);
  const [queryClient] = useState(() => new QueryClient());

  useEffect(() => {
    const unsubscribeQueries = queryClient.getQueryCache().subscribe((event) => {
      if (event.type === "updated" && event.action.type === "error" && event.action.error instanceof SessionExpiredError) {
        onSessionExpired?.();
      }
    });
    const unsubscribeMutations = queryClient.getMutationCache().subscribe((event) => {
      if (event.type === "updated" && event.action.type === "error" && event.action.error instanceof SessionExpiredError) {
        onSessionExpired?.();
      }
    });
    return () => {
      unsubscribeQueries();
      unsubscribeMutations();
    };
  }, [queryClient, onSessionExpired]);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      queryClient.clear();
    };
  }, [queryClient]);

  function handleSessionExpired() {
    if (mounted.current) onSessionExpired?.();
  }

  return (
    <QueryClientProvider client={queryClient}>
      <WorkspaceContent onSessionExpired={handleSessionExpired} />
    </QueryClientProvider>
  );
}
