"use client";

import { QueryClient, QueryClientProvider, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import DocumentList from "./document-list";
import DocumentUpload from "./document-upload";

function WorkspaceContent() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);

  function handleUploadCompleted() {
    setPage(0);
    void queryClient.invalidateQueries({ queryKey: ["documents"] });
  }

  return (
    <>
      <DocumentUpload onUploaded={handleUploadCompleted} />
      <DocumentList page={page} onPageChange={setPage} />
    </>
  );
}

export default function DocumentWorkspace() {
  const [queryClient] = useState(() => new QueryClient());

  return (
    <QueryClientProvider client={queryClient}>
      <WorkspaceContent />
    </QueryClientProvider>
  );
}
