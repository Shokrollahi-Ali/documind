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
  return (
    <li className={`relative rounded-xl border p-3 transition-colors ${isSelected ? selectedStyles : unselectedStyles}`}>
      <h3 className="text-base font-medium">
        <button
          type="button"
          onClick={() => onSelect(document)}
          aria-current={isSelected ? "true" : undefined}
          className="break-all text-left outline-none after:absolute after:inset-0 after:rounded-xl focus-visible:after:outline-2 focus-visible:after:outline-blue-600"
        >
          {document.original_filename}
        </button>
      </h3>
      <p className="text-sm text-zinc-600 dark:text-zinc-400">{formatFileSize(document.size_bytes)}</p>
      <div className="mt-2 flex items-center justify-between gap-2">
        <DocumentStatusBadge status={document.status} />
        <DocumentDelete document={document} onDeleted={onDeleted} />
      </div>
    </li>
  );
}
