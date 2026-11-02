import { useQuery } from "@tanstack/react-query";

import { listDocuments } from "../api/list-documents";
import { getDocumentRefreshInterval } from "../lib/document-refresh";

export const documentsQueryKey = ["documents"] as const;

const documentsPageSize = 10;
const documentsStaleTimeMs = 30000;

function getPageOffset(page: number): number {
  return page * documentsPageSize;
}

export function getDocumentsQueryKey(page: number) {
  return [...documentsQueryKey, { limit: documentsPageSize, offset: getPageOffset(page) }] as const;
}

export function useDocuments(page: number) {
  return useQuery({
    queryKey: getDocumentsQueryKey(page),
    queryFn: ({ signal }) => listDocuments(documentsPageSize, getPageOffset(page), signal),
    staleTime: documentsStaleTimeMs,
    refetchInterval: (query) => getDocumentRefreshInterval(query.state.data?.items),
    retry: false,
  });
}
