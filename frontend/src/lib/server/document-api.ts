import { getAnswerTimeoutMs, getApiTimeoutMs, getApiUrl } from "@/lib/server/api-configuration";

export function isDocumentId(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
}

export function getDocumentsUrl() {
  return getApiUrl("documents");
}

export function getDocumentApiConfiguration() {
  return { url: getDocumentsUrl(), timeoutMs: getApiTimeoutMs() };
}

export function getDocumentAnswerConfiguration(documentId: string) {
  return { url: getApiUrl(`documents/${documentId}/answer`), timeoutMs: getAnswerTimeoutMs() };
}
