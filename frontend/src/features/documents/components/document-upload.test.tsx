import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";

import { SessionExpiredError } from "@/lib/client/session-expired";
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

it("offers an Upload button and a labelled input that accepts PDFs", () => {
  render(<DocumentUpload />);

  expect(screen.getByRole("button", { name: "Upload" })).toBeEnabled();
  expect(screen.getByLabelText("PDF document")).toHaveAttribute("accept", ".pdf,application/pdf");
});

it("opens the file picker when Upload is clicked", async () => {
  const user = userEvent.setup();
  const onPickerOpened = vi.fn();
  render(<DocumentUpload />);
  screen.getByLabelText("PDF document").addEventListener("click", onPickerOpened);

  await user.click(screen.getByRole("button", { name: "Upload" }));

  expect(onPickerOpened).toHaveBeenCalledTimes(1);
});

it("uploads the selected PDF right away and tells the workspace", async () => {
  const user = userEvent.setup();
  vi.mocked(uploadDocument).mockResolvedValue(uploadedDocument);
  const onUploaded = vi.fn();
  render(<DocumentUpload onUploaded={onUploaded} />);
  const file = createPdf();

  await user.upload(screen.getByLabelText("PDF document"), file);

  expect(uploadDocument).toHaveBeenCalledWith(file);
  await waitFor(() => expect(onUploaded).toHaveBeenCalledTimes(1));
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("shows progress and blocks another upload while one is running", async () => {
  const user = userEvent.setup();
  let finishUpload!: (value: typeof uploadedDocument) => void;
  vi.mocked(uploadDocument).mockImplementation(() => new Promise((resolve) => { finishUpload = resolve; }));
  render(<DocumentUpload />);
  const input = screen.getByLabelText("PDF document");

  await user.upload(input, createPdf());

  expect(screen.getByRole("button", { name: "Uploading…" })).toBeDisabled();
  expect(input).toBeDisabled();
  expect(screen.getByRole("status")).toHaveTextContent("Uploading your document");

  await act(async () => finishUpload(uploadedDocument));

  expect(screen.getByRole("button", { name: "Upload" })).toBeEnabled();
  expect(uploadDocument).toHaveBeenCalledTimes(1);
});

it("rejects a file that is not a PDF without uploading it", async () => {
  const user = userEvent.setup({ applyAccept: false });
  render(<DocumentUpload />);

  await user.upload(screen.getByLabelText("PDF document"), new File(["text"], "notes.txt", { type: "text/plain" }));

  expect(screen.getByRole("alert")).toHaveTextContent("Choose a PDF document.");
  expect(uploadDocument).not.toHaveBeenCalled();
});

it("rejects an empty PDF without uploading it", async () => {
  const user = userEvent.setup();
  render(<DocumentUpload />);

  await user.upload(screen.getByLabelText("PDF document"), new File([], "empty.pdf", { type: "application/pdf" }));

  expect(screen.getByRole("alert")).toHaveTextContent("The selected document is empty.");
  expect(uploadDocument).not.toHaveBeenCalled();
});

it("shows an upload error and lets the user choose the same file again", async () => {
  const user = userEvent.setup();
  vi.mocked(uploadDocument)
    .mockRejectedValueOnce(new Error("Document storage is temporarily unavailable"))
    .mockResolvedValueOnce(uploadedDocument);
  const onUploaded = vi.fn();
  render(<DocumentUpload onUploaded={onUploaded} />);
  const input = screen.getByLabelText("PDF document");
  const file = createPdf();

  await user.upload(input, file);

  expect(await screen.findByRole("alert")).toHaveTextContent("Document storage is temporarily unavailable");
  expect(screen.getByRole("button", { name: "Upload" })).toBeEnabled();
  expect(onUploaded).not.toHaveBeenCalled();

  await user.upload(input, file);

  await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
  expect(uploadDocument).toHaveBeenCalledTimes(2);
  expect(onUploaded).toHaveBeenCalledTimes(1);
});

it("tells the workspace when the session has expired", async () => {
  const user = userEvent.setup();
  vi.mocked(uploadDocument).mockRejectedValue(new SessionExpiredError());
  const onSessionExpired = vi.fn();
  render(<DocumentUpload onSessionExpired={onSessionExpired} />);

  await user.upload(screen.getByLabelText("PDF document"), createPdf());

  await waitFor(() => expect(onSessionExpired).toHaveBeenCalledTimes(1));
});
