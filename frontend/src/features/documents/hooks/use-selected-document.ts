import { useState } from "react";

import type { DocumentMetadata } from "../lib/document";

export function useSelectedDocument(documents: DocumentMetadata[] | undefined) {
  const [selectedDocument, setSelectedDocument] = useState<DocumentMetadata | null>(null);

  const latestVersion = documents?.find((document) => document.id === selectedDocument?.id);

  return {
    selectedDocument: latestVersion ?? selectedDocument,
    selectDocument: setSelectedDocument,
    clearSelection: () => setSelectedDocument(null),
  };
}
