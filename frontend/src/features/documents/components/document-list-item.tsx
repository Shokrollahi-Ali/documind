import { useIsMutating } from "@tanstack/react-query";

import { LoadingIcon } from "@/components/icons";

import { getDocumentAnswerMutationKey } from "../hooks/use-document-conversation";
import type { DocumentMetadata } from "../lib/document";
import { formatFileSize } from "../lib/format-file-size";
import DocumentDelete from "./document-delete";
import DocumentStatusBadge from "./document-status-badge";

const selectedStyles = "border-blue-300 bg-blue-50 dark:border-blue-800 dark:bg-blue-950";
const unselectedStyles = "border-zinc-200 hover:border-zinc-400 dark:border-zinc-800 dark:hover:border-zinc-600";

export default function DocumentListItem({ document, isSelected, onSelect, onDeleted }: {
  document: DocumentMetadata;
  isSelected: boolean;
  onSelect: (document: DocumentMetadata) => void;
  onDeleted: (documentId: string) => Promise<void>;
}) {
  const isAnswering = useIsMutating({
    mutationKey: getDocumentAnswerMutationKey(document.id),
    exact: true,
  }) > 0;

  return (
    <li className={`relative rounded-xl border p-3 transition-colors ${isSelected ? selectedStyles : unselectedStyles}`}>
      <h3 className="text-base font-medium">
        <button
          type="button"
          onClick={() => onSelect(document)}
          aria-current={isSelected ? "true" : undefined}
          title={document.original_filename}
          className="block w-full truncate text-left outline-none after:absolute after:inset-0 after:rounded-xl focus-visible:after:outline-2 focus-visible:after:outline-blue-600"
        >
          {document.original_filename}
        </button>
      </h3>
      <p className="text-sm text-zinc-600 dark:text-zinc-400">{formatFileSize(document.size_bytes)}</p>
      <div className="mt-2 flex items-center justify-between gap-2">
        {isAnswering ? (
          <span
            role="status"
            aria-label={`Generating answer for ${document.original_filename}`}
            className="inline-flex h-6 items-center gap-1.5 rounded-full bg-blue-100 px-2.5 text-sm text-blue-900 dark:bg-blue-950 dark:text-blue-200"
          >
            <LoadingIcon className="animate-spin motion-reduce:animate-none" />
            Answering…
          </span>
        ) : (
          <DocumentStatusBadge status={document.status} />
        )}
        <DocumentDelete document={document} onDeleted={onDeleted} />
      </div>
    </li>
  );
}
