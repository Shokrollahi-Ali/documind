function getUploadConfiguration() {
  const apiUrl = process.env.DOCUMIND_API_URL;
  if (!apiUrl) throw new Error("DOCUMIND_API_URL is required");

  const url = new URL(apiUrl);
  if (!["http:", "https:"].includes(url.protocol) || url.search || url.hash) {
    throw new Error("DOCUMIND_API_URL must be an HTTP service URL");
  }
  url.pathname = `${url.pathname.replace(/\/$/, "")}/documents`;

  const timeoutMs = Number(process.env.DOCUMIND_UPLOAD_TIMEOUT_MS ?? "120000");
  if (!Number.isSafeInteger(timeoutMs) || timeoutMs <= 0 || timeoutMs > 2147483647) {
    throw new Error("DOCUMIND_UPLOAD_TIMEOUT_MS must be a positive timeout in milliseconds");
  }

  return { url, timeoutMs };
}

export async function POST(request: Request): Promise<Response> {
  let configuration: ReturnType<typeof getUploadConfiguration>;
  try {
    configuration = getUploadConfiguration();
  } catch (error) {
    console.error("Invalid document upload configuration", error);
    return Response.json(
      { detail: "Document uploads are not configured. Contact the administrator." },
      { status: 503 },
    );
  }

  const contentType = request.headers.get("content-type");
  if (!contentType?.toLowerCase().startsWith("multipart/form-data;") || !request.body) {
    return Response.json({ detail: "A multipart file upload is required." }, { status: 415 });
  }

  const timeoutSignal = AbortSignal.timeout(configuration.timeoutMs);
  const signal = AbortSignal.any([request.signal, timeoutSignal]);

  try {
    const options: RequestInit & { duplex: "half" } = {
      method: "POST",
      headers: { "Content-Type": contentType },
      body: request.body,
      duplex: "half",
      signal,
      redirect: "error",
      cache: "no-store",
    };
    const response = await fetch(configuration.url, options);
    const body = await response.text();

    return new Response(body, {
      status: response.status,
      headers: {
        "Content-Type": response.headers.get("content-type") ?? "application/json",
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    console.error("Document upload service request failed", error);
    const detail = timeoutSignal.aborted
      ? "The upload timed out. The document may have been saved; check before retrying."
      : "The upload could not be confirmed. The document service may be unavailable; check before retrying.";

    return Response.json({ detail }, { status: timeoutSignal.aborted ? 504 : 502 });
  }
}
