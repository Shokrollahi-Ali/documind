import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import type { DocumentMetadata } from "../lib/document";
import DocumentPanel from "./document-panel";

function createDocument(status: DocumentMetadata["status"]): DocumentMetadata {
  return {
    id: "fdc6e6a9-4585-477e-b53a-2576edb7a0e1",
    original_filename: "report.pdf",
    content_type: "application/pdf",
    size_bytes: 128,
    status,
    created_at: "2026-10-15T12:00:00Z",
  };
}

function renderPanel(document: DocumentMetadata | null) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <DocumentPanel document={document} history={{ getTurns: () => [], addTurn: vi.fn(), clearTurns: vi.fn() }} />
    </QueryClientProvider>,
  );
}

it("asks the user to pick a document when none is selected", () => {
  renderPanel(null);

  expect(screen.getByText("Select a document from the list, or upload a new one.")).toBeInTheDocument();
  expect(screen.queryByLabelText("Your question")).not.toBeInTheDocument();
});

it("shows the name of the selected document", () => {
  renderPanel(createDocument("ready"));

  expect(screen.getByRole("heading", { level: 2, name: "report.pdf" })).toBeInTheDocument();
});

it.each(["uploaded", "processing", "extracted", "chunked"] as const)(
  "explains that a %s document is still being prepared and cannot be asked yet",
  (status) => {
    renderPanel(createDocument(status));

    expect(screen.getByRole("status")).toHaveTextContent("still being prepared");
    expect(screen.queryByLabelText("Your question")).not.toBeInTheDocument();
  },
);

it("explains why a failed document cannot be used", () => {
  renderPanel(createDocument("failed"));

  expect(screen.getByText(/couldn’t be processed/)).toBeInTheDocument();
  expect(screen.getByText(/Scanned or password-protected PDFs/)).toBeInTheDocument();
  expect(screen.getByText("Delete it from the list and upload a different file.")).toBeInTheDocument();
  expect(screen.queryByLabelText("Your question")).not.toBeInTheDocument();
});

it("offers the question box for a ready document", () => {
  renderPanel(createDocument("ready"));

  expect(screen.getByLabelText("Your question")).toBeInTheDocument();
  expect(screen.queryByText(/still being prepared/)).not.toBeInTheDocument();
  expect(screen.queryByText(/couldn’t be processed/)).not.toBeInTheDocument();
});
