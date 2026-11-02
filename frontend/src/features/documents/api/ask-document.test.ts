import { afterEach, expect, it, vi } from "vitest";

import { SessionExpiredError } from "@/lib/client/session-expired";
import { askDocument } from "./ask-document";

const documentId = "fdc6e6a9-4585-477e-b53a-2576edb7a0e1";
const answer = {
  answer: "Sixty days [chunk 1]",
  sources: [{ chunk_index: 1, page_number: 4, text: "Sixty days notice." }],
};

afterEach(() => vi.unstubAllGlobals());

it("sends the question as JSON and returns the answer", async () => {
  const fetchMock = vi.fn().mockResolvedValue(Response.json(answer));
  vi.stubGlobal("fetch", fetchMock);

  await expect(askDocument(documentId, "What is the notice period?")).resolves.toEqual(answer);

  const [url, options] = fetchMock.mock.calls[0];
  expect(url).toBe(`/api/documents/${documentId}/answer`);
  expect(options.method).toBe("POST");
  expect(options.headers["Content-Type"]).toBe("application/json");
  expect(JSON.parse(options.body)).toEqual({ question: "What is the notice period?" });
});

it("shows the message sent by the backend", async () => {
  const body = { detail: "Document is not ready for questions" };
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(body, { status: 409 })));

  await expect(askDocument(documentId, "Question?")).rejects.toThrow("Document is not ready for questions");
});

it("uses a general message when the backend message is not text", async () => {
  const body = { detail: [{ msg: "String should have at most 2000 characters" }] };
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(body, { status: 422 })));

  await expect(askDocument(documentId, "Question?")).rejects.toThrow("could not be answered");
});

it("uses a general message when the error response is not JSON", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("Bad gateway", { status: 502 })));

  await expect(askDocument(documentId, "Question?")).rejects.toThrow("could not be answered");
});

it("reports an expired session", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 401 })));

  await expect(askDocument(documentId, "Question?")).rejects.toBeInstanceOf(SessionExpiredError);
});

it("reports a connection failure", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));

  await expect(askDocument(documentId, "Question?")).rejects.toThrow("could not be sent");
});

it.each([
  { answer: "", sources: [] },
  { answer: "Text", sources: "none" },
  { answer: "Text", sources: [{ chunk_index: 1, page_number: 4 }] },
])("rejects an answer with an unexpected shape", async (payload) => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(payload)));

  await expect(askDocument(documentId, "Question?")).rejects.toThrow("unexpected response");
});
