function getApplicationOrigin(request: Request): string {
  const configuredOrigin = process.env.DOCUMIND_APP_ORIGIN;
  if (!configuredOrigin) {
    if (process.env.NODE_ENV === "production") {
      throw new Error("DOCUMIND_APP_ORIGIN is required in production");
    }
    return new URL(request.url).origin;
  }

  const url = new URL(configuredOrigin);
  if (
    !["http:", "https:"].includes(url.protocol) || url.pathname !== "/" ||
    url.username || url.password || url.search || url.hash
  ) {
    throw new Error("DOCUMIND_APP_ORIGIN must be an HTTP origin");
  }
  return url.origin;
}

export function validateMutationOrigin(request: Request): Response | null {
  let expectedOrigin: string;
  try {
    expectedOrigin = getApplicationOrigin(request);
  } catch {
    console.error("Invalid application origin configuration");
    return Response.json(
      { detail: "The application origin is not configured correctly." },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }

  if (
    request.headers.get("origin") !== expectedOrigin ||
    request.headers.get("sec-fetch-site") === "cross-site"
  ) {
    return Response.json(
      { detail: "A same-origin request is required." },
      { status: 403, headers: { "Cache-Control": "no-store" } },
    );
  }
  return null;
}
