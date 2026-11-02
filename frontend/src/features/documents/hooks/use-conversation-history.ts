import { useState } from "react";

import type { ConversationTurn } from "./use-document-conversation";

export function useConversationHistory() {
  const [turnsByDocument, setTurnsByDocument] = useState<Record<string, ConversationTurn[]>>({});

  function getTurns(documentId: string): ConversationTurn[] {
    return turnsByDocument[documentId] ?? [];
  }

  function addTurn(documentId: string, turn: ConversationTurn) {
    setTurnsByDocument((current) => ({
      ...current,
      [documentId]: [...(current[documentId] ?? []), turn],
    }));
  }

  function clearTurns(documentId: string) {
    setTurnsByDocument((current) => {
      const remainingTurns = { ...current };
      delete remainingTurns[documentId];
      return remainingTurns;
    });
  }

  return { getTurns, addTurn, clearTurns };
}

export type ConversationHistory = ReturnType<typeof useConversationHistory>;
