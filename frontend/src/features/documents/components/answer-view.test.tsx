import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";

import type { DocumentAnswer } from "../lib/document-answer";
import AnswerView from "./answer-view";

const noticeSource = { chunk_index: 3, page_number: 4, text: "Sixty days notice." };
const emailSource = { chunk_index: 8, page_number: 7, text: "Email must be acknowledged." };
const answer: DocumentAnswer = {
  answer: "Give 60 days notice [chunk 3]. Email counts only if confirmed [chunk 8].",
  sources: [noticeSource, emailSource],
};

it("shows the answer with a numbered button for each source", () => {
  render(<AnswerView answer={answer} />);

  expect(screen.getByText(/Give 60 days notice/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Source 1" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Source 2" })).toBeInTheDocument();
  expect(screen.queryByText(/\[chunk/)).not.toBeInTheDocument();
});

it("keeps the sources hidden until asked", () => {
  render(<AnswerView answer={answer} />);

  expect(screen.queryByText("Sixty days notice.")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Source 1" })).toHaveAttribute("aria-expanded", "false");
});

it("opens and closes one source when its button is clicked", async () => {
  const user = userEvent.setup();
  render(<AnswerView answer={answer} />);

  await user.click(screen.getByRole("button", { name: "Source 1" }));

  expect(screen.getByText("Source 1 · page 4")).toBeInTheDocument();
  expect(screen.getByText("Sixty days notice.")).toBeInTheDocument();
  expect(screen.queryByText("Email must be acknowledged.")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Source 1" })).toHaveAttribute("aria-expanded", "true");

  await user.click(screen.getByRole("button", { name: "Source 1" }));

  expect(screen.queryByText("Sixty days notice.")).not.toBeInTheDocument();
});

it("shows and hides every source with one button", async () => {
  const user = userEvent.setup();
  render(<AnswerView answer={answer} />);

  await user.click(screen.getByRole("button", { name: "Show 2 sources" }));

  expect(screen.getByText("Source 1 · page 4")).toBeInTheDocument();
  expect(screen.getByText("Source 2 · page 7")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Hide sources" }));

  expect(screen.queryByText("Source 1 · page 4")).not.toBeInTheDocument();
  expect(screen.queryByText("Source 2 · page 7")).not.toBeInTheDocument();
});

it("opens the remaining sources when one is already open", async () => {
  const user = userEvent.setup();
  render(<AnswerView answer={answer} />);
  await user.click(screen.getByRole("button", { name: "Source 2" }));

  await user.click(screen.getByRole("button", { name: "Show 2 sources" }));

  expect(screen.getByText("Source 1 · page 4")).toBeInTheDocument();
  expect(screen.getByText("Source 2 · page 7")).toBeInTheDocument();
});

it("words the sources button for a single source", () => {
  render(<AnswerView answer={{ answer: "Sixty days [chunk 3].", sources: [noticeSource] }} />);

  expect(screen.getByRole("button", { name: "Show 1 source" })).toBeInTheDocument();
});

it("lists a source once when it is cited twice", async () => {
  const user = userEvent.setup();
  render(<AnswerView answer={{ answer: "A [chunk 3] and B [chunk 3].", sources: [noticeSource] }} />);

  expect(screen.getAllByRole("button", { name: "Source 1" })).toHaveLength(2);

  await user.click(screen.getByRole("button", { name: "Show 1 source" }));

  expect(screen.getAllByText("Source 1 · page 4")).toHaveLength(1);
});

it("shows no source buttons for an answer without sources", () => {
  const noContextAnswer = { answer: "The passages do not contain enough information.", sources: [] };
  render(<AnswerView answer={noContextAnswer} />);

  expect(screen.getByText("The passages do not contain enough information.")).toBeInTheDocument();
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});
