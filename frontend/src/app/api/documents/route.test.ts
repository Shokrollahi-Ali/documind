import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { GET, POST } from "./route";

function createUploadRequest() {
  const formData = new FormData();
  formData.append("file", new File(["pdf content"], "report.pdf", { type: "application/pdf" }));
  return new Request("http://localhost:3000/api/documents", {
    method: "POST",
    body: formData,
    headers: {
      Origin: "http://localhost:3000",
      Cookie: "private-cookie=value; documind_session=document-session",
    },
  });
}

beforeEach(() => {
  vi.stubEnv("DOCUMIND_API_URL", "http://backend:8000/");
  vi.stubEnv("DOCUMIND_UPLOAD_TIMEOUT_MS", "120000");
  vi.stubEnv("DOCUMIND_APP_ORIGIN", "");
  vi.stubEnv("DOCUMIND_SESSION_COOKIE_NAME", "documind_session");
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
      expect(request.headers.get("cookie")).toBe("documind_session=document-session");
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

  it.each([401, 413, 415, 422, 503])("preserves backend rejection %i", async (status) => {
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
    const request = new Request("http://localhost/api/documents", {
      method: "POST", body: "invalid", headers: { Origin: "http://localhost" },
    });
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


describe("document list route", () => {
  it("forwards only validated pagination and disables caching", async () => {
    const fetchMock = vi.fn().mockResolvedValue(Response.json({ items: [], has_more: false, limit: 10, offset: 20 }));
    vi.stubGlobal("fetch", fetchMock);
    const response = await GET(new Request("http://localhost/api/documents?limit=10&offset=20&ignored=value", {
      headers: { Cookie: "documind_session=list-session; private-cookie=value" },
    }));
    expect(response.status).toBe(200);
    expect(fetchMock.mock.calls[0][0].toString()).toBe("http://backend:8000/documents?limit=10&offset=20");
    expect(fetchMock.mock.calls[0][1].cache).toBe("no-store");
    expect(fetchMock.mock.calls[0][1].headers.get("cookie")).toBe("documind_session=list-session");
    expect(response.headers.get("cache-control")).toBe("no-store");
  });

  it.each(["limit=0", "limit=101", "offset=-1", "offset=1.5"])("rejects invalid pagination", async (query) => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    expect((await GET(new Request(`http://localhost/api/documents?${query}`))).status).toBe(422);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("preserves backend errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ detail: "Unavailable" }, { status: 503 })));
    expect((await GET(new Request("http://localhost/api/documents"))).status).toBe(503);
  });

  it("returns a safe gateway error on connection failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("private error")));
    const response = await GET(new Request("http://localhost/api/documents"));
    expect(response.status).toBe(502);
    expect(await response.text()).not.toContain("private error");
  });
});

it("rejects cross-origin uploads before forwarding cookies or files", async () => {
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  const request = createUploadRequest();
  request.headers.set("Origin", "https://untrusted.example");
  expect((await POST(request)).status).toBe(403);
  expect(fetchMock).not.toHaveBeenCalled();
});
