import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, expect, it, vi } from "vitest";

import { askDocument } from "../api/ask-document";
import type { DocumentAnswer } from "../lib/document-answer";
import { useConversationHistory } from "./use-conversation-history";
import { useDocumentConversation } from "./use-document-conversation";

vi.mock("../api/ask-document", () => ({ askDocument: vi.fn() }));

const documentId = "fdc6e6a9-4585-477e-b53a-2576edb7a0e1";
const answer: DocumentAnswer = {
  answer: "Sixty days [chunk 1]",
  sources: [{ chunk_index: 1, page_number: 4, text: "Sixty days notice." }],
};

function createWrapper() {
  const queryClient = new QueryClient();

  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

function renderConversation() {
  return renderHook(() => {
    const history = useConversationHistory();
    const conversation = useDocumentConversation(documentId, (turn) => history.addTurn(documentId, turn));
    return { ...conversation, turns: history.getTurns(documentId) };
  }, { wrapper: createWrapper() });
}

beforeEach(() => {
  vi.mocked(askDocument).mockReset();
});

it("starts with no questions", () => {
  const { result } = renderConversation();

  expect(result.current.turns).toEqual([]);
  expect(result.current.isAsking).toBe(false);
  expect(result.current.errorMessage).toBeNull();
});

it("adds the question and its answer once the answer arrives", async () => {
  vi.mocked(askDocument).mockResolvedValue(answer);
  const onAnswered = vi.fn();
  const { result } = renderConversation();

  act(() => result.current.askQuestion("What is the notice period?", onAnswered));

  await waitFor(() => expect(result.current.turns).toHaveLength(1));
  expect(result.current.turns[0]).toEqual({ question: "What is the notice period?", answer });
  expect(askDocument).toHaveBeenCalledWith(documentId, "What is the notice period?");
  expect(onAnswered).toHaveBeenCalledTimes(1);
});

it("reports the question that is waiting for an answer", async () => {
  let finishAnswer!: (value: DocumentAnswer) => void;
  vi.mocked(askDocument).mockImplementation(() => new Promise((resolve) => { finishAnswer = resolve; }));
  const { result } = renderConversation();

  act(() => result.current.askQuestion("What is the notice period?", vi.fn()));

  await waitFor(() => expect(result.current.isAsking).toBe(true));
  expect(result.current.pendingQuestion).toBe("What is the notice period?");

  await act(async () => finishAnswer(answer));

  await waitFor(() => expect(result.current.isAsking).toBe(false));
  expect(result.current.pendingQuestion).toBeUndefined();
});

it("reports an error and keeps the earlier answers", async () => {
  vi.mocked(askDocument)
    .mockResolvedValueOnce(answer)
    .mockRejectedValueOnce(new Error("Document is not ready for questions"));
  const onAnswered = vi.fn();
  const { result } = renderConversation();
  act(() => result.current.askQuestion("First question?", vi.fn()));
  await waitFor(() => expect(result.current.turns).toHaveLength(1));

  act(() => result.current.askQuestion("Second question?", onAnswered));

  await waitFor(() => expect(result.current.errorMessage).toBe("Document is not ready for questions"));
  expect(result.current.turns).toHaveLength(1);
  expect(onAnswered).not.toHaveBeenCalled();
});

it("clears the error when another question is asked", async () => {
  vi.mocked(askDocument)
    .mockRejectedValueOnce(new Error("The model declined to answer this question"))
    .mockResolvedValueOnce(answer);
  const { result } = renderConversation();
  act(() => result.current.askQuestion("First question?", vi.fn()));
  await waitFor(() => expect(result.current.errorMessage).not.toBeNull());

  act(() => result.current.askQuestion("Second question?", vi.fn()));

  await waitFor(() => expect(result.current.turns).toHaveLength(1));
  expect(result.current.errorMessage).toBeNull();
});


it("rejects duplicate submissions before the component rerenders", async () => {
  let finishAnswer!: (value: DocumentAnswer) => void;
  vi.mocked(askDocument).mockImplementation(() => new Promise((resolve) => { finishAnswer = resolve; }));
  const { result } = renderConversation();
  act(() => {
    result.current.askQuestion("First question?", vi.fn());
    result.current.askQuestion("Duplicate question?", vi.fn());
  });
  await waitFor(() => expect(askDocument).toHaveBeenCalledTimes(1));
  await act(async () => finishAnswer(answer));
});

it("restores a pending request and its eventual error after remounting", async () => {
  let rejectAnswer!: (error: Error) => void;
  vi.mocked(askDocument).mockImplementation(() => new Promise((_resolve, reject) => { rejectAnswer = reject; }));
  const wrapper = createWrapper();
  const firstPanel = renderHook(() => useDocumentConversation(documentId, vi.fn()), { wrapper });
  act(() => firstPanel.result.current.askQuestion("Pending question?", vi.fn()));
  await waitFor(() => expect(firstPanel.result.current.isAsking).toBe(true));
  firstPanel.unmount();

  const nextPanel = renderHook(() => useDocumentConversation(documentId, vi.fn()), { wrapper });
  expect(nextPanel.result.current.isAsking).toBe(true);
  expect(nextPanel.result.current.pendingQuestion).toBe("Pending question?");
  act(() => nextPanel.result.current.askQuestion("Duplicate?", vi.fn()));
  expect(askDocument).toHaveBeenCalledTimes(1);

  await act(async () => rejectAnswer(new Error("Answer service unavailable")));
  await waitFor(() => expect(nextPanel.result.current.isAsking).toBe(false));
  expect(nextPanel.result.current.errorMessage).toBe("Answer service unavailable");
  vi.mocked(askDocument).mockResolvedValue(answer);
  act(() => nextPanel.result.current.askQuestion("Retry question?", vi.fn()));
  await waitFor(() => expect(nextPanel.result.current.errorMessage).toBeNull());
  await waitFor(() => expect(nextPanel.result.current.isAsking).toBe(false));
  expect(askDocument).toHaveBeenCalledTimes(2);
});
