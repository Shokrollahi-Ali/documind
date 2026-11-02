import { getDocumentAnswerConfiguration, isDocumentId } from "@/lib/server/document-api";
import { jsonError, readJsonBody } from "@/lib/server/json-request";
import { validateMutationOrigin } from "@/lib/server/request-origin";
import { getSessionHeaders } from "@/lib/server/session-cookies";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ documentId: string }> },
): Promise<Response> {
  const rejection = validateMutationOrigin(request);
  if (rejection) return rejection;

  const { documentId } = await params;
  if (!isDocumentId(documentId)) return jsonError("Invalid document ID.", 422);

  let configuration: ReturnType<typeof getDocumentAnswerConfiguration>;
  let headers: Headers;
  try {
    configuration = getDocumentAnswerConfiguration(documentId);
    headers = getSessionHeaders(request);
  } catch (error) {
    console.error("Invalid document answer configuration", error);
    return jsonError("Document questions are not configured.", 503);
  }

  const body = await readJsonBody(request);
  if (body instanceof Response) return body;
  headers.set("Content-Type", "application/json");

  const timeoutSignal = AbortSignal.timeout(configuration.timeoutMs);
  try {
    const response = await fetch(configuration.url, {
      method: "POST",
      headers,
      body,
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.any([request.signal, timeoutSignal]),
    });
    return new Response(await response.text(), {
      status: response.status,
      headers: {
        "Content-Type": response.headers.get("content-type") ?? "application/json",
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    console.error("Document answer request failed", error);
    return timeoutSignal.aborted
      ? jsonError("The answer took too long. Try again.", 504)
      : jsonError("The answer service is temporarily unavailable.", 502);
  }
}
