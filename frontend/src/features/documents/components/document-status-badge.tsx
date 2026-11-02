import { documentStageLabels, getDocumentStage } from "../lib/document-status";
import type { DocumentStage, DocumentStatus } from "../lib/document-status";

const stageStyles: Record<DocumentStage, string> = {
  preparing: "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200",
  ready: "bg-green-100 text-green-900 dark:bg-green-950 dark:text-green-200",
  failed: "bg-red-100 text-red-900 dark:bg-red-950 dark:text-red-200",
};

export default function DocumentStatusBadge({ status }: { status: DocumentStatus }) {
  const stage = getDocumentStage(status);

  return (
    <span className={`inline-flex h-6 items-center rounded-full px-2.5 text-sm ${stageStyles[stage]}`}>
      {documentStageLabels[stage]}
    </span>
  );
}
