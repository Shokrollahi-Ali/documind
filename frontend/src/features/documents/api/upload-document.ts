import { isDocumentMetadata } from "../lib/document";
import type { DocumentMetadata } from "../lib/document";

function getUploadError(payload: unknown): string {
  if (
    typeof payload === "object" && payload !== null &&
    "detail" in payload && typeof payload.detail === "string"
  ) {
    return payload.detail;
  }

  return "The upload failed. Please try again later.";
}

export async function uploadDocument(file: File): Promise<DocumentMetadata> {
  const formData = new FormData();
  const pdfFile = file.type ? file : new File([file], file.name, { type: "application/pdf" });
  formData.append("file", pdfFile);

  let response: Response;
  try {
    response = await fetch("/api/documents", {
      method: "POST",
      body: formData,
    });
  } catch {
    throw new Error("The upload could not be confirmed. Check your connection before retrying; the document may have been saved.");
  }

  const payload: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(getUploadError(payload));
  }

  if (!isDocumentMetadata(payload)) {
    throw new Error("The service returned an unexpected response. The document may have been saved; check before retrying.");
  }

  return payload;
}
