import { getDocumentApiConfiguration } from "../../../../lib/server/document-api";

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ documentId: string }> },
): Promise<Response> {
  const { documentId } = await params;
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(documentId)) {
    return Response.json({ detail: "Invalid document ID." }, { status: 422 });
  }

  let configuration: ReturnType<typeof getDocumentApiConfiguration>;
  try {
    configuration = getDocumentApiConfiguration();
  } catch (error) {
    console.error("Invalid document deletion configuration", error);
    return Response.json({ detail: "Document deletion is not configured." }, { status: 503 });
  }

  configuration.url.pathname += `/${documentId}`;
  const timeoutSignal = AbortSignal.timeout(configuration.timeoutMs);
  try {
    const response = await fetch(configuration.url, {
      method: "DELETE",
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.any([request.signal, timeoutSignal]),
    });
    if (response.status === 204) {
      return new Response(null, { status: 204, headers: { "Cache-Control": "no-store" } });
    }
    return new Response(await response.text(), {
      status: response.status,
      headers: {
        "Content-Type": response.headers.get("content-type") ?? "application/json",
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    console.error("Document deletion request failed", error);
    return Response.json(
      { detail: "Deletion could not be confirmed. Refresh the list before retrying." },
      { status: timeoutSignal.aborted ? 504 : 502 },
    );
  }
}
