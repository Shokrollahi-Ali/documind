export function getApiUrl(path: string): URL {
  const apiUrl = process.env.DOCUMIND_API_URL;
  if (!apiUrl) throw new Error("DOCUMIND_API_URL is required");

  const url = new URL(apiUrl);
  if (
    !["http:", "https:"].includes(url.protocol) ||
    url.username || url.password || url.search || url.hash
  ) {
    throw new Error("DOCUMIND_API_URL must be an HTTP service URL without credentials");
  }
  url.pathname = `${url.pathname.replace(/\/$/, "")}/${path}`;
  return url;
}

export function getApiTimeoutMs(): number {
  const timeoutMs = Number(process.env.DOCUMIND_API_TIMEOUT_MS ?? "10000");
  if (!Number.isSafeInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 2147483647) {
    throw new Error("Invalid DOCUMIND_API_TIMEOUT_MS");
  }
  return timeoutMs;
}
