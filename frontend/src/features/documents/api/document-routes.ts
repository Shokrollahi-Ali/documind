export const documentsPath = "/api/documents";

export function getDocumentPath(documentId: string): string {
  return `${documentsPath}/${encodeURIComponent(documentId)}`;
}

export function getDocumentAnswerPath(documentId: string): string {
  return `${getDocumentPath(documentId)}/answer`;
}
