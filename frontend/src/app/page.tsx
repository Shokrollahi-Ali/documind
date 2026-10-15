import DocumentWorkspace from "@/features/documents/components/document-workspace";

export default function HomePage() {
  return (
    <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-12 font-sans">
      <header className="space-y-3">
        <p className="text-sm font-semibold tracking-wide">Documind</p>
        <h1 className="text-3xl font-semibold tracking-tight">Your documents</h1>
        <p className="text-base text-zinc-600 dark:text-zinc-400">
          Select a PDF document to get started.
        </p>
      </header>
      <DocumentWorkspace />
    </main>
  );
}
