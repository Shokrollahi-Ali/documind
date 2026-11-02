export const maxJsonBodyBytes = 16 * 1024;

export function jsonError(detail: string, status: number): Response {
  return Response.json({ detail }, { status, headers: { "Cache-Control": "no-store" } });
}

export async function readJsonBody(
  request: Request,
  maxBytes: number = maxJsonBodyBytes,
): Promise<string | Response> {
  const contentType = request.headers.get("content-type")?.split(";")[0].trim().toLowerCase();
  if (contentType !== "application/json") {
    return jsonError("A JSON request body is required.", 415);
  }
  if (!request.body) return jsonError("A JSON request body is required.", 400);

  const reader = request.body.getReader();
  const decoder = new TextDecoder();
  let size = 0;
  let body = "";
  try {
    while (true) {
      const chunk = await reader.read();
      if (chunk.done) break;
      size += chunk.value.byteLength;
      if (size > maxBytes) {
        await reader.cancel();
        return jsonError(`Request bodies must not exceed ${maxBytes} bytes.`, 413);
      }
      body += decoder.decode(chunk.value, { stream: true });
    }
    body += decoder.decode();
    JSON.parse(body);
    return body;
  } catch {
    return jsonError("The request body must contain valid JSON.", 400);
  } finally {
    reader.releaseLock();
  }
}
