import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import type { DocumentMetadata } from "../lib/document";
import DocumentListItem from "./document-list-item";

function createDocument(status: DocumentMetadata["status"]): DocumentMetadata {
  return {
    id: "fdc6e6a9-4585-477e-b53a-2576edb7a0e1",
    original_filename: "report.pdf",
    content_type: "application/pdf",
    size_bytes: 1_200_000,
    status,
    created_at: "2026-10-15T12:00:00Z",
  };
}

function renderItem(status: DocumentMetadata["status"]) {
  const onDeleted = vi.fn().mockResolvedValue(undefined);
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ul>
        <DocumentListItem document={createDocument(status)} onDeleted={onDeleted} />
      </ul>
    </QueryClientProvider>,
  );
}

it("shows the file name, the size and the status together", () => {
  renderItem("ready");

  expect(screen.getByRole("heading", { name: "report.pdf" })).toBeInTheDocument();
  expect(screen.getByText("1.2 MB")).toBeInTheDocument();
  expect(screen.getByText("Ready to ask")).toBeInTheDocument();
});

it.each([
  ["uploaded", "Preparing…"],
  ["processing", "Preparing…"],
  ["extracted", "Preparing…"],
  ["chunked", "Preparing…"],
  ["ready", "Ready to ask"],
  ["failed", "Couldn’t process"],
] as const)("labels a %s document as %s", (status, label) => {
  renderItem(status);

  expect(screen.getByText(label)).toBeInTheDocument();
});

it("offers a delete button named after the document", () => {
  renderItem("ready");

  expect(screen.getByRole("button", { name: "Delete report.pdf" })).toBeInTheDocument();
});
