import { act, renderHook } from "@testing-library/react";
import { expect, it } from "vitest";

import type { DocumentMetadata } from "../lib/document";
import { useSelectedDocument } from "./use-selected-document";

function createDocument(id: string, status: DocumentMetadata["status"] = "processing"): DocumentMetadata {
  return {
    id,
    original_filename: `${id}.pdf`,
    content_type: "application/pdf",
    size_bytes: 128,
    status,
    created_at: "2026-10-15T12:00:00Z",
  };
}

function renderSelection(documents: DocumentMetadata[] | undefined) {
  return renderHook(
    ({ currentDocuments }) => useSelectedDocument(currentDocuments),
    { initialProps: { currentDocuments: documents } },
  );
}

it("starts with no document selected", () => {
  const { result } = renderSelection([createDocument("first")]);

  expect(result.current.selectedDocument).toBeNull();
});

it("returns the document that was selected", () => {
  const first = createDocument("first");
  const { result } = renderSelection([first]);

  act(() => result.current.selectDocument(first));

  expect(result.current.selectedDocument).toEqual(first);
});

it("returns the newest version of the selected document when the list reloads", () => {
  const first = createDocument("first", "processing");
  const { result, rerender } = renderSelection([first]);
  act(() => result.current.selectDocument(first));

  rerender({ currentDocuments: [createDocument("first", "ready")] });

  expect(result.current.selectedDocument?.status).toBe("ready");
});

it("keeps the selected document while the list shows other documents", () => {
  const first = createDocument("first");
  const { result, rerender } = renderSelection([first]);
  act(() => result.current.selectDocument(first));

  rerender({ currentDocuments: [createDocument("second")] });

  expect(result.current.selectedDocument).toEqual(first);
});

it("keeps the selected document before the list has loaded", () => {
  const first = createDocument("first");
  const { result, rerender } = renderSelection([first]);
  act(() => result.current.selectDocument(first));

  rerender({ currentDocuments: undefined });

  expect(result.current.selectedDocument).toEqual(first);
});

it("clears the selection", () => {
  const first = createDocument("first");
  const { result } = renderSelection([first]);
  act(() => result.current.selectDocument(first));

  act(() => result.current.clearSelection());

  expect(result.current.selectedDocument).toBeNull();
});
