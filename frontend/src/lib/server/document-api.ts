export function getDocumentsUrl() {
  const apiUrl = process.env.DOCUMIND_API_URL;
  if (!apiUrl) throw new Error("DOCUMIND_API_URL is required");

  const url = new URL(apiUrl);
  if (!["http:", "https:"].includes(url.protocol) || url.search || url.hash) {
    throw new Error("DOCUMIND_API_URL must be an HTTP service URL");
  }
  url.pathname = `${url.pathname.replace(/\/$/, "")}/documents`;

  return url;
}


export function getDocumentApiConfiguration() {
  const url = getDocumentsUrl();
  const timeoutMs = Number(process.env.DOCUMIND_API_TIMEOUT_MS ?? "10000");
  if (!Number.isSafeInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 2147483647) {
    throw new Error("Invalid DOCUMIND_API_TIMEOUT_MS");
  }
  return { url, timeoutMs };
}
