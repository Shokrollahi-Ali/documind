import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { listDocuments } from "../api/list-documents";
import { getDocumentRefreshInterval } from "../lib/document-refresh";

export const documentsQueryKey = ["documents"] as const;

export const documentsPageSize = 10;
const documentsStaleTimeMs = 30000;

function getPageOffset(page: number, pageSize: number): number {
  return page * pageSize;
}

export function getDocumentsQueryKey(page: number, pageSize = documentsPageSize) {
  return [...documentsQueryKey, { limit: pageSize, offset: getPageOffset(page, pageSize) }] as const;
}

export function useDocuments(page: number, pageSize = documentsPageSize) {
  return useQuery({
    queryKey: getDocumentsQueryKey(page, pageSize),
    queryFn: ({ signal }) => listDocuments(pageSize, getPageOffset(page, pageSize), signal),
    placeholderData: keepPreviousData,
    staleTime: documentsStaleTimeMs,
    refetchInterval: (query) => getDocumentRefreshInterval(query.state.data?.items),
    retry: false,
  });
}
