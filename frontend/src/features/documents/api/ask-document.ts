import { checkSession } from "@/lib/client/session-expired";
import { isDocumentAnswer } from "../lib/document-answer";
import type { DocumentAnswer } from "../lib/document-answer";

function getAnswerError(payload: unknown): string {
  if (
    typeof payload === "object" && payload !== null &&
    "detail" in payload && typeof payload.detail === "string"
  ) {
    return payload.detail;
  }

  return "The question could not be answered. Try again.";
}

export async function askDocument(documentId: string, question: string): Promise<DocumentAnswer> {
  let response: Response;
  try {
    response = await fetch(`/api/documents/${encodeURIComponent(documentId)}/answer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
      cache: "no-store",
    });
  } catch {
    throw new Error("The question could not be sent. Check your connection and try again.");
  }

  checkSession(response);
  const payload: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(getAnswerError(payload));
  }

  if (!isDocumentAnswer(payload)) {
    throw new Error("The document service returned an unexpected response.");
  }

  return payload;
}
