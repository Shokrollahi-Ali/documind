export class SessionExpiredError extends Error {
  constructor() {
    super("Your session has expired. Please sign in again.");
    this.name = "SessionExpiredError";
  }
}

export function checkSession(response: Response): void {
  if (response.status === 401) throw new SessionExpiredError();
}
