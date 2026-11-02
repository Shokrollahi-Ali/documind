import type { DocumentAnswerSource } from "../lib/document-answer";

export default function SourcePassage({ number, source }: {
  number: number;
  source: DocumentAnswerSource;
}) {
  return (
    <div className="mt-2 rounded-lg bg-zinc-100 px-3 py-2 text-sm text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
      <p className="font-medium text-zinc-900 dark:text-zinc-100">Source {number} · page {source.page_number}</p>
      <p className="mt-1 whitespace-pre-wrap text-justify hyphens-auto wrap-break-word">{source.text}</p>
    </div>
  );
}
