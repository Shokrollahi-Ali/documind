import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import type { DocumentMetadata } from "../lib/document";
import DocumentListItem from "./document-list-item";

beforeEach(() => {
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", {
    configurable: true,
    value: function (this: HTMLDialogElement) { this.open = true; },
  });
});

afterEach(() => {
  Reflect.deleteProperty(HTMLDialogElement.prototype, "showModal");
});

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

function renderItem({ status = "ready", isSelected = false, onSelect = vi.fn() }: {
  status?: DocumentMetadata["status"];
  isSelected?: boolean;
  onSelect?: (document: DocumentMetadata) => void;
} = {}) {
  const onDeleted = vi.fn().mockResolvedValue(undefined);
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ul>
        <DocumentListItem
          document={createDocument(status)}
          isSelected={isSelected}
          onSelect={onSelect}
          onDeleted={onDeleted}
        />
      </ul>
    </QueryClientProvider>,
  );
}

it("shows the file name, the size and the status together", () => {
  renderItem();

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
  renderItem({ status });

  expect(screen.getByText(label)).toBeInTheDocument();
});

it("selects the document when its name is clicked", async () => {
  const user = userEvent.setup();
  const onSelect = vi.fn();
  renderItem({ onSelect });

  await user.click(screen.getByRole("button", { name: "report.pdf" }));

  expect(onSelect).toHaveBeenCalledWith(createDocument("ready"));
});

it("marks the selected document as current", () => {
  renderItem({ isSelected: true });

  expect(screen.getByRole("button", { name: "report.pdf" })).toHaveAttribute("aria-current", "true");
});

it("does not mark an unselected document as current", () => {
  renderItem({ isSelected: false });

  expect(screen.getByRole("button", { name: "report.pdf" })).not.toHaveAttribute("aria-current");
});

it("offers a delete button named after the document", () => {
  renderItem();

  expect(screen.getByRole("button", { name: "Delete report.pdf" })).toBeInTheDocument();
});

it("does not select the document when its delete button is clicked", async () => {
  const user = userEvent.setup();
  const onSelect = vi.fn();
  renderItem({ onSelect });

  await user.click(screen.getByRole("button", { name: "Delete report.pdf" }));

  expect(onSelect).not.toHaveBeenCalled();
});
