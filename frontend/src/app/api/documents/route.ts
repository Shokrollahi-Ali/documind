function getDocumentsUrl() {
  const apiUrl = process.env.DOCUMIND_API_URL;
  if (!apiUrl) throw new Error("DOCUMIND_API_URL is required");

  const url = new URL(apiUrl);
  if (!["http:", "https:"].includes(url.protocol) || url.search || url.hash) {
    throw new Error("DOCUMIND_API_URL must be an HTTP service URL");
  }
  url.pathname = `${url.pathname.replace(/\/$/, "")}/documents`;

  return url;
}

function getUploadConfiguration() {
  const url = getDocumentsUrl();

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

export async function GET(request: Request): Promise<Response> {
  const query = new URL(request.url).searchParams;
  const limit = Number(query.get("limit") ?? "10");
  const offset = Number(query.get("offset") ?? "0");
  if (!Number.isSafeInteger(limit) || limit < 1 || limit > 100 || !Number.isSafeInteger(offset) || offset < 0) {
    return Response.json({ detail: "Invalid pagination parameters." }, { status: 422 });
  }

  let url: URL;
  let timeoutMs: number;
  try {
    url = getDocumentsUrl();
    timeoutMs = Number(process.env.DOCUMIND_API_TIMEOUT_MS ?? "10000");
    if (!Number.isSafeInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 2147483647) {
      throw new Error("Invalid DOCUMIND_API_TIMEOUT_MS");
    }
  } catch (error) {
    console.error("Invalid document list configuration", error);
    return Response.json({ detail: "Document listing is not configured." }, { status: 503 });
  }

  url.searchParams.set("limit", String(limit));
  url.searchParams.set("offset", String(offset));
  const timeoutSignal = AbortSignal.timeout(timeoutMs);

  try {
    const response = await fetch(url, {
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
    console.error("Document listing request failed", error);
    return Response.json(
      { detail: "The document service is temporarily unavailable." },
      { status: timeoutSignal.aborted ? 504 : 502 },
    );
  }
}
