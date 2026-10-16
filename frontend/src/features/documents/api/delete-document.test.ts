import { afterEach, expect, it, vi } from "vitest";

import { deleteDocument } from "./delete-document";

afterEach(() => vi.unstubAllGlobals());

it.each([204, 404])("accepts deleted or already missing documents (%i)", async (status) => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status })));
  await expect(deleteDocument("document-id")).resolves.toBeUndefined();
});

it.each([200, 403, 503])("rejects unsuccessful or unexpected status %i", async (status) => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status })));
  await expect(deleteDocument("document-id")).rejects.toThrow("Could not delete");
});

it("reports an uncertain outcome when the connection fails", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  await expect(deleteDocument("document-id")).rejects.toThrow("could not be confirmed");
});
