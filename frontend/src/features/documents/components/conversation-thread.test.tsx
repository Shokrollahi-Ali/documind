import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import type { ConversationTurn } from "../hooks/use-document-conversation";
import ConversationThread from "./conversation-thread";

const turns: ConversationTurn[] = [
  {
    question: "What is the notice period?",
    answer: {
      answer: "Sixty days [chunk 1].",
      sources: [{ chunk_index: 1, page_number: 4, text: "Sixty days notice." }],
    },
  },
  {
    question: "Can I keep a pet?",
    answer: { answer: "The passages do not contain enough information.", sources: [] },
  },
];

it("invites the user to ask a question when the conversation is empty", () => {
  render(<ConversationThread turns={[]} />);

  expect(screen.getByText(/Ask anything about this document/)).toBeInTheDocument();
});

it("shows every question with its answer in the order they were asked", () => {
  render(<ConversationThread turns={turns} />);

  const questions = screen.getAllByText(/\?$/).map((element) => element.textContent);

  expect(questions).toEqual(["What is the notice period?", "Can I keep a pet?"]);
  expect(screen.getByRole("button", { name: "Source 1" })).toBeInTheDocument();
  expect(screen.getByText("The passages do not contain enough information.")).toBeInTheDocument();
  expect(screen.queryByText(/Ask anything about this document/)).not.toBeInTheDocument();
});

it("shows the waiting message under a question that has no answer yet", () => {
  render(<ConversationThread turns={[]} pendingQuestion="What is the notice period?" />);

  expect(screen.getByText("What is the notice period?")).toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("Reading the document… this can take up to a minute.");
  expect(screen.queryByText(/Ask anything about this document/)).not.toBeInTheDocument();
});

it("keeps earlier answers visible while the next question is waiting", () => {
  render(<ConversationThread turns={turns} pendingQuestion="Another question?" />);

  expect(screen.getByText("What is the notice period?")).toBeInTheDocument();
  expect(screen.getByText("Another question?")).toBeInTheDocument();
  expect(screen.getByRole("status")).toBeInTheDocument();
});
