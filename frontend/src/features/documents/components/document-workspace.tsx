"use client";

import { QueryClient, QueryClientProvider, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { SessionExpiredError } from "@/lib/client/session-expired";

import DocumentList from "./document-list";
import DocumentUpload from "./document-upload";

function WorkspaceContent({ onSessionExpired }: { onSessionExpired?: () => void }) {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);

  function handleUploadCompleted() {
    setPage(0);
    void queryClient.invalidateQueries({ queryKey: ["documents"] });
  }

  return (
    <>
      <DocumentUpload onUploaded={handleUploadCompleted} onSessionExpired={onSessionExpired} />
      <DocumentList page={page} onPageChange={setPage} />
    </>
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
