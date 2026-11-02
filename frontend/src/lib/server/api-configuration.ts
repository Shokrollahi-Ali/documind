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

const maximumTimeoutMs = 2147483647;
const defaultApiTimeoutMs = 10000;
const defaultAnswerTimeoutMs = 100000;

function readTimeoutMs(variableName: string, defaultTimeoutMs: number): number {
  const timeoutMs = Number(process.env[variableName] ?? defaultTimeoutMs);
  if (!Number.isSafeInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > maximumTimeoutMs) {
    throw new Error(`Invalid ${variableName}`);
  }
  return timeoutMs;
}

export function getApiTimeoutMs(): number {
  return readTimeoutMs("DOCUMIND_API_TIMEOUT_MS", defaultApiTimeoutMs);
}

export function getAnswerTimeoutMs(): number {
  return readTimeoutMs("DOCUMIND_ANSWER_TIMEOUT_MS", defaultAnswerTimeoutMs);
}
