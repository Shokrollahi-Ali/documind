import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";

import { askDocument } from "../api/ask-document";
import type { DocumentAnswer } from "../lib/document-answer";
import QuestionPanel from "./question-panel";

vi.mock("../api/ask-document", () => ({ askDocument: vi.fn() }));

const documentId = "fdc6e6a9-4585-477e-b53a-2576edb7a0e1";
const noticeAnswer: DocumentAnswer = {
  answer: "Sixty days [chunk 1].",
  sources: [{ chunk_index: 1, page_number: 4, text: "Sixty days notice." }],
};

function renderPanel() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <QuestionPanel documentId={documentId} />
    </QueryClientProvider>,
  );
}

async function askQuestion(question: string) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Your question"), question);
  await user.click(screen.getByRole("button", { name: "Ask" }));
}

beforeEach(() => {
  vi.mocked(askDocument).mockReset();
});

it("invites the user to ask a question", () => {
  renderPanel();

  expect(screen.getByText(/Ask anything about this document/)).toBeInTheDocument();
  expect(screen.getByLabelText("Your question")).toHaveValue("");
});

it("shows progress while waiting and then the answer with its sources", async () => {
  let finishAnswer!: (value: DocumentAnswer) => void;
  vi.mocked(askDocument).mockImplementation(() => new Promise((resolve) => { finishAnswer = resolve; }));
  renderPanel();

  await askQuestion("What is the notice period?");

  expect(screen.getByRole("status")).toHaveTextContent("Reading the document");
  expect(screen.getByRole("button", { name: "Asking…" })).toBeDisabled();
  expect(screen.getByLabelText("Your question")).toBeDisabled();

  await act(async () => finishAnswer(noticeAnswer));

  expect(await screen.findByRole("button", { name: "Source 1" })).toBeInTheDocument();
  expect(screen.getByText("What is the notice period?")).toBeInTheDocument();
  await waitFor(() => expect(screen.getByRole("button", { name: "Ask" })).toBeEnabled());
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  expect(screen.getByLabelText("Your question")).toHaveValue("");
});

it("sends the question for this document", async () => {
  vi.mocked(askDocument).mockResolvedValue(noticeAnswer);
  renderPanel();

  await askQuestion("What is the notice period?");

  expect(await screen.findByRole("button", { name: "Source 1" })).toBeInTheDocument();
  expect(askDocument).toHaveBeenCalledWith(documentId, "What is the notice period?");
});

it("keeps every question and answer in the conversation", async () => {
  vi.mocked(askDocument).mockResolvedValue(noticeAnswer);
  renderPanel();

  await askQuestion("First question?");
  await screen.findByRole("button", { name: "Source 1" });
  await waitFor(() => expect(screen.getByRole("button", { name: "Ask" })).toBeEnabled());
  await askQuestion("Second question?");

  expect(await screen.findByText("Second question?")).toBeInTheDocument();
  expect(screen.getByText("First question?")).toBeInTheDocument();
});

it("does not send an empty question", async () => {
  const user = userEvent.setup();
  renderPanel();

  await user.click(screen.getByRole("button", { name: "Ask" }));

  expect(screen.getByRole("alert")).toHaveTextContent("Enter a question first.");
  expect(askDocument).not.toHaveBeenCalled();
});

it("shows the error and keeps the question so the user can try again", async () => {
  vi.mocked(askDocument).mockRejectedValue(new Error("A valid answer could not be generated"));
  renderPanel();

  await askQuestion("What is the notice period?");

  expect(await screen.findByRole("alert")).toHaveTextContent("A valid answer could not be generated");
  expect(screen.getByLabelText("Your question")).toHaveValue("What is the notice period?");
  expect(screen.getByRole("button", { name: "Ask" })).toBeEnabled();
});
