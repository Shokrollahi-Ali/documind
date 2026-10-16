import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { uploadDocument } from "../api/upload-document";
import DocumentWorkspace from "./document-workspace";

vi.mock("../api/upload-document", () => ({ uploadDocument: vi.fn() }));

const document = {
  id: "fdc6e6a9-4585-477e-b53a-2576edb7a0e1",
  original_filename: "saved.pdf",
  content_type: "application/pdf",
  size_bytes: 128,
  status: "uploaded" as const,
  created_at: "2026-10-15T12:00:00Z",
};

function pageResponse(items = [document], offset = 0, hasMore = false) {
  return Response.json({ items, offset, limit: 10, has_more: hasMore });
}

beforeEach(() => {
  vi.mocked(uploadDocument).mockReset();
  Object.defineProperties(HTMLDialogElement.prototype, {
    showModal: { configurable: true, value: function (this: HTMLDialogElement) { this.open = true; } },
    close: { configurable: true, value: function (this: HTMLDialogElement) { this.open = false; } },
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  Reflect.deleteProperty(HTMLDialogElement.prototype, "showModal");
  Reflect.deleteProperty(HTMLDialogElement.prototype, "close");
});

describe("document workspace", () => {
  it("loads existing documents when the homepage opens", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(pageResponse()));
    render(<DocumentWorkspace />);

    expect(await screen.findByRole("heading", { name: "saved.pdf" })).toBeInTheDocument();
    expect(screen.getByText("< 0.01 MB")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });

  it("shows a useful empty state", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(pageResponse([])));
    render(<DocumentWorkspace />);
    expect(await screen.findByText("No documents yet. Upload a PDF to get started.")).toBeInTheDocument();
  });

  it("lets users refresh after a list failure", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn()
      .mockResolvedValueOnce(new Response("Unavailable", { status: 503 }))
      .mockResolvedValueOnce(pageResponse()));
    render(<DocumentWorkspace />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load");

    await user.click(screen.getByRole("button", { name: "Refresh list" }));
    expect(await screen.findByRole("heading", { name: "saved.pdf" })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("requests the next page and can return to the previous page", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockImplementation((url: string) => Promise.resolve(
      url.includes("offset=10")
        ? pageResponse([{ ...document, original_filename: "older.pdf" }], 10)
        : pageResponse([document], 0, true),
    ));
    vi.stubGlobal("fetch", fetchMock);
    render(<DocumentWorkspace />);
    await screen.findByRole("heading", { name: "saved.pdf" });

    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(await screen.findByRole("heading", { name: "older.pdf" })).toBeInTheDocument();
    expect(screen.getByText("Page 2")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/documents?limit=10&offset=10", expect.any(Object));

    await user.click(screen.getByRole("button", { name: "Previous" }));
    expect(await screen.findByRole("heading", { name: "saved.pdf" })).toBeInTheDocument();
  });

  it("refreshes the list and returns to the first page after an upload", async () => {
    const user = userEvent.setup();
    let uploadComplete = false;
    vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => {
      if (url.includes("offset=10")) return Promise.resolve(pageResponse([document], 10));
      const items = uploadComplete ? [{ ...document, original_filename: "new.pdf" }] : [document];
      return Promise.resolve(pageResponse(items, 0, true));
    }));
    vi.mocked(uploadDocument).mockImplementation(async () => {
      uploadComplete = true;
      return { ...document, original_filename: "new.pdf" };
    });
    render(<DocumentWorkspace />);
    await screen.findByRole("heading", { name: "saved.pdf" });
    await user.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Previous" })).toBeEnabled());

    await user.upload(screen.getByLabelText("PDF document"), new File(["pdf"], "new.pdf", { type: "application/pdf" }));
    await user.click(screen.getByRole("button", { name: "Upload document" }));

    const list = screen.getByRole("region", { name: "Saved documents" });
    expect(await within(list).findByRole("heading", { name: "new.pdf" })).toBeInTheDocument();
    expect(screen.getByText("Page 1")).toBeInTheDocument();
  });
});

