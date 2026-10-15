import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { POST } from "./route";

function createUploadRequest() {
  const formData = new FormData();
  formData.append("file", new File(["pdf content"], "report.pdf", { type: "application/pdf" }));
  return new Request("http://localhost:3000/api/documents", {
    method: "POST",
    body: formData,
    headers: { Cookie: "private-cookie=value" },
  });
}

beforeEach(() => {
  vi.stubEnv("DOCUMIND_API_URL", "http://backend:8000/");
  vi.stubEnv("DOCUMIND_UPLOAD_TIMEOUT_MS", "120000");
  vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

describe("document upload route", () => {
  it("forwards the multipart stream and preserves the response status", async () => {
    const fetchMock = vi.fn(async (url: URL, options: RequestInit) => {
      expect(url.toString()).toBe("http://backend:8000/documents");
      expect(options.redirect).toBe("error");
      const request = new Request(url, options);
      expect(request.headers.has("cookie")).toBe(false);
      const formData = await request.formData();
      const file = formData.get("file") as File;
      expect(file.name).toBe("report.pdf");
      expect(await file.text()).toBe("pdf content");
      return Response.json({ id: "created-document" }, { status: 201 });
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(createUploadRequest());

    expect(response.status).toBe(201);
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(await response.json()).toEqual({ id: "created-document" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it.each([413, 415, 422, 503])("preserves backend rejection %i", async (status) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ detail: "PDF rejected" }, { status })));
    const response = await POST(createUploadRequest());
    expect(response.status).toBe(status);
    expect(await response.json()).toEqual({ detail: "PDF rejected" });
  });

  it.each(["", "file:///tmp/api", "not-a-url"])("rejects invalid configuration without contacting a backend", async (url) => {
    vi.stubEnv("DOCUMIND_API_URL", url);
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    expect((await POST(createUploadRequest())).status).toBe(503);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects invalid timeout configuration", async () => {
    vi.stubEnv("DOCUMIND_UPLOAD_TIMEOUT_MS", "0");
    expect((await POST(createUploadRequest())).status).toBe(503);
  });

  it("rejects non-multipart requests", async () => {
    const request = new Request("http://localhost/api/documents", { method: "POST", body: "invalid" });
    expect((await POST(request)).status).toBe(415);
  });

  it("returns a safe error when the backend cannot be reached", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("private infrastructure details")));
    const response = await POST(createUploadRequest());
    expect(response.status).toBe(502);
    expect(await response.text()).not.toContain("private infrastructure details");
  });

  it("aborts an upstream request that exceeds the configured timeout", async () => {
    vi.stubEnv("DOCUMIND_UPLOAD_TIMEOUT_MS", "10");
    vi.stubGlobal("fetch", vi.fn((_url: URL, options: RequestInit) => new Promise((_resolve, reject) => {
      options.signal?.addEventListener("abort", () => reject(options.signal?.reason), { once: true });
    })));

    const response = await POST(createUploadRequest());

    expect(response.status).toBe(504);
    expect(await response.text()).toContain("may have been saved");
  });
});
