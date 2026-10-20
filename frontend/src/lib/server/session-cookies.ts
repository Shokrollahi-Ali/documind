export function getSessionCookieName(): string {
  const name = process.env.DOCUMIND_SESSION_COOKIE_NAME ?? "documind_session";
  if (!/^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$/.test(name)) {
    throw new Error("DOCUMIND_SESSION_COOKIE_NAME must be a valid cookie name");
  }
  return name;
}

export function getSessionHeaders(request: Request): Headers {
  const name = getSessionCookieName();
  const headers = new Headers();
  const cookies = request.headers.get("cookie")?.split(";") ?? [];
  const sessionCookie = cookies.map((cookie) => cookie.trim())
    .find((cookie) => cookie.startsWith(`${name}=`));

  if (sessionCookie) headers.set("Cookie", sessionCookie);
  return headers;
}

export function copySessionCookies(upstream: Headers, downstream: Headers): void {
  const name = getSessionCookieName();
  for (const cookie of upstream.getSetCookie()) {
    if (cookie.startsWith(`${name}=`)) {
      downstream.append("Set-Cookie", cookie);
    }
  }
}
