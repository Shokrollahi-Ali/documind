import { act, renderHook } from "@testing-library/react";
import { expect, it } from "vitest";

import { useConversationHistory } from "./use-conversation-history";

const turn = { question: "What is the notice period?", answer: { answer: "Sixty days.", sources: [] } };

it("keeps each document's turns separate and in order", () => {
  const { result } = renderHook(() => useConversationHistory());
  const secondTurn = { ...turn, question: "Who gives notice?" };
  act(() => {
    result.current.addTurn("first", turn);
    result.current.addTurn("first", secondTurn);
    result.current.addTurn("second", secondTurn);
  });
  expect(result.current.getTurns("first")).toEqual([turn, secondTurn]);
  expect(result.current.getTurns("second")).toEqual([secondTurn]);
  expect(result.current.getTurns("unknown")).toEqual([]);
});

it("clears only the deleted document's history", () => {
  const { result } = renderHook(() => useConversationHistory());
  act(() => {
    result.current.addTurn("first", turn);
    result.current.addTurn("second", turn);
  });
  act(() => result.current.clearTurns("first"));
  expect(result.current.getTurns("first")).toEqual([]);
  expect(result.current.getTurns("second")).toEqual([turn]);
});

it("starts empty when the workspace is mounted again", () => {
  const firstWorkspace = renderHook(() => useConversationHistory());
  act(() => firstWorkspace.result.current.addTurn("first", turn));
  firstWorkspace.unmount();
  const nextWorkspace = renderHook(() => useConversationHistory());
  expect(nextWorkspace.result.current.getTurns("first")).toEqual([]);
});
