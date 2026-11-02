"use client";

import { useId, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";

import Button from "@/components/button";
import { formatQuestionCounter, validateQuestion } from "../lib/question";

export default function QuestionForm({ isAsking, errorMessage, onAsk }: {
  isAsking: boolean;
  errorMessage: string | null;
  onAsk: (question: string, onAnswered: () => void) => void;
}) {
  const inputId = useId();
  const [draft, setDraft] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  const shownError = validationError ?? errorMessage;

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    setDraft(event.target.value);
    setValidationError(null);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isAsking) return;

    const error = validateQuestion(draft);
    setValidationError(error);
    if (error) return;

    onAsk(draft.trim(), () => setDraft(""));
  }

  return (
    <form onSubmit={handleSubmit} aria-busy={isAsking}>
      <label htmlFor={inputId} className="text-sm text-zinc-600 dark:text-zinc-400">
        Your question
      </label>
      <div className="mt-1 flex items-center gap-2">
        <input
          id={inputId}
          value={draft}
          onChange={handleChange}
          disabled={isAsking}
          placeholder="Ask anything about this document"
          autoComplete="off"
          aria-invalid={Boolean(shownError)}
          className="h-9 min-w-0 flex-1 rounded-lg border border-zinc-300 bg-transparent px-3 text-base placeholder:text-zinc-500 focus-visible:outline-2 focus-visible:outline-blue-600 disabled:opacity-50 dark:border-zinc-700"
        />
        <Button type="submit" variant="primary" disabled={isAsking}>
          {isAsking ? "Asking…" : "Ask"}
        </Button>
      </div>
      <div className="mt-1 flex items-start justify-between gap-2 text-sm">
        {shownError && <p role="alert" className="text-red-700 dark:text-red-400">{shownError}</p>}
        <span className="ml-auto tabular-nums text-zinc-600 dark:text-zinc-400">{formatQuestionCounter(draft)}</span>
      </div>
    </form>
  );
}
