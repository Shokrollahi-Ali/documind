import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { POST as login } from "@/app/api/auth/login/route";
import { POST as logout } from "@/app/api/auth/logout/route";
import { POST as register } from "@/app/api/auth/register/route";
import { validateMutationOrigin } from "@/lib/server/request-origin";

beforeEach(() => {
  vi.stubEnv("DOCUMIND_APP_ORIGIN", "https://app.example");
  vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

it.each([login, register, logout])("rejects an external origin before contacting FastAPI", async (handler) => {
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  const response = await handler(new Request("https://app.example/api/auth/login", {
    method: "POST", headers: { Origin: "https://attacker.example" },
  }));
  expect(response.status).toBe(403);
  expect(fetchMock).not.toHaveBeenCalled();
});

it.each([undefined, "null", "https://other.app.example", "https://app.example.attacker.test", "http://app.example"])(
  "rejects missing, opaque, or mismatched origins: %s", (origin) => {
    const headers = new Headers();
    if (origin) headers.set("Origin", origin);
    const rejection = validateMutationOrigin(new Request("https://app.example/api/documents", { headers }));
    expect(rejection?.status).toBe(403);
  },
);

it("uses the configured public origin behind a reverse proxy", () => {
  const request = new Request("http://internal:3000/api/auth/logout", {
    headers: { Origin: "https://app.example" },
  });
  expect(validateMutationOrigin(request)).toBeNull();
});

it("does not trust forwarded host headers as the allowed origin", () => {
  const request = new Request("https://app.example/api/auth/logout", {
    headers: { Origin: "https://attacker.example", "X-Forwarded-Host": "attacker.example" },
  });
  expect(validateMutationOrigin(request)?.status).toBe(403);
});

it("rejects explicitly cross-site fetch metadata", () => {
  const request = new Request("https://app.example/api/auth/logout", {
    headers: { Origin: "https://app.example", "Sec-Fetch-Site": "cross-site" },
  });
  expect(validateMutationOrigin(request)?.status).toBe(403);
});

it("requires an explicit public origin in production", () => {
  vi.stubEnv("NODE_ENV", "production");
  vi.stubEnv("DOCUMIND_APP_ORIGIN", "");
  expect(validateMutationOrigin(new Request("https://app.example"))?.status).toBe(503);
});

it("uses the request origin during local development when no origin is configured", () => {
  vi.stubEnv("NODE_ENV", "development");
  vi.stubEnv("DOCUMIND_APP_ORIGIN", "");
  const request = new Request("http://localhost:3000/api/auth/logout", {
    headers: { Origin: "http://localhost:3000" },
  });
  expect(validateMutationOrigin(request)).toBeNull();
});

it.each(["invalid", "file:///tmp/app", "https://app.example/path", "https://app.example?x=1"])(
  "rejects invalid origin configuration: %s", (origin) => {
    vi.stubEnv("DOCUMIND_APP_ORIGIN", origin);
    expect(validateMutationOrigin(new Request("https://app.example"))?.status).toBe(503);
  },
);
