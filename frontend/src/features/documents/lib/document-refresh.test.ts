import { expect, it } from "vitest";

import type { DocumentMetadata } from "./document";
import { documentRefreshIntervalMs, getDocumentRefreshInterval } from "./document-refresh";

function createDocument(status: DocumentMetadata["status"]): DocumentMetadata {
  return {
    id: `document-${status}`,
    original_filename: "report.pdf",
    content_type: "application/pdf",
    size_bytes: 128,
    status,
    created_at: "2026-10-15T12:00:00Z",
  };
}

it.each(["uploaded", "processing", "extracted", "chunked"] as const)(
  "keeps refreshing while a document is %s",
  (status) => {
    expect(getDocumentRefreshInterval([createDocument(status)])).toBe(documentRefreshIntervalMs);
  },
);

it("keeps refreshing when only some documents are preparing", () => {
  const documents = [createDocument("ready"), createDocument("processing")];

  expect(getDocumentRefreshInterval(documents)).toBe(documentRefreshIntervalMs);
});

it("stops refreshing when every document is ready or failed", () => {
  const documents = [createDocument("ready"), createDocument("failed")];

  expect(getDocumentRefreshInterval(documents)).toBe(false);
});

it("does not refresh an empty list", () => {
  expect(getDocumentRefreshInterval([])).toBe(false);
});

it("does not refresh before the first page has loaded", () => {
  expect(getDocumentRefreshInterval(undefined)).toBe(false);
});
