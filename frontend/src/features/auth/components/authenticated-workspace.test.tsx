import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import AuthenticatedWorkspace from "./authenticated-workspace";

const account = { id: "user-one", email: "reader@example.com", created_at: "2026-10-20T12:00:00Z" };
const emptyPage = { items: [], limit: 10, offset: 0, has_more: false };
afterEach(() => vi.unstubAllGlobals());

async function fillCredentials() {
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText("Email"), account.email);
  await user.type(screen.getByLabelText("Password"), "a-long-test-passphrase");
  return user;
}

it("waits for the session before requesting any documents", async () => {
  const fetchMock = vi.fn().mockReturnValue(new Promise(() => {}));
  vi.stubGlobal("fetch", fetchMock);
  render(<AuthenticatedWorkspace />);
  expect(screen.getByRole("status")).toHaveTextContent("Checking your session");
  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(fetchMock.mock.calls[0][0]).toBe("/api/auth/me");
  expect(screen.queryByLabelText("PDF document")).not.toBeInTheDocument();
});

it("signs in, opens documents, and signs out", async () => {
  vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => {
    if (url === "/api/auth/me") return Promise.resolve(new Response(null, { status: 401 }));
    if (url === "/api/auth/login") return Promise.resolve(Response.json(account));
    if (url === "/api/auth/logout") return Promise.resolve(new Response(null, { status: 204 }));
    return Promise.resolve(Response.json(emptyPage));
  }));
  render(<AuthenticatedWorkspace />);
  const user = await fillCredentials();
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByText(account.email)).toBeInTheDocument();
  await screen.findByText("No documents yet. Upload a PDF to get started.");
  await user.click(screen.getByRole("button", { name: "Sign out" }));
  expect(await screen.findByText("You have signed out.")).toBeInTheDocument();
  expect(screen.queryByLabelText("PDF document")).not.toBeInTheDocument();
  expect(screen.getByLabelText("Password")).toHaveValue("");
});

it("registers then asks for sign-in without retaining the password", async () => {
  const fetchMock = vi.fn().mockImplementation((url: string) => Promise.resolve(
    url === "/api/auth/me" ? new Response(null, { status: 401 }) : Response.json(account, { status: 201 }),
  ));
  vi.stubGlobal("fetch", fetchMock);
  render(<AuthenticatedWorkspace />);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Create an account" }));
  expect(screen.getByLabelText("Password")).toHaveAttribute("minlength", "15");
  await fillCredentials();
  await user.click(screen.getByRole("button", { name: "Create account" }));
  expect(await screen.findByText("Account created. Sign in to open your documents.")).toBeInTheDocument();
  expect(screen.getByLabelText("Password")).toHaveValue("");
  expect(fetchMock.mock.calls.map(([url]) => url)).toEqual(["/api/auth/me", "/api/auth/register"]);
});

it("shows incorrect credentials and permits another attempt", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 401 })));
  render(<AuthenticatedWorkspace />);
  const user = await fillCredentials();
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("email or password is incorrect");
  expect(screen.getByRole("button", { name: "Sign in" })).toBeEnabled();
});

it("disables the form and mode switch while a request is pending", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(new Response(null, { status: 401 })).mockReturnValue(new Promise(() => {})));
  render(<AuthenticatedWorkspace />);
  const user = await fillCredentials();
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  expect(screen.getByLabelText("Email")).toBeDisabled();
  expect(screen.getByRole("button", { name: "Please wait…" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Create an account" })).toBeDisabled();
});

it("allows retrying a session failure", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(new Response(null, { status: 503 })).mockImplementation((url: string) => Promise.resolve(Response.json(url === "/api/auth/me" ? account : emptyPage))));
  render(<AuthenticatedWorkspace />);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Try again" }));
  expect(await screen.findByText(account.email)).toBeInTheDocument();
});

it("returns to sign-in when a document request reports an expired session", async () => {
  vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => Promise.resolve(
    url === "/api/auth/me" ? Response.json(account) : new Response(null, { status: 401 }),
  )));
  render(<AuthenticatedWorkspace />);
  expect(await screen.findByText("Your session has expired. Please sign in again.")).toBeInTheDocument();
  expect(screen.queryByLabelText("PDF document")).not.toBeInTheDocument();
});

it("keeps sign-out retryable after server failure", async () => {
  vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => Promise.resolve(
    url === "/api/auth/me" ? Response.json(account) : url === "/api/auth/logout" ? new Response(null, { status: 503 }) : Response.json(emptyPage),
  )));
  render(<AuthenticatedWorkspace />);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Sign out" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Sign-out could not be confirmed");
  expect(screen.getByRole("button", { name: "Sign out" })).toBeEnabled();
});

it("discards document cache when signing into another account", async () => {
  let currentAccount = account;
  const document = { id: "doc-one", original_filename: "private-first-user.pdf", content_type: "application/pdf", size_bytes: 100, status: "uploaded", created_at: account.created_at };
  vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => {
    if (url === "/api/auth/me") return Promise.resolve(Response.json(currentAccount));
    if (url === "/api/auth/logout") return Promise.resolve(new Response(null, { status: 204 }));
    if (url === "/api/auth/login") { currentAccount = { ...account, id: "user-two" }; return Promise.resolve(Response.json(currentAccount)); }
    return Promise.resolve(Response.json({ ...emptyPage, items: currentAccount.id === "user-one" ? [document] : [] }));
  }));
  render(<AuthenticatedWorkspace />);
  await screen.findByRole("heading", { name: document.original_filename });
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Sign out" }));
  await fillCredentials();
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  await screen.findByText("No documents yet. Upload a PDF to get started.");
  expect(screen.queryByText(document.original_filename)).not.toBeInTheDocument();
});

it("ignores an old upload failure after signing into a new session", async () => {
  let finishUpload!: (response: Response) => void;
  let signedIn = true;
  vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string, options?: RequestInit) => {
    if (url === "/api/auth/me") return Promise.resolve(signedIn ? Response.json(account) : new Response(null, { status: 401 }));
    if (url === "/api/auth/logout") { signedIn = false; return Promise.resolve(new Response(null, { status: 204 })); }
    if (url === "/api/auth/login") { signedIn = true; return Promise.resolve(Response.json(account)); }
    if (url === "/api/documents" && options?.method === "POST") return new Promise<Response>((resolve) => { finishUpload = resolve; });
    return Promise.resolve(Response.json(emptyPage));
  }));
  render(<AuthenticatedWorkspace />);
  const user = userEvent.setup();
  await user.upload(await screen.findByLabelText("PDF document"), new File(["%PDF-1.7"], "pending.pdf", { type: "application/pdf" }));
  await user.click(screen.getByRole("button", { name: "Upload document" }));
  await user.click(screen.getByRole("button", { name: "Sign out" }));
  await fillCredentials();
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  await screen.findByText("No documents yet. Upload a PDF to get started.");
  finishUpload(new Response(null, { status: 401 }));
  await user.click(screen.getByRole("button", { name: "Refresh list" }));
  expect(screen.getByLabelText("PDF document")).toBeInTheDocument();
  expect(screen.queryByLabelText("Password")).not.toBeInTheDocument();
});
