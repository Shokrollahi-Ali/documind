import type { DocumentMetadata } from "./document";
import { getDocumentStage } from "./document-status";

export const documentRefreshIntervalMs = 3000;

function isPreparing(document: DocumentMetadata): boolean {
  return getDocumentStage(document.status) === "preparing";
}

export function getDocumentRefreshInterval(documents: DocumentMetadata[] | undefined): number | false {
  if (documents?.some(isPreparing)) return documentRefreshIntervalMs;

  return false;
}
