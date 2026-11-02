import { isDocumentStatus } from "./document-status";
import type { DocumentStatus } from "./document-status";

export type DocumentMetadata = {
  id: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  status: DocumentStatus;
  created_at: string;
};

export function isDocumentMetadata(value: unknown): value is DocumentMetadata {
  if (typeof value !== "object" || value === null) return false;

  const document = value as Record<string, unknown>;

  return (
    typeof document.id === "string" && document.id.length > 0 &&
    typeof document.original_filename === "string" &&
    typeof document.content_type === "string" &&
    typeof document.size_bytes === "number" &&
    Number.isSafeInteger(document.size_bytes) && document.size_bytes > 0 &&
    isDocumentStatus(document.status) &&
    typeof document.created_at === "string" &&
    Number.isFinite(Date.parse(document.created_at))
  );
}
