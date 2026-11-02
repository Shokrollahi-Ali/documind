import { useMutation, useMutationState, useQueryClient } from "@tanstack/react-query";

import { askDocument } from "../api/ask-document";
import type { DocumentAnswer } from "../lib/document-answer";

export type ConversationTurn = {
  question: string;
  answer: DocumentAnswer;
};

export function getDocumentAnswerMutationKey(documentId: string) {
  return ["document-answer", documentId] as const;
}

export function useDocumentConversation(
  documentId: string,
  onTurnAdded: (turn: ConversationTurn) => void,
) {
  const queryClient = useQueryClient();
  const mutationKey = getDocumentAnswerMutationKey(documentId);
  const requests = useMutationState({
    filters: { mutationKey, exact: true },
    select: (mutation) => ({
      status: mutation.state.status,
      question: typeof mutation.state.variables === "string" ? mutation.state.variables : undefined,
      errorMessage: mutation.state.error?.message ?? null,
    }),
  });
  const latestRequest = requests.at(-1);
  const isAsking = latestRequest?.status === "pending";

  const asking = useMutation({
    mutationKey,
    mutationFn: (question: string) => askDocument(documentId, question),
    onSuccess: (answer, question) => onTurnAdded({ question, answer }),
    retry: false,
  });

  function askQuestion(question: string, onAnswered: () => void) {
    if (queryClient.isMutating({ mutationKey, exact: true }) > 0) return;
    asking.mutate(question, { onSuccess: onAnswered });
  }

  return {
    askQuestion,
    isAsking,
    pendingQuestion: isAsking ? latestRequest.question : undefined,
    errorMessage: latestRequest?.errorMessage ?? null,
  };
}
