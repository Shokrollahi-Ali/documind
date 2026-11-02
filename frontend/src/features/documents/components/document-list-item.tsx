import type { DocumentMetadata } from "../lib/document";
import { formatFileSize } from "../lib/format-file-size";
import DocumentDelete from "./document-delete";
import DocumentStatusBadge from "./document-status-badge";

export default function DocumentListItem({ document, onDeleted }: {
  document: DocumentMetadata;
  onDeleted: (documentId: string) => Promise<void>;
}) {
  return (
    <li className="rounded-xl border border-zinc-200 p-3 dark:border-zinc-800">
      <h3 className="break-all text-[13px] font-medium">{document.original_filename}</h3>
      <p className="text-xs text-zinc-600 dark:text-zinc-400">{formatFileSize(document.size_bytes)}</p>
      <div className="mt-2 flex items-center justify-between gap-2">
        <DocumentStatusBadge status={document.status} />
        <DocumentDelete document={document} onDeleted={onDeleted} />
      </div>
    </li>
  );
}
