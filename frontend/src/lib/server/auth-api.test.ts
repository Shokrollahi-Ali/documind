import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { POST as login } from "@/app/api/auth/login/route";
import { POST as logout } from "@/app/api/auth/logout/route";
import { GET as currentUser } from "@/app/api/auth/me/route";
import { POST as register } from "@/app/api/auth/register/route";

const credentials = { email: "alice@example.com", password: "private-test-password" };

function authRequest(action: string, options: RequestInit = {}): Request {
  const method = action === "me" ? "GET" : "POST";
  return new Request(`https://app.example/api/auth/${action}`, {
    method,
    headers: {
      Origin: "https://app.example",
      "Content-Type": "application/json",
      Cookie: "unrelated=private-value; documind_session=existing-token",
      Authorization: "Bearer unrelated-secret",
    },
    body: action === "login" || action === "register" ? JSON.stringify(credentials) : undefined,
    ...options,
  });
}

beforeEach(() => {
  vi.stubEnv("DOCUMIND_API_URL", "http://backend:8000/v1/");
  vi.stubEnv("DOCUMIND_API_TIMEOUT_MS", "10000");
  vi.stubEnv("DOCUMIND_APP_ORIGIN", "https://app.example");
  vi.stubEnv("DOCUMIND_SESSION_COOKIE_NAME", "documind_session");
  vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe.each([
  { action: "register", handler: register, status: 201 },
  { action: "login", handler: login, status: 200 },
  { action: "me", handler: currentUser, status: 200 },
  { action: "logout", handler: logout, status: 204 },
])("$action proxy", ({ action, handler, status }) => {
  it("calls the expected backend route and forwards only the session cookie", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      status === 204 ? new Response(null, { status }) : Response.json({ id: "user-id" }, { status }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const response = await handler(authRequest(action));

    expect(response.status).toBe(status);
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, options] = fetchMock.mock.calls[0];
    expect(url.toString()).toBe(`http://backend:8000/v1/auth/${action}`);
    expect(options.method).toBe(action === "me" ? "GET" : "POST");
    expect(options.headers.get("cookie")).toBe("documind_session=existing-token");
    expect(options.headers.has("authorization")).toBe(false);
    expect(options.cache).toBe("no-store");
    expect(options.redirect).toBe("error");
    if (action === "login" || action === "register") {
      expect(JSON.parse(options.body)).toEqual(credentials);
      expect(options.headers.get("content-type")).toBe("application/json");
    } else {
      expect(options.body).toBeUndefined();
    }
    if (status === 204) expect(await response.text()).toBe("");
  });

  it.each([401, 409, 422, 503])("preserves backend error %i without caching", async (status) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ detail: "Rejected" }, { status })));
    const response = await handler(authRequest(action));
    expect(response.status).toBe(status);
    expect(await response.json()).toEqual({ detail: "Rejected" });
    expect(response.headers.get("cache-control")).toBe("no-store");
  });
});

it("preserves the session cookie attributes and separate Set-Cookie headers", async () => {
  const cookies = [
    "documind_session=old; Path=/; Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly; Secure; SameSite=lax",
    "documind_session=new; Path=/; Max-Age=3600; HttpOnly; Secure; SameSite=lax",
  ];
  const headers = new Headers();
  for (const cookie of cookies) headers.append("Set-Cookie", cookie);
  headers.append("Set-Cookie", "unrelated=private; Path=/");
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ id: "user-id" }, { headers })));

  const response = await login(authRequest("login"));

  expect(response.headers.getSetCookie()).toEqual(cookies);
  expect(await response.json()).toEqual({ id: "user-id" });
});

it("relays cookie deletion on bodyless logout responses", async () => {
  const cookie = "documind_session=; Path=/; Max-Age=0; HttpOnly; SameSite=lax";
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
    new Response(null, { status: 204, headers: { "Set-Cookie": cookie } }),
  ));
  const response = await logout(authRequest("logout"));
  expect(response.status).toBe(204);
  expect(await response.text()).toBe("");
  expect(response.headers.getSetCookie()).toEqual([cookie]);
});

