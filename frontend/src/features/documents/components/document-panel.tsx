import type { ConversationHistory } from "../hooks/use-conversation-history";
import type { DocumentMetadata } from "../lib/document";
import { getDocumentStage } from "../lib/document-status";
import QuestionPanel from "./question-panel";

export default function DocumentPanel({ document, history }: {
  document: DocumentMetadata | null;
  history: ConversationHistory;
}) {
  if (!document) {
    return (
      <p className="text-base text-zinc-600 dark:text-zinc-400">
        Select a document from the list, or upload a new one.
      </p>
    );
  }

  const stage = getDocumentStage(document.status);

  return (
    <section aria-labelledby="selected-document-heading">
      <h2 id="selected-document-heading" className="break-all text-xl font-medium">
        {document.original_filename}
      </h2>
      {stage === "preparing" && (
        <p role="status" className="mt-3 text-base text-zinc-600 dark:text-zinc-400">
          This document is still being prepared. This page updates by itself, and you can ask questions once it’s ready.
        </p>
      )}
      {stage === "ready" && (
        <QuestionPanel
          key={document.id}
          documentId={document.id}
          turns={history.getTurns(document.id)}
          onTurnAdded={(turn) => history.addTurn(document.id, turn)}
        />
      )}
      {stage === "failed" && (
        <>
          <p className="mt-3 text-base text-red-700 dark:text-red-400">
            This document couldn’t be processed, so it can’t answer questions. Scanned or password-protected PDFs often cause this.
          </p>
          <p className="mt-2 text-base text-zinc-600 dark:text-zinc-400">
            Delete it from the list and upload a different file.
          </p>
        </>
      )}
    </section>
  );
}
