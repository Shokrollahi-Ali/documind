"use client";

import type { ConversationTurn } from "../hooks/use-document-conversation";
import { useDocumentConversation } from "../hooks/use-document-conversation";
import ConversationThread from "./conversation-thread";
import QuestionForm from "./question-form";
import styles from "./document-workspace.module.css";

export default function QuestionPanel({ documentId, turns, onTurnAdded }: {
  documentId: string;
  turns: ConversationTurn[];
  onTurnAdded: (turn: ConversationTurn) => void;
}) {
  const { askQuestion, isAsking, pendingQuestion, errorMessage } = useDocumentConversation(documentId, onTurnAdded);

  return (
    <div className={styles.questionPanel}>
      <div className={styles.messages} role="region" aria-label="Conversation messages" tabIndex={0}>
        <ConversationThread turns={turns} pendingQuestion={pendingQuestion} />
      </div>
      <div className={styles.composer}>
        <QuestionForm isAsking={isAsking} errorMessage={errorMessage} onAsk={askQuestion} />
      </div>
    </div>
  );
}
