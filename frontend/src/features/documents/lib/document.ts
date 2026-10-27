export type DocumentMetadata = {
  id: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  status: "uploaded" | "processing" | "extracted" | "chunked" | "ready" | "failed";
  created_at: string;
};

export function isDocumentMetadata(value: unknown): value is DocumentMetadata {
  if (typeof value !== "object" || value === null) return false;

  const document = value as Record<string, unknown>;
  const validStatuses = ["uploaded", "processing", "extracted", "chunked", "ready", "failed"];

  return (
    typeof document.id === "string" && document.id.length > 0 &&
    typeof document.original_filename === "string" &&
    typeof document.content_type === "string" &&
    typeof document.size_bytes === "number" &&
    Number.isSafeInteger(document.size_bytes) && document.size_bytes > 0 &&
    typeof document.status === "string" && validStatuses.includes(document.status) &&
    typeof document.created_at === "string" &&
    Number.isFinite(Date.parse(document.created_at))
  );
}
