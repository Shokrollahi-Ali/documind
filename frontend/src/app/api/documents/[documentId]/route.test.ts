import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { DELETE } from "./route";

const documentId = "fdc6e6a9-4585-477e-b53a-2576edb7a0e1";
function removeDocument(id = documentId) {
  return DELETE(new Request(`http://localhost/api/documents/${id}`, {
    method: "DELETE",
    headers: {
      Origin: "http://localhost",
      Cookie: "private-cookie=value; documind_session=delete-session",
    },
  }), {
    params: Promise.resolve({ documentId: id }),
  });
}

beforeEach(() => {
  vi.stubEnv("DOCUMIND_API_URL", "http://backend:8000/api/");
  vi.stubEnv("DOCUMIND_API_TIMEOUT_MS", "10000");
  vi.stubEnv("DOCUMIND_APP_ORIGIN", "");
  vi.stubEnv("DOCUMIND_SESSION_COOKIE_NAME", "documind_session");
  vi.spyOn(console, "error").mockImplementation(() => {});
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

it("forwards deletion and returns a bodyless 204", async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
  vi.stubGlobal("fetch", fetchMock);
  const response = await removeDocument();
  expect(response.status).toBe(204);
  expect(await response.text()).toBe("");
  expect(fetchMock.mock.calls[0][0].toString()).toBe(`http://backend:8000/api/documents/${documentId}`);
  expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: "DELETE", cache: "no-store", redirect: "error" });
  expect(fetchMock.mock.calls[0][1].headers.get("cookie")).toBe("documind_session=delete-session");
});

it.each([401, 404, 503])("preserves backend status %i", async (status) => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ detail: "Unavailable" }, { status })));
  expect((await removeDocument()).status).toBe(status);
});

it("rejects cross-origin deletion before contacting the backend", async () => {
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  const response = await DELETE(new Request(`http://localhost/api/documents/${documentId}`, {
    method: "DELETE", headers: { Origin: "https://untrusted.example" },
  }), { params: Promise.resolve({ documentId }) });
  expect(response.status).toBe(403);
  expect(fetchMock).not.toHaveBeenCalled();
});

it("rejects unsafe document IDs before contacting the backend", async () => {
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  expect((await removeDocument("../other")).status).toBe(422);
  expect(fetchMock).not.toHaveBeenCalled();
});

it("rejects invalid service configuration", async () => {
  vi.stubEnv("DOCUMIND_API_URL", "file:///tmp/service");
  expect((await removeDocument()).status).toBe(503);
});

it("returns a safe error for network failures", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("private backend details")));
  const response = await removeDocument();
  expect(response.status).toBe(502);
  expect(await response.text()).not.toContain("private backend details");
});

it("aborts requests after the configured timeout", async () => {
  vi.stubEnv("DOCUMIND_API_TIMEOUT_MS", "10");
  vi.stubGlobal("fetch", vi.fn((_url: URL, options: RequestInit) => new Promise((_resolve, reject) => {
    options.signal?.addEventListener("abort", () => reject(options.signal?.reason), { once: true });
  })));
  expect((await removeDocument()).status).toBe(504);
});
