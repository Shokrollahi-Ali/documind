import { afterEach, expect, it, vi } from "vitest";

import { listDocuments } from "./list-documents";

afterEach(() => { vi.unstubAllGlobals(); });

it("passes pagination and cancellation to the list request", async () => {
  const page = { items: [], has_more: false, limit: 10, offset: 20 };
  const fetchMock = vi.fn().mockResolvedValue(Response.json(page));
  vi.stubGlobal("fetch", fetchMock);
  const signal = new AbortController().signal;

  expect(await listDocuments(10, 20, signal)).toEqual(page);
  expect(fetchMock).toHaveBeenCalledWith("/api/documents?limit=10&offset=20", { signal, cache: "no-store" });
});

it.each([
  { items: [], has_more: false, limit: 10, offset: 99 },
  { items: [{ id: "incomplete" }], has_more: false, limit: 10, offset: 0 },
  { items: [], has_more: "false", limit: 10, offset: 0 },
])("rejects malformed or mismatched pages", async (page) => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(page)));
  await expect(listDocuments(10, 0, new AbortController().signal)).rejects.toThrow("unexpected response");
});