it("requires confirmation and allows cancellation without sending DELETE", async () => {
  const user = userEvent.setup();
  const fetchMock = vi.fn().mockResolvedValue(pageResponse());
  vi.stubGlobal("fetch", fetchMock);
  render(<DocumentWorkspace />);
  await user.click(await screen.findByRole("button", { name: "Delete saved.pdf" }));
  expect(screen.getByRole("dialog", { name: "Delete document?" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus();
  expect(screen.getByText(/This permanently removes/)).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Cancel" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

it("disables confirmation while deleting and refreshes the list on success", async () => {
  const user = userEvent.setup();
  let completeDeletion!: (response: Response) => void;
  let deleted = false;
  vi.stubGlobal("fetch", vi.fn().mockImplementation((_url: string, options: RequestInit) => {
    if (options.method === "DELETE") {
      return new Promise<Response>((resolve) => { completeDeletion = resolve; });
    }
    return Promise.resolve(pageResponse(deleted ? [] : [document]));
  }));
  render(<DocumentWorkspace />);
  await user.click(await screen.findByRole("button", { name: "Delete saved.pdf" }));
  await user.click(screen.getByRole("button", { name: "Confirm deletion" }));
  expect(screen.getByRole("button", { name: "Deleting…" })).toBeDisabled();
  expect(fireEvent(screen.getByRole("dialog"), new Event("cancel", { cancelable: true }))).toBe(false);
  expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
  deleted = true;
  completeDeletion(new Response(null, { status: 204 }));
  expect(await screen.findByText("Document deleted.")).toBeInTheDocument();
  expect(await screen.findByText("No documents yet. Upload a PDF to get started.")).toBeInTheDocument();
});

it("keeps the document and shows an error when deletion fails", async () => {
  const user = userEvent.setup();
  vi.stubGlobal("fetch", vi.fn().mockImplementation((_url: string, options: RequestInit) => Promise.resolve(
    options.method === "DELETE" ? new Response(null, { status: 503 }) : pageResponse(),
  )));
  render(<DocumentWorkspace />);
  await user.click(await screen.findByRole("button", { name: "Delete saved.pdf" }));
  await user.click(screen.getByRole("button", { name: "Confirm deletion" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Could not delete");
  expect(screen.getByRole("heading", { name: "saved.pdf" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Confirm deletion" })).toBeEnabled();
});

it("returns to the first page after deleting the last document on a later page", async () => {
  const user = userEvent.setup();
  let deleted = false;
  vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string, options: RequestInit) => {
    if (options.method === "DELETE") {
      deleted = true;
      return Promise.resolve(new Response(null, { status: 204 }));
    }
    if (url.includes("offset=10")) return Promise.resolve(pageResponse(deleted ? [] : [document], 10));
    return Promise.resolve(pageResponse([{ ...document, id: "another-id", original_filename: "newer.pdf" }], 0, !deleted));
  }));
  render(<DocumentWorkspace />);
  await screen.findByRole("heading", { name: "newer.pdf" });
  await user.click(screen.getByRole("button", { name: "Next" }));
  await user.click(await screen.findByRole("button", { name: "Delete saved.pdf" }));
  await user.click(screen.getByRole("button", { name: "Confirm deletion" }));
  expect(await screen.findByRole("heading", { name: "newer.pdf" })).toBeInTheDocument();
  expect(screen.getByText("Page 1")).toBeInTheDocument();
  await waitFor(() => expect(screen.getByRole("button", { name: "Next" })).toBeDisabled());
});


it("allows Escape dismissal before deletion starts", async () => {
  const user = userEvent.setup();
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(pageResponse()));
  render(<DocumentWorkspace />);
  await user.click(await screen.findByRole("button", { name: "Delete saved.pdf" }));
  expect(fireEvent(screen.getByRole("dialog"), new Event("cancel", { cancelable: true }))).toBe(true);
});
