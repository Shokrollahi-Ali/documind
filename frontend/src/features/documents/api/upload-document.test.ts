import { afterEach, describe, expect, it, vi } from "vitest";

import { uploadDocument } from "./upload-document";

const document = {
  id: "fdc6e6a9-4585-477e-b53a-2576edb7a0e1",
  original_filename: "report.pdf",
  content_type: "application/pdf",
  size_bytes: 100,
  status: "uploaded",
  created_at: "2026-10-15T12:00:00Z",
};

afterEach(() => vi.unstubAllGlobals());

describe("document upload client", () => {
  it("sends the PDF as multipart data without overriding the boundary header", async () => {
    const fetchMock = vi.fn().mockResolvedValue(Response.json(document, { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);
    const file = new File(["pdf"], "report.pdf", { type: "application/pdf" });

    expect(await uploadDocument(file)).toEqual(document);
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/documents");
    expect(options.method).toBe("POST");
    expect(options.headers).toBeUndefined();
    expect(options.body.get("file")).toEqual(file);
  });

  it("supplies the PDF MIME type when the browser leaves it empty", async () => {
    const fetchMock = vi.fn().mockResolvedValue(Response.json(document));
    vi.stubGlobal("fetch", fetchMock);

    await uploadDocument(new File(["pdf"], "report.pdf"));

    const uploadedFile = fetchMock.mock.calls[0][1].body.get("file");
    expect(uploadedFile.type).toBe("application/pdf");
    expect(await uploadedFile.text()).toBe("pdf");
  });

  it.each([413, 415, 422, 503])("preserves backend error messages for status %i", async (status) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ detail: "Backend validation message" }, { status })));
    await expect(uploadDocument(new File(["pdf"], "report.pdf"))).rejects.toThrow("Backend validation message");
  });

  it("handles HTML gateway errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html>Error</html>", { status: 502 })));
    await expect(uploadDocument(new File(["pdf"], "report.pdf"))).rejects.toThrow("The upload failed.");
  });

  it.each([
    null,
    { ...document, size_bytes: "100" },
    { ...document, status: "unknown" },
    { ...document, created_at: "invalid" },
  ])("does not treat a malformed response as success", async (payload) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(payload)));
    await expect(uploadDocument(new File(["pdf"], "report.pdf"))).rejects.toThrow("unexpected response");
  });

  it("does not automatically retry a network failure", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("Network error"));
    vi.stubGlobal("fetch", fetchMock);
    await expect(uploadDocument(new File(["pdf"], "report.pdf"))).rejects.toThrow("may have been saved");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
