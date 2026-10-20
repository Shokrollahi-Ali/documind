import { getApiTimeoutMs, getApiUrl } from "@/lib/server/api-configuration";

export function getDocumentsUrl() {
  return getApiUrl("documents");
}

export function getDocumentApiConfiguration() {
  return { url: getDocumentsUrl(), timeoutMs: getApiTimeoutMs() };
}
