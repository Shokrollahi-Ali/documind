import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";

import QuestionForm from "./question-form";

function renderForm({ isAsking = false, errorMessage = null, onAsk = vi.fn() }: {
  isAsking?: boolean;
  errorMessage?: string | null;
  onAsk?: (question: string, onAnswered: () => void) => void;
} = {}) {
  render(<QuestionForm isAsking={isAsking} errorMessage={errorMessage} onAsk={onAsk} />);
}

it("starts with an empty, labelled question box", () => {
  renderForm();

  expect(screen.getByLabelText("Your question")).toHaveValue("");
  expect(screen.getByRole("button", { name: "Ask" })).toBeEnabled();
  expect(screen.getByText("0 / 2,000")).toBeInTheDocument();
});

it("asks for a question instead of sending an empty one", async () => {
  const user = userEvent.setup();
  const onAsk = vi.fn();
  renderForm({ onAsk });

  await user.click(screen.getByRole("button", { name: "Ask" }));

  expect(screen.getByRole("alert")).toHaveTextContent("Enter a question first.");
  expect(onAsk).not.toHaveBeenCalled();
});

it("clears the validation message when the user starts typing", async () => {
  const user = userEvent.setup();
  renderForm();
  await user.click(screen.getByRole("button", { name: "Ask" }));

  await user.type(screen.getByLabelText("Your question"), "W");

  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("sends the question without the spaces around it", async () => {
  const user = userEvent.setup();
  const onAsk = vi.fn();
  renderForm({ onAsk });

  await user.type(screen.getByLabelText("Your question"), "  What is the notice period?  ");
  await user.click(screen.getByRole("button", { name: "Ask" }));

  expect(onAsk).toHaveBeenCalledWith("What is the notice period?", expect.any(Function));
});

it("sends the question when Enter is pressed", async () => {
  const user = userEvent.setup();
  const onAsk = vi.fn();
  renderForm({ onAsk });

  await user.type(screen.getByLabelText("Your question"), "What is the notice period?{Enter}");

  expect(onAsk).toHaveBeenCalledTimes(1);
});

it("clears the text once the question has been answered", async () => {
  const user = userEvent.setup();
  const onAsk = vi.fn((_question: string, onAnswered: () => void) => onAnswered());
  renderForm({ onAsk });
  const input = screen.getByLabelText("Your question");

  await user.type(input, "What is the notice period?");
  await user.click(screen.getByRole("button", { name: "Ask" }));

  expect(input).toHaveValue("");
});

it("keeps the text when the question has not been answered", async () => {
  const user = userEvent.setup();
  renderForm({ onAsk: vi.fn() });
  const input = screen.getByLabelText("Your question");

  await user.type(input, "What is the notice period?");
  await user.click(screen.getByRole("button", { name: "Ask" }));

  expect(input).toHaveValue("What is the notice period?");
});

it("counts the characters typed so far", async () => {
  const user = userEvent.setup();
  renderForm();

  await user.type(screen.getByLabelText("Your question"), "abc");

  expect(screen.getByText("3 / 2,000")).toBeInTheDocument();
});

it("shows the error message from the backend", () => {
  renderForm({ errorMessage: "Document is not ready for questions" });

  expect(screen.getByRole("alert")).toHaveTextContent("Document is not ready for questions");
});

it("disables the box and the button while a question is being answered", () => {
  renderForm({ isAsking: true });

  expect(screen.getByLabelText("Your question")).toBeDisabled();
  expect(screen.getByRole("button", { name: "Asking…" })).toBeDisabled();
});
