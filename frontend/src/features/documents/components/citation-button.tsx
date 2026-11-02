export default function CitationButton({ number, isOpen, onClick }: {
  number: number;
  isOpen: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-expanded={isOpen}
      className="mx-0.5 inline-flex h-[18px] items-center rounded-full bg-blue-100 px-1.5 text-[11px] text-blue-800 hover:bg-blue-200 aria-expanded:bg-blue-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 dark:bg-blue-950 dark:text-blue-200 dark:hover:bg-blue-900 dark:aria-expanded:bg-blue-900"
    >
      Source {number}
    </button>
  );
}