it("supports a custom session cookie name in both directions", async () => {
  vi.stubEnv("DOCUMIND_SESSION_COOKIE_NAME", "custom_session");
  const request = authRequest("login");
  request.headers.set("Cookie", "documind_session=ignored; custom_session=forwarded");
  const fetchMock = vi.fn().mockResolvedValue(Response.json({ id: "user-id" }, {
    headers: { "Set-Cookie": "custom_session=new; Path=/; HttpOnly" },
  }));
  vi.stubGlobal("fetch", fetchMock);
  const response = await login(request);
  expect(fetchMock.mock.calls[0][1].headers.get("cookie")).toBe("custom_session=forwarded");
  expect(response.headers.getSetCookie()).toEqual(["custom_session=new; Path=/; HttpOnly"]);
});

it("does not invent a session when the request has no matching cookie", async () => {
  const request = authRequest("me");
  request.headers.set("Cookie", "unrelated=private");
  const fetchMock = vi.fn().mockResolvedValue(Response.json({ detail: "Authentication required" }, { status: 401 }));
  vi.stubGlobal("fetch", fetchMock);
  expect((await currentUser(request)).status).toBe(401);
  expect(fetchMock.mock.calls[0][1].headers.has("cookie")).toBe(false);
});

it.each(["", "file:///tmp/api", "invalid", "http://user:password@backend", "http://backend?secret=x"])(
  "rejects invalid backend configuration: %s", async (apiUrl) => {
    vi.stubEnv("DOCUMIND_API_URL", apiUrl);
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const response = await login(authRequest("login"));
    expect(response.status).toBe(503);
    expect(fetchMock).not.toHaveBeenCalled();
  },
);

it.each(["0", "NaN", "2147483648"])("rejects invalid timeout %s", async (timeout) => {
  vi.stubEnv("DOCUMIND_API_TIMEOUT_MS", timeout);
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  expect((await currentUser(authRequest("me"))).status).toBe(503);
  expect(fetchMock).not.toHaveBeenCalled();
});

it("rejects an invalid session cookie configuration", async () => {
  vi.stubEnv("DOCUMIND_SESSION_COOKIE_NAME", "session; other=value");
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  expect((await currentUser(authRequest("me"))).status).toBe(503);
  expect(fetchMock).not.toHaveBeenCalled();
});

it.each([login, register])("rejects malformed JSON before contacting FastAPI", async (handler) => {
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  expect((await handler(authRequest("login", { body: "{" }))).status).toBe(400);
  expect(fetchMock).not.toHaveBeenCalled();
});

it("rejects form credentials rather than accepting cross-site form submissions", async () => {
  const request = authRequest("login", { body: "email=alice&password=private" });
  request.headers.set("Content-Type", "application/x-www-form-urlencoded");
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  expect((await login(request)).status).toBe(415);
  expect(fetchMock).not.toHaveBeenCalled();
});

it("bounds the JSON body even when Content-Length is missing", async () => {
  const request = authRequest("login", { body: JSON.stringify({ password: "x".repeat(16384) }) });
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  expect(request.headers.has("content-length")).toBe(false);
  expect((await login(request)).status).toBe(413);
  expect(fetchMock).not.toHaveBeenCalled();
});

it("does not retry or expose backend errors, credentials, or cookies in logs", async () => {
  const fetchMock = vi.fn().mockRejectedValue(new Error("private-test-password existing-token"));
  vi.stubGlobal("fetch", fetchMock);
  const response = await login(authRequest("login"));
  expect(response.status).toBe(502);
  expect(await response.text()).not.toContain("private-test-password");
  expect(JSON.stringify(vi.mocked(console.error).mock.calls)).not.toContain("existing-token");
  expect(JSON.stringify(vi.mocked(console.error).mock.calls)).not.toContain("private-test-password");
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

it("times out slow authentication requests", async () => {
  vi.stubEnv("DOCUMIND_API_TIMEOUT_MS", "10");
  vi.stubGlobal("fetch", vi.fn((_url: URL, options: RequestInit) => new Promise((_resolve, reject) => {
    options.signal?.addEventListener("abort", () => reject(options.signal?.reason), { once: true });
  })));
  expect((await login(authRequest("login"))).status).toBe(504);
});

it("propagates client cancellation to the upstream request", async () => {
  const controller = new AbortController();
  vi.stubGlobal("fetch", vi.fn((_url: URL, options: RequestInit) => new Promise((_resolve, reject) => {
    options.signal?.addEventListener("abort", () => reject(options.signal?.reason), { once: true });
    controller.abort();
  })));
  const response = await currentUser(authRequest("me", { signal: controller.signal }));
  expect(response.status).toBe(502);
});
