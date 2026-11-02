import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";

import DocumentPagination from "./document-pagination";

it("shows the page number starting from one", () => {
  render(<DocumentPagination page={2} canGoPrevious canGoNext onPageChange={vi.fn()} />);

  expect(screen.getByText("Page 3")).toBeInTheDocument();
});

it("moves to the previous and the next page", async () => {
  const user = userEvent.setup();
  const onPageChange = vi.fn();
  render(<DocumentPagination page={2} canGoPrevious canGoNext onPageChange={onPageChange} />);

  await user.click(screen.getByRole("button", { name: "Previous" }));
  expect(onPageChange).toHaveBeenLastCalledWith(1);

  await user.click(screen.getByRole("button", { name: "Next" }));
  expect(onPageChange).toHaveBeenLastCalledWith(3);
});

it("disables the buttons that cannot be used", () => {
  render(<DocumentPagination page={0} canGoPrevious={false} canGoNext={false} onPageChange={vi.fn()} />);

  expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
});
