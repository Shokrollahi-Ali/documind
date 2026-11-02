import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";

import TopBar from "./top-bar";

const account = { id: "user-one", email: "reader@example.com", created_at: "2026-10-20T12:00:00Z" };

it("shows only the brand when nobody is signed in", () => {
  render(<TopBar isSigningOut={false} onSignOut={vi.fn()} />);

  expect(screen.getByText("Documind")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Sign out" })).not.toBeInTheDocument();
});

it("shows the email and a sign-out button for a signed-in user", () => {
  render(<TopBar user={account} isSigningOut={false} onSignOut={vi.fn()} />);

  expect(screen.getByText("reader@example.com")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Sign out" })).toBeEnabled();
});

it("signs out when the button is clicked", async () => {
  const user = userEvent.setup();
  const onSignOut = vi.fn();
  render(<TopBar user={account} isSigningOut={false} onSignOut={onSignOut} />);

  await user.click(screen.getByRole("button", { name: "Sign out" }));

  expect(onSignOut).toHaveBeenCalledTimes(1);
});

it("disables the button and says so while signing out", () => {
  render(<TopBar user={account} isSigningOut onSignOut={vi.fn()} />);

  expect(screen.getByRole("button", { name: "Signing out…" })).toBeDisabled();
});
