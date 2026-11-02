"use client";

import type { ConversationTurn } from "../hooks/use-document-conversation";
import { useDocumentConversation } from "../hooks/use-document-conversation";
import ConversationThread from "./conversation-thread";
import QuestionForm from "./question-form";

export default function QuestionPanel({ documentId, turns, onTurnAdded }: {
  documentId: string;
  turns: ConversationTurn[];
  onTurnAdded: (turn: ConversationTurn) => void;
}) {
  const { askQuestion, isAsking, pendingQuestion, errorMessage } = useDocumentConversation(documentId, onTurnAdded);

  return (
    <div className="mt-4 flex flex-col gap-6">
      <ConversationThread turns={turns} pendingQuestion={pendingQuestion} />
      <QuestionForm isAsking={isAsking} errorMessage={errorMessage} onAsk={askQuestion} />
    </div>
  );
}
