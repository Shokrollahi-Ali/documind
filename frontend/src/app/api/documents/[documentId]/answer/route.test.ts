import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { POST } from "./route";

const documentId = "fdc6e6a9-4585-477e-b53a-2576edb7a0e1";

function askQuestion(id = documentId, origin = "http://localhost", body = '{"question":"What is the notice period?"}') {
  return POST(new Request(`http://localhost/api/documents/${id}/answer`, {
    method: "POST",
    body,
    headers: {
      Origin: origin,
      "Content-Type": "application/json",
      Cookie: "private-cookie=value; documind_session=answer-session",
    },
  }), {
    params: Promise.resolve({ documentId: id }),
  });
}

beforeEach(() => {
  vi.stubEnv("DOCUMIND_API_URL", "http://backend:8000/api/");
  vi.stubEnv("DOCUMIND_ANSWER_TIMEOUT_MS", "100000");
  vi.stubEnv("DOCUMIND_APP_ORIGIN", "");
  vi.stubEnv("DOCUMIND_SESSION_COOKIE_NAME", "documind_session");
  vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

it("forwards the question with only the session cookie", async () => {
  const fetchMock = vi.fn().mockResolvedValue(Response.json({ answer: "Sixty days [chunk 1]", sources: [] }));
  vi.stubGlobal("fetch", fetchMock);

  const response = await askQuestion();

  expect(response.status).toBe(200);
  expect(response.headers.get("cache-control")).toBe("no-store");
  expect(await response.json()).toEqual({ answer: "Sixty days [chunk 1]", sources: [] });
  const [url, options] = fetchMock.mock.calls[0];
  expect(url.toString()).toBe(`http://backend:8000/api/documents/${documentId}/answer`);
  expect(options).toMatchObject({ method: "POST", cache: "no-store", redirect: "error" });
  expect(JSON.parse(options.body)).toEqual({ question: "What is the notice period?" });
  expect(options.headers.get("cookie")).toBe("documind_session=answer-session");
  expect(options.headers.get("content-type")).toBe("application/json");
});

it.each([401, 404, 409, 422, 502, 503])("preserves backend status %i", async (status) => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ detail: "Rejected" }, { status })));

  const response = await askQuestion();

  expect(response.status).toBe(status);
  expect(await response.json()).toEqual({ detail: "Rejected" });
});

it("rejects cross-origin questions before contacting the backend", async () => {
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);

  expect((await askQuestion(documentId, "https://untrusted.example")).status).toBe(403);
  expect(fetchMock).not.toHaveBeenCalled();
});

it("rejects unsafe document IDs before contacting the backend", async () => {
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);

  expect((await askQuestion("../other")).status).toBe(422);
  expect(fetchMock).not.toHaveBeenCalled();
});

it("rejects malformed JSON before contacting the backend", async () => {
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);

  expect((await askQuestion(documentId, "http://localhost", "{")).status).toBe(400);
  expect(fetchMock).not.toHaveBeenCalled();
});

it("rejects oversized questions before contacting the backend", async () => {
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  const body = JSON.stringify({ question: "x".repeat(16384) });

  expect((await askQuestion(documentId, "http://localhost", body)).status).toBe(413);
  expect(fetchMock).not.toHaveBeenCalled();
});

it("rejects invalid timeout configuration without contacting the backend", async () => {
  vi.stubEnv("DOCUMIND_ANSWER_TIMEOUT_MS", "0");
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);

  expect((await askQuestion()).status).toBe(503);
  expect(fetchMock).not.toHaveBeenCalled();
});

it("returns a safe error for network failures", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("private backend details")));

  const response = await askQuestion();

  expect(response.status).toBe(502);
  expect(await response.text()).not.toContain("private backend details");
});

it("aborts a request that exceeds the answer timeout", async () => {
  vi.stubEnv("DOCUMIND_ANSWER_TIMEOUT_MS", "10");
  vi.stubGlobal("fetch", vi.fn((_url: URL, options: RequestInit) => new Promise((_resolve, reject) => {
    options.signal?.addEventListener("abort", () => reject(options.signal?.reason), { once: true });
  })));

  expect((await askQuestion()).status).toBe(504);
});

it("waits for the answer timeout rather than the shorter default timeout", async () => {
  vi.stubEnv("DOCUMIND_API_TIMEOUT_MS", "1");
  vi.stubEnv("DOCUMIND_ANSWER_TIMEOUT_MS", "5000");
  vi.stubGlobal("fetch", vi.fn((_url: URL, options: RequestInit) => new Promise<Response>((resolve, reject) => {
    options.signal?.addEventListener("abort", () => reject(options.signal?.reason), { once: true });
    setTimeout(() => resolve(Response.json({ answer: "Done [chunk 1]", sources: [] })), 50);
  })));

  expect((await askQuestion()).status).toBe(200);
});
