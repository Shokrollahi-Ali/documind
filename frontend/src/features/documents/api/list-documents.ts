import { checkSession } from "@/lib/client/session-expired";
import { isDocumentMetadata } from "../lib/document";
import type { DocumentMetadata } from "../lib/document";

export type DocumentPage = {
  items: DocumentMetadata[];
  has_more: boolean;
  limit: number;
  offset: number;
};

function isDocumentPage(value: unknown): value is DocumentPage {
  if (typeof value !== "object" || value === null) return false;
  const page = value as Record<string, unknown>;

  return (
    Array.isArray(page.items) && page.items.every(isDocumentMetadata) &&
    typeof page.has_more === "boolean" &&
    typeof page.limit === "number" && Number.isInteger(page.limit) && page.limit > 0 &&
    typeof page.offset === "number" && Number.isInteger(page.offset) && page.offset >= 0
  );
}

export async function listDocuments(limit: number, offset: number, signal: AbortSignal): Promise<DocumentPage> {
  const query = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  const response = await fetch(`/api/documents?${query}`, { signal, cache: "no-store" });
  checkSession(response);
  if (!response.ok) throw new Error("Could not load your documents. Please try again.");

  const page: unknown = await response.json();
  if (!isDocumentPage(page) || page.limit !== limit || page.offset !== offset || page.items.length > limit) {
    throw new Error("The document service returned an unexpected response.");
  }
  return page;
}
