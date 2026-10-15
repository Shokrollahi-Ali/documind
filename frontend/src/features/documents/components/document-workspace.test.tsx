import { render, screen, waitFor, within } from "@testing-library/react";
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
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("document workspace", () => {
  it("loads existing documents when the homepage opens", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(pageResponse()));
    render(<DocumentWorkspace />);

    expect(await screen.findByRole("heading", { name: "saved.pdf" })).toBeInTheDocument();
    expect(screen.getByText("128 bytes")).toBeInTheDocument();
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
