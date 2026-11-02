import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { documentRefreshIntervalMs } from "../lib/document-refresh";
import { getDocumentsQueryKey, useDocuments } from "./use-documents";

function createPageResponse(status: string) {
  const document = {
    id: "fdc6e6a9-4585-477e-b53a-2576edb7a0e1",
    original_filename: "report.pdf",
    content_type: "application/pdf",
    size_bytes: 128,
    status,
    created_at: "2026-10-15T12:00:00Z",
  };

  return Response.json({ items: [document], limit: 10, offset: 0, has_more: false });
}

function createWrapper() {
  const queryClient = new QueryClient();

  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

it("keeps refreshing while a document is preparing and stops once it is ready", async () => {
  let status = "processing";
  const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(createPageResponse(status)));
  vi.stubGlobal("fetch", fetchMock);

  const { result } = renderHook(() => useDocuments(0), { wrapper: createWrapper() });
  await waitFor(() => expect(result.current.data?.items[0].status).toBe("processing"));

  status = "ready";
  await act(async () => {
    vi.advanceTimersByTime(documentRefreshIntervalMs);
  });
  await waitFor(() => expect(result.current.data?.items[0].status).toBe("ready"));

  const callsAfterReady = fetchMock.mock.calls.length;
  await act(async () => {
    vi.advanceTimersByTime(documentRefreshIntervalMs * 3);
  });
  expect(fetchMock).toHaveBeenCalledTimes(callsAfterReady);
});

it("does not refresh when every document is already ready", async () => {
  const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(createPageResponse("ready")));
  vi.stubGlobal("fetch", fetchMock);

  const { result } = renderHook(() => useDocuments(0), { wrapper: createWrapper() });
  await waitFor(() => expect(result.current.data?.items[0].status).toBe("ready"));

  await act(async () => {
    vi.advanceTimersByTime(documentRefreshIntervalMs * 3);
  });
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

it("requests each page with its own offset", () => {
  expect(getDocumentsQueryKey(0)).toEqual(["documents", { limit: 10, offset: 0 }]);
  expect(getDocumentsQueryKey(2)).toEqual(["documents", { limit: 10, offset: 20 }]);
});
