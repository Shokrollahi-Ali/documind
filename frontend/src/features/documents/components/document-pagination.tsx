import Button from "@/components/button";

export default function DocumentPagination({ page, canGoPrevious, canGoNext, onPageChange }: {
  page: number;
  canGoPrevious: boolean;
  canGoNext: boolean;
  onPageChange: (page: number) => void;
}) {
  return (
    <nav aria-label="Document pages" className="mt-4 flex items-center justify-between gap-3">
      <Button size="sm" onClick={() => onPageChange(page - 1)} disabled={!canGoPrevious}>Previous</Button>
      <span className="text-xs text-zinc-600 dark:text-zinc-400">Page {page + 1}</span>
      <Button size="sm" onClick={() => onPageChange(page + 1)} disabled={!canGoNext}>Next</Button>
    </nav>
  );
}
