export type UploadedDocument = {
  id: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  status: "uploaded" | "processing" | "ready" | "failed";
  created_at: string;
};

function isUploadedDocument(value: unknown): value is UploadedDocument {
  if (typeof value !== "object" || value === null) return false;

  const document = value as Record<string, unknown>;
  const validStatuses = ["uploaded", "processing", "ready", "failed"];

  return (
    typeof document.id === "string" && document.id.length > 0 &&
    typeof document.original_filename === "string" &&
    typeof document.content_type === "string" &&
    typeof document.size_bytes === "number" &&
    Number.isSafeInteger(document.size_bytes) && document.size_bytes > 0 &&
    typeof document.status === "string" && validStatuses.includes(document.status) &&
    typeof document.created_at === "string" &&
    Number.isFinite(Date.parse(document.created_at))
  );
}

function getUploadError(payload: unknown): string {
  if (
    typeof payload === "object" && payload !== null &&
    "detail" in payload && typeof payload.detail === "string"
  ) {
    return payload.detail;
  }

  return "The upload failed. Please try again later.";
}

export async function uploadDocument(file: File): Promise<UploadedDocument> {
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

  if (!isUploadedDocument(payload)) {
    throw new Error("The service returned an unexpected response. The document may have been saved; check before retrying.");
  }

  return payload;
}
