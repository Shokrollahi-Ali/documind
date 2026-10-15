import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { uploadDocument } from "../api/upload-document";

import DocumentUpload from "./document-upload";

vi.mock("../api/upload-document", () => ({ uploadDocument: vi.fn() }));

beforeEach(() => {
  vi.mocked(uploadDocument).mockReset();
});

const uploadedDocument = {
  id: "fdc6e6a9-4585-477e-b53a-2576edb7a0e1",
  original_filename: "report.pdf",
  content_type: "application/pdf",
  size_bytes: 11,
  status: "uploaded" as const,
  created_at: "2026-10-15T12:00:00Z",
};

function createPdf(name = "report.pdf") {
  return new File(["PDF content"], name, { type: "application/pdf" });
}

describe("document selection", () => {
  it("starts with a labelled file picker and no selected document", () => {
    render(<DocumentUpload />);

    expect(screen.getByLabelText("PDF document")).toHaveAttribute("accept", ".pdf,application/pdf");
    expect(screen.getByRole("status")).toHaveTextContent("No document selected.");
    expect(screen.queryByRole("button", { name: "Remove selection" })).not.toBeInTheDocument();
  });

  it("shows the selected filename and size and allows replacing it", async () => {
    const user = userEvent.setup();
    render(<DocumentUpload />);
    const input = screen.getByLabelText("PDF document");

    await user.upload(input, createPdf());
    expect(screen.getByRole("status")).toHaveTextContent("Selected: report.pdf");
    expect(screen.getByText("11 bytes")).toBeInTheDocument();

    await user.upload(input, createPdf("replacement.PDF"));
    expect(screen.getByRole("status")).toHaveTextContent("Selected: replacement.PDF");
    expect(screen.queryByText("Selected: report.pdf")).not.toBeInTheDocument();
  });

  it("clears the input, restores focus, and allows selecting the same file again", async () => {
    const user = userEvent.setup();
    render(<DocumentUpload />);
    const input = screen.getByLabelText("PDF document");
    const file = createPdf();

    await user.upload(input, file);
    await user.click(screen.getByRole("button", { name: "Remove selection" }));

    expect(input).toHaveValue("");
    expect(input).toHaveFocus();
    expect(screen.getByRole("status")).toHaveTextContent("No document selected.");

    await user.upload(input, file);
    expect(screen.getByRole("status")).toHaveTextContent("Selected: report.pdf");
  });

  it("rejects invalid selections and recovers when a valid PDF is selected", async () => {
    const user = userEvent.setup({ applyAccept: false });
    render(<DocumentUpload />);
    const input = screen.getByLabelText("PDF document");

    await user.upload(input, createPdf());
    await user.upload(input, new File(["text"], "notes.txt", { type: "text/plain" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Choose a PDF document.");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveValue("");
    expect(screen.getByRole("status")).toHaveTextContent("No document selected.");

    await user.upload(input, createPdf());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(input).toHaveAttribute("aria-invalid", "false");
  });

  it("rejects an empty PDF", async () => {
    const user = userEvent.setup();
    render(<DocumentUpload />);

    await user.upload(screen.getByLabelText("PDF document"), new File([], "empty.pdf", { type: "application/pdf" }));

    expect(screen.getByRole("alert")).toHaveTextContent("The selected document is empty.");
    expect(screen.queryByRole("button", { name: "Remove selection" })).not.toBeInTheDocument();
  });
});


describe("document upload interaction", () => {
  it("disables uploading until a valid file is selected", () => {
    render(<DocumentUpload />);
    expect(screen.getByRole("button", { name: "Upload document" })).toBeDisabled();
  });

  it("prevents duplicate submissions while pending and confirms success", async () => {
    const user = userEvent.setup();
    let finishUpload!: (value: typeof uploadedDocument) => void;
    vi.mocked(uploadDocument).mockImplementation(() => new Promise((resolve) => { finishUpload = resolve; }));
    render(<DocumentUpload />);
    const input = screen.getByLabelText("PDF document");
    await user.upload(input, createPdf());
    await user.dblClick(screen.getByRole("button", { name: "Upload document" }));

    expect(uploadDocument).toHaveBeenCalledTimes(1);
    expect(input).toBeDisabled();
    expect(screen.getByRole("button", { name: "Remove selection" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Uploading…" })).toBeDisabled();

    await act(async () => finishUpload(uploadedDocument));

    expect(screen.getByRole("status")).toHaveTextContent("uploaded successfully");
    expect(input).toHaveValue("");
    expect(input).toBeEnabled();
  });

  it("keeps the selected PDF after an error and permits an explicit retry", async () => {
    const user = userEvent.setup();
    vi.mocked(uploadDocument)
      .mockRejectedValueOnce(new Error("Document storage is temporarily unavailable"))
      .mockResolvedValueOnce(uploadedDocument);
    render(<DocumentUpload />);
    await user.upload(screen.getByLabelText("PDF document"), createPdf());
    await user.click(screen.getByRole("button", { name: "Upload document" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Document storage is temporarily unavailable");
    expect(screen.getByRole("status")).toHaveTextContent("Selected: report.pdf");
    expect(screen.getByRole("button", { name: "Upload document" })).toBeEnabled();

    await user.click(screen.getByRole("button", { name: "Upload document" }));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("uploaded successfully");
  });
});
