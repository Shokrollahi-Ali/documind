import { getApiTimeoutMs, getApiUrl } from "@/lib/server/api-configuration";
import { validateMutationOrigin } from "@/lib/server/request-origin";
import { copySessionCookies, getSessionHeaders } from "@/lib/server/session-cookies";

type AuthAction = "register" | "login" | "me" | "logout";
const MAX_AUTH_BODY_BYTES = 16 * 1024;

function authError(detail: string, status: number): Response {
  return Response.json({ detail }, { status, headers: { "Cache-Control": "no-store" } });
}

async function readAuthBody(request: Request): Promise<string | Response> {
  const contentType = request.headers.get("content-type")?.split(";")[0].trim().toLowerCase();
  if (contentType !== "application/json") {
    return authError("A JSON request body is required.", 415);
  }
  if (!request.body) return authError("A JSON request body is required.", 400);

  const reader = request.body.getReader();
  const decoder = new TextDecoder();
  let size = 0;
  let body = "";
  try {
    while (true) {
      const chunk = await reader.read();
      if (chunk.done) break;
      size += chunk.value.byteLength;
      if (size > MAX_AUTH_BODY_BYTES) {
        await reader.cancel();
        return authError("Authentication requests must not exceed 16 KiB.", 413);
      }
      body += decoder.decode(chunk.value, { stream: true });
    }
    body += decoder.decode();
    JSON.parse(body);
    return body;
  } catch {
    return authError("The request body must contain valid JSON.", 400);
  } finally {
    reader.releaseLock();
  }
}

export async function proxyAuthRequest(request: Request, action: AuthAction): Promise<Response> {
  const method = action === "me" ? "GET" : "POST";
  if (method === "POST") {
    const rejection = validateMutationOrigin(request);
    if (rejection) return rejection;
  }

  let url: URL;
  let timeoutMs: number;
  let headers: Headers;
  try {
    url = getApiUrl(`auth/${action}`);
    timeoutMs = getApiTimeoutMs();
    headers = getSessionHeaders(request);
  } catch {
    console.error("Invalid authentication service configuration");
    return authError("Authentication is not configured correctly.", 503);
  }

  let body: string | undefined;
  if (action === "register" || action === "login") {
    const parsedBody = await readAuthBody(request);
    if (parsedBody instanceof Response) return parsedBody;
    body = parsedBody;
    headers.set("Content-Type", "application/json");
  }

  const timeoutSignal = AbortSignal.timeout(timeoutMs);
  try {
    const upstream = await fetch(url, {
      method,
      headers,
      body,
      signal: AbortSignal.any([request.signal, timeoutSignal]),
      cache: "no-store",
      redirect: "error",
    });
    const responseHeaders = new Headers({ "Cache-Control": "no-store" });
    const contentType = upstream.headers.get("content-type");
    if (contentType) responseHeaders.set("Content-Type", contentType);
    copySessionCookies(upstream.headers, responseHeaders);

    return new Response(upstream.status === 204 ? null : await upstream.text(), {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch {
    console.error("Authentication service request failed");
    return authError(
      "The authentication request could not be confirmed. Please try again.",
      timeoutSignal.aborted ? 504 : 502,
    );
  }
}
