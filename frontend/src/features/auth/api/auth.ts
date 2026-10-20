export type User = { id: string; email: string; created_at: string };
export type Credentials = { email: string; password: string };

function parseUser(value: unknown): User {
  if (typeof value !== "object" || value === null) throw new Error("Unexpected account response.");
  const user = value as Record<string, unknown>;
  if (
    typeof user.id !== "string" || !user.id ||
    typeof user.email !== "string" || !user.email ||
    typeof user.created_at !== "string" || Number.isNaN(Date.parse(user.created_at))
  ) throw new Error("Unexpected account response.");
  return { id: user.id, email: user.email, created_at: user.created_at };
}

export async function getCurrentUser(signal: AbortSignal): Promise<User | null> {
  const response = await fetch("/api/auth/me", { signal, cache: "no-store" });
  if (response.status === 401) return null;
  if (!response.ok) throw new Error("We could not check your session. Please try again.");
  return parseUser(await response.json());
}

export async function submitCredentials(action: "login" | "register", credentials: Credentials): Promise<User> {
  let response: Response;
  try {
    response = await fetch(`/api/auth/${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(credentials),
      cache: "no-store",
    });
  } catch {
    throw new Error("The request could not be confirmed. Check your connection before trying again.");
  }
  if (response.status === 401) throw new Error("The email or password is incorrect.");
  if (response.status === 409) throw new Error("An account with this email already exists. Sign in instead.");
  if (response.status === 422) throw new Error("Check your email and password and try again.");
  if (!response.ok) throw new Error("The request could not be confirmed. Please try again later.");
  return parseUser(await response.json());
}

export async function logout(): Promise<void> {
  const response = await fetch("/api/auth/logout", { method: "POST", cache: "no-store" });
  if (response.status !== 204) throw new Error("Sign-out could not be confirmed. Please try again.");
}
