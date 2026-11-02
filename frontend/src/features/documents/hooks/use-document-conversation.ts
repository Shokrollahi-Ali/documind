import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { askDocument } from "../api/ask-document";
import type { DocumentAnswer } from "../lib/document-answer";

export type ConversationTurn = {
  question: string;
  answer: DocumentAnswer;
};

export function useDocumentConversation(documentId: string) {
  const [turns, setTurns] = useState<ConversationTurn[]>([]);

  const asking = useMutation({
    mutationFn: (question: string) => askDocument(documentId, question),
    onSuccess: (answer, question) => {
      setTurns((currentTurns) => [...currentTurns, { question, answer }]);
    },
    retry: false,
  });

  function askQuestion(question: string, onAnswered: () => void) {
    asking.mutate(question, { onSuccess: onAnswered });
  }

  return {
    turns,
    askQuestion,
    isAsking: asking.isPending,
    pendingQuestion: asking.isPending ? asking.variables : undefined,
    errorMessage: asking.error?.message ?? null,
  };
}
