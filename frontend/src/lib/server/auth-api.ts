import { getApiTimeoutMs, getApiUrl } from "@/lib/server/api-configuration";
import { jsonError, readJsonBody } from "@/lib/server/json-request";
import { validateMutationOrigin } from "@/lib/server/request-origin";
import { copySessionCookies, getSessionHeaders } from "@/lib/server/session-cookies";

type AuthAction = "register" | "login" | "me" | "logout";
const MAX_AUTH_BODY_BYTES = 16 * 1024;

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
    return jsonError("Authentication is not configured correctly.", 503);
  }

  let body: string | undefined;
  if (action === "register" || action === "login") {
    const parsedBody = await readJsonBody(request, MAX_AUTH_BODY_BYTES);
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
    return jsonError(
      "The authentication request could not be confirmed. Please try again.",
      timeoutSignal.aborted ? 504 : 502,
    );
  }
}
