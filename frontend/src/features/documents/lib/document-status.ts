export const documentStatuses = [
  "uploaded",
  "processing",
  "extracted",
  "chunked",
  "ready",
  "failed",
] as const;

export type DocumentStatus = (typeof documentStatuses)[number];

export type DocumentStage = "preparing" | "ready" | "failed";

export const documentStageLabels: Record<DocumentStage, string> = {
  preparing: "Preparing…",
  ready: "Ready to ask",
  failed: "Couldn’t process",
};

export function isDocumentStatus(value: unknown): value is DocumentStatus {
  return documentStatuses.some((status) => status === value);
}

export function getDocumentStage(status: DocumentStatus): DocumentStage {
  if (status === "ready") return "ready";
  if (status === "failed") return "failed";
  return "preparing";
}
