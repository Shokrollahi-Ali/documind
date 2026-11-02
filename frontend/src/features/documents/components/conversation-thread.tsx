import type { ConversationTurn } from "../hooks/use-document-conversation";
import AnswerView from "./answer-view";

function QuestionBubble({ question }: { question: string }) {
  return (
    <p className="rounded-lg bg-zinc-100 px-3 py-2 text-base wrap-break-word dark:bg-zinc-800">{question}</p>
  );
}

export default function ConversationThread({ turns, pendingQuestion }: {
  turns: ConversationTurn[];
  pendingQuestion?: string;
}) {
  const hasPendingQuestion = pendingQuestion !== undefined;

  return (
    <div aria-live="polite" className="flex flex-col gap-5">
      {turns.length === 0 && !hasPendingQuestion && (
        <p className="text-base text-zinc-600 dark:text-zinc-400">
          Ask anything about this document. Answers come only from its text, with the pages they came from.
        </p>
      )}
      {turns.map((turn, index) => (
        <div key={index} className="flex flex-col gap-2">
          <QuestionBubble question={turn.question} />
          <AnswerView answer={turn.answer} />
        </div>
      ))}
      {hasPendingQuestion && (
        <div className="flex flex-col gap-2">
          <QuestionBubble question={pendingQuestion} />
          <p role="status" className="text-base text-zinc-600 dark:text-zinc-400">
            Reading the document… this can take up to a minute.
          </p>
        </div>
      )}
    </div>
  );
}
