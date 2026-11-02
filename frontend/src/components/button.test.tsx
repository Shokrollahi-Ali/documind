import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { FormEvent } from "react";
import { expect, it, vi } from "vitest";

import Button from "./button";

it("does not submit a form unless it is a submit button", async () => {
  const user = userEvent.setup();
  const onSubmit = vi.fn((event: FormEvent) => event.preventDefault());
  render(
    <form onSubmit={onSubmit}>
      <Button>Plain</Button>
      <Button type="submit">Send</Button>
    </form>,
  );

  await user.click(screen.getByRole("button", { name: "Plain" }));
  expect(onSubmit).not.toHaveBeenCalled();

  await user.click(screen.getByRole("button", { name: "Send" }));
  expect(onSubmit).toHaveBeenCalledTimes(1);
});

it("passes standard button attributes through", async () => {
  const user = userEvent.setup();
  const onClick = vi.fn();
  render(<Button onClick={onClick} aria-label="Refresh list" disabled>Refresh</Button>);

  const button = screen.getByRole("button", { name: "Refresh list" });
  expect(button).toBeDisabled();

  await user.click(button);
  expect(onClick).not.toHaveBeenCalled();
});

it("keeps custom classes next to its own styles", () => {
  render(<Button className="mt-4">Cancel</Button>);

  expect(screen.getByRole("button", { name: "Cancel" })).toHaveClass("mt-4", "rounded-lg");
});
