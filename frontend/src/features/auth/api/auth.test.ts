import { afterEach, expect, it, vi } from "vitest";
import { getCurrentUser, logout, submitCredentials } from "./auth";
import { listDocuments } from "@/features/documents/api/list-documents";
import { uploadDocument } from "@/features/documents/api/upload-document";
import { deleteDocument } from "@/features/documents/api/delete-document";
import { SessionExpiredError } from "@/lib/client/session-expired";

afterEach(() => vi.unstubAllGlobals());

it.each([null, {}, { id: "x", email: "e", created_at: "invalid" }])("rejects malformed account data", async (payload) => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(payload)));
  await expect(getCurrentUser(new AbortController().signal)).rejects.toThrow("Unexpected account response");
});

it.each([[401, "email or password"], [409, "already exists"], [422, "Check your email"], [503, "could not be confirmed"]])("handles authentication status %s", async (status, message) => {
  const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: Number(status) }));
  vi.stubGlobal("fetch", fetchMock);
  await expect(submitCredentials("register", { email: "reader@example.com", password: "long-test-passphrase" })).rejects.toThrow(String(message));
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

it("does not report failed logout as successful", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 500 })));
  await expect(logout()).rejects.toThrow("Sign-out could not be confirmed");
});

it.each(["list", "upload", "delete"])("identifies session expiration in %s", async (action) => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 401 })));
  const request = action === "list" ? listDocuments(10, 0, new AbortController().signal)
    : action === "upload" ? uploadDocument(new File(["pdf"], "test.pdf", { type: "application/pdf" })) : deleteDocument("id");
  await expect(request).rejects.toBeInstanceOf(SessionExpiredError);
});
