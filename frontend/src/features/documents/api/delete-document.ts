import { checkSession } from "@/lib/client/session-expired";
export async function deleteDocument(documentId: string): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`/api/documents/${encodeURIComponent(documentId)}`, {
      method: "DELETE",
      cache: "no-store",
    });
  } catch {
    throw new Error("Deletion could not be confirmed. Refresh the list before retrying.");
  }

  checkSession(response);
  if (response.status === 204 || response.status === 404) return;
  throw new Error("Could not delete the document. Refresh the list and try again.");
}
