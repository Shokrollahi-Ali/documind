import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

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

it("asks the user to pick a document when none is selected", () => {
  render(<DocumentPanel document={null} />);

  expect(screen.getByText("Select a document from the list, or upload a new one.")).toBeInTheDocument();
});

it("shows the name of the selected document", () => {
  render(<DocumentPanel document={createDocument("ready")} />);

  expect(screen.getByRole("heading", { level: 2, name: "report.pdf" })).toBeInTheDocument();
});

it.each(["uploaded", "processing", "extracted", "chunked"] as const)(
  "explains that a %s document is still being prepared",
  (status) => {
    render(<DocumentPanel document={createDocument(status)} />);

    expect(screen.getByRole("status")).toHaveTextContent("still being prepared");
  },
);

it("explains why a failed document cannot be used", () => {
  render(<DocumentPanel document={createDocument("failed")} />);

  expect(screen.getByText(/couldn’t be processed/)).toBeInTheDocument();
  expect(screen.getByText(/Scanned or password-protected PDFs/)).toBeInTheDocument();
  expect(screen.getByText("Delete it from the list and upload a different file.")).toBeInTheDocument();
});

it("shows no preparing or failure message for a ready document", () => {
  render(<DocumentPanel document={createDocument("ready")} />);

  expect(screen.queryByText(/still being prepared/)).not.toBeInTheDocument();
  expect(screen.queryByText(/couldn’t be processed/)).not.toBeInTheDocument();
});
